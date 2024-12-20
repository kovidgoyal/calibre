#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import errno
import glob
import json
import os
import shutil
import zipfile

from polyglot.builtins import iteritems, itervalues, only_unicode_recursive
from setup import Command, basenames, download_securely, dump_json


def get_opts_from_parser(parser):
    def do_opt(opt):
        yield from opt._long_opts
        yield from opt._short_opts
    for o in parser.option_list:
        yield from do_opt(o)
    for g in parser.option_groups:
        for o in g.option_list:
            yield from do_opt(o)


class CACerts(Command):  # {{{

    description = 'Get updated mozilla CA certificate bundle'
    CA_PATH = os.path.join(Command.RESOURCES, 'mozilla-ca-certs.pem')

    def add_options(self, parser):
        parser.add_option('--path-to-cacerts', help='Path to previously downloaded mozilla-ca-certs.pem')

    def run(self, opts):
        if opts.path_to_cacerts:
            shutil.copyfile(opts.path_to_cacerts, self.CA_PATH)
            os.chmod(self.CA_PATH, 0o644)
        else:
            try:
                with open(self.CA_PATH, 'rb') as f:
                    raw = f.read()
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise
                raw = b''
            nraw = download_securely('https://curl.haxx.se/ca/cacert.pem')
            if not nraw:
                raise RuntimeError('Failed to download CA cert bundle')
            if nraw != raw:
                self.info('Updating Mozilla CA certificates')
                with open(self.CA_PATH, 'wb') as f:
                    f.write(nraw)
                self.verify_ca_certs()

    def verify_ca_certs(self):
        from calibre.utils.https import get_https_resource_securely
        get_https_resource_securely('https://calibre-ebook.com', cacerts=self.b(self.CA_PATH))
# }}}


class RecentUAs(Command):  # {{{

    description = 'Get updated list of common browser user agents'
    UA_PATH = os.path.join(Command.RESOURCES, 'user-agent-data.json')

    def add_options(self, parser):
        parser.add_option('--path-to-user-agent-data', help='Path to previously downloaded user-agent-data.json')

    def run(self, opts):
        from setup.browser_data import get_data
        if opts.path_to_user_agent_data:
            shutil.copyfile(opts.path_to_user_agent_data, self.UA_PATH)
            os.chmod(self.UA_PATH, 0o644)
        else:
            data = get_data()
            with open(self.UA_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
# }}}


class RapydScript(Command):  # {{{

    description = 'Compile RapydScript to JavaScript'

    def add_options(self, parser):
        parser.add_option('--only-module', default=None,
                help='Only compile the specified module')

    def run(self, opts):
        from calibre.utils.rapydscript import compile_editor, compile_srv, compile_viewer
        if opts.only_module:
            locals()['compile_' + opts.only_module]()
        else:
            compile_editor()
            compile_viewer()
            compile_srv()
# }}}


class Resources(Command):  # {{{

    description = 'Compile various needed calibre resources'
    sub_commands = ['liberation_fonts', 'mathjax', 'rapydscript', 'hyphenation', 'piper_voices']

    def run(self, opts):
        from calibre.utils.serialize import msgpack_dumps
        scripts = {}
        for x in ('console', 'gui'):
            for name in basenames[x]:
                if name in ('calibre-complete', 'calibre_postinstall'):
                    continue
                scripts[name] = x

        dest = self.j(self.RESOURCES, 'scripts.calibre_msgpack')
        if self.newer(dest, self.j(self.SRC, 'calibre', 'linux.py')):
            self.info('\tCreating ' + self.b(dest))
            with open(dest, 'wb') as f:
                f.write(msgpack_dumps(scripts))

        from calibre.web.feeds.recipes.collection import iterate_over_builtin_recipe_files, serialize_builtin_recipes

        files = [x[1] for x in iterate_over_builtin_recipe_files()]

        dest = self.j(self.RESOURCES, 'builtin_recipes.xml')
        if self.newer(dest, files):
            self.info('\tCreating builtin_recipes.xml')
            xml = serialize_builtin_recipes()
            with open(dest, 'wb') as f:
                f.write(xml)

        recipe_icon_dir = self.a(self.j(self.RESOURCES, '..', 'recipes',
            'icons'))
        dest = os.path.splitext(dest)[0] + '.zip'
        files += glob.glob(self.j(recipe_icon_dir, '*.png'))
        if self.newer(dest, files):
            self.info('\tCreating builtin_recipes.zip')
            with zipfile.ZipFile(dest, 'w', zipfile.ZIP_STORED) as zf:
                for n in sorted(files, key=self.b):
                    with open(n, 'rb') as f:
                        zf.writestr(self.b(n), f.read())

        dest = self.j(self.RESOURCES, 'ebook-convert-complete.calibre_msgpack')
        files = []
        for x in os.walk(self.j(self.SRC, 'calibre')):
            for f in x[-1]:
                if f.endswith('.py'):
                    files.append(self.j(x[0], f))
        if self.newer(dest, files):
            self.info('\tCreating ' + self.b(dest))
            complete = {}
            from calibre.ebooks.conversion.plumber import supported_input_formats
            complete['input_fmts'] = set(supported_input_formats())
            from calibre.web.feeds.recipes.collection import get_builtin_recipe_titles
            complete['input_recipes'] = [t+'.recipe ' for t in
                    get_builtin_recipe_titles()]
            from calibre.customize.ui import available_output_formats
            complete['output'] = set(available_output_formats())
            from calibre.ebooks.conversion.cli import create_option_parser
            from calibre.utils.logging import Log
            log = Log()
            # log.outputs = []
            for inf in supported_input_formats():
                if inf in ('zip', 'rar', 'oebzip'):
                    continue
                for ouf in available_output_formats():
                    of = ouf if ouf == 'oeb' else 'dummy.'+ouf
                    p = create_option_parser(('ec', 'dummy1.'+inf, of, '-h'),
                            log)[0]
                    complete[(inf, ouf)] = [x+' 'for x in
                            get_opts_from_parser(p)]

            with open(dest, 'wb') as f:
                f.write(msgpack_dumps(only_unicode_recursive(complete)))

        self.info('\tCreating template-functions.json')
        dest = self.j(self.RESOURCES, 'template-functions.json')
        function_dict = {}
        import inspect

        from calibre.utils.formatter_functions import formatter_functions
        for obj in formatter_functions().get_builtins().values():
            eval_func = inspect.getmembers(obj,
                    lambda x: inspect.ismethod(x) and x.__name__ == 'evaluate')
            try:
                lines = [l[4:] for l in inspect.getsourcelines(eval_func[0][1])[0]]
            except:
                continue
            lines = ''.join(lines)
            function_dict[obj.name] = lines
        dump_json(function_dict, dest)

        self.info('\tCreating editor-functions.json')
        dest = self.j(self.RESOURCES, 'editor-functions.json')
        function_dict = {}
        from calibre.gui2.tweak_book.function_replace import builtin_functions
        for func in builtin_functions():
            try:
                src = ''.join(inspect.getsourcelines(func)[0][1:])
            except Exception:
                continue
            src = src.replace('def ' + func.__name__, 'def replace')
            imports = [f'from {x.__module__} import {x.__name__}' for x in func.imports]
            if imports:
                src = '\n'.join(imports) + '\n\n' + src
            function_dict[func.name] = src
        dump_json(function_dict, dest)
        self.info('\tCreating user-manual-translation-stats.json')
        d = {}
        for lc, stats in iteritems(json.load(open(self.j(self.d(self.SRC), 'manual', 'locale', 'completed.json')))):
            total = sum(itervalues(stats))
            d[lc] = stats['translated'] / float(total)
        dump_json(d, self.j(self.RESOURCES, 'user-manual-translation-stats.json'))

        src = self.j(self.SRC, '..', 'Changelog.txt')
        dest = self.j(self.RESOURCES, 'changelog.json')
        if self.newer(dest, [src]):
            self.info('\tCreating changelog.json')
            from setup.changelog import parse
            with open(src, encoding='utf-8') as f:
                dump_json(parse(f.read(), parse_dates=False), dest)

    def clean(self):
        for x in ('scripts', 'ebook-convert-complete'):
            x = self.j(self.RESOURCES, x+'.pickle')
            if os.path.exists(x):
                os.remove(x)
        for x in ('builtin_recipes.xml', 'builtin_recipes.zip',
                'template-functions.json', 'user-manual-translation-stats.json'):
            x = self.j(self.RESOURCES, x)
            if os.path.exists(x):
                os.remove(x)
# }}}
