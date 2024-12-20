#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re
from functools import lru_cache, partial
from tempfile import TemporaryDirectory

from epub import EPUBHelpBuilder
from sphinx.util.console import bold
from sphinx.util.logging import getLogger

from calibre.linux import cli_index_strings, entry_points


def info(*a):
    getLogger(__name__).info(*a)


def warn(*a):
    getLogger(__name__).warn(*a)


include_pat = re.compile(r'^.. include:: (\S+.rst)', re.M)


@lru_cache(2)
def formatter_funcs():
    from calibre.db.legacy import LibraryDatabase
    from calibre.utils.ffml_processor import FFMLProcessor
    from calibre.utils.formatter_functions import formatter_functions

    ans = {'doc': {}, 'sum': {}}
    with TemporaryDirectory() as tdir:
        db = LibraryDatabase(tdir) # needed to load formatter_funcs
        ffml = FFMLProcessor()
        all_funcs = formatter_functions().get_builtins()
        for func_name, func in all_funcs.items():
            # indent the text since :ffdoc: is used inside lists
            # if we need no indent we can create a new role like
            # :ffdoc-no-indent:
            text = ffml.document_to_rst(func.doc, func_name, indent=1)
            ans['doc'][func_name] = text.strip()
            text = ffml.document_to_summary_rst(func.doc, func_name, indent=1)
            ans['sum'][func_name] = text.strip()
        db.close()
        del db
    return ans


def ffdoc(language, m):
    func_name = m.group(1)
    try:
        return formatter_funcs()['doc'][func_name]
    except Exception as e:
        if language in ('en', 'eng'):
            raise
        warn(f'Failed to process template language docs for in the {language} language with error: {e}')
        return 'INVALID TRANSLATION'


def ffsum(language, m):
    func_name = m.group(1)
    try:
        return formatter_funcs()['sum'][func_name]
    except Exception as e:
        if language in ('en', 'eng'):
            raise
        warn(f'Failed to process template language summary docs for in the {language} language with error: {e}')
        return 'INVALID TRANSLATION'


def source_read_handler(app, docname, source):
    src = source[0]
    if app.builder.name == 'gettext':
        if docname == 'template_lang':
            src = re.sub(r':(ffdoc|ffsum):`(.+?)`', ' ', src)  # ffdoc and ffsum should not be translated
    else:
        if app.config.language != 'en':
            src = re.sub(r'(\s+generated/)en/', r'\1' + app.config.language + '/', src)
        if docname == 'template_lang':
            try:
                src = re.sub(r':ffdoc:`(.+?)`', partial(ffdoc, app.config.language), src)
                src = re.sub(r':ffsum:`(.+?)`', partial(ffsum, app.config.language), src)
            except Exception:
                import traceback
                traceback.print_exc()
                raise
    # Sphinx does not call source_read_handle for the .. include directive
    for m in reversed(tuple(include_pat.finditer(src))):
        included_doc_name = m.group(1).lstrip('/')
        ss = [open(included_doc_name, 'rb').read().decode('utf-8')]
        source_read_handler(app, included_doc_name.partition('.')[0], ss)
        src = src[:m.start()] + ss[0] + src[m.end():]
    source[0] = src


CLI_INDEX='''
.. _cli:

%s
=========================================================

.. image:: ../../images/cli.png

.. note::
    %s

%s
--------------------------------------

.. toctree::
    :maxdepth: 1

{documented}

%s
----------------------------------------

{undocumented}

%s
'''

CLI_PREAMBLE='''\
.. _{cmdref}:

.. raw:: html

    <style>code {{font-size: 1em; background-color: transparent; font-family: sans-serif }}</style>

``{cmd}``
===================================================================

.. code-block:: none

    {cmdline}

{usage}
'''


def titlecase(language, x):
    if x and language == 'en':
        from calibre.utils.titlecase import titlecase as tc
        x = tc(x)
    return x


def generate_calibredb_help(preamble, language):
    from calibre.db.cli.main import COMMANDS, get_parser, option_parser_for
    preamble = preamble[:preamble.find('\n\n\n', preamble.find('code-block'))]
    preamble += '\n\n'
    preamble += _('''\
:command:`calibredb` is the command line interface to the calibre database. It has
several sub-commands, documented below.

:command:`calibredb` can be used to manipulate either a calibre database
specified by path or a calibre :guilabel:`Content server` running either on
the local machine or over the internet. You can start a calibre
:guilabel:`Content server` using either the :command:`calibre-server`
program or in the main calibre program click :guilabel:`Connect/share ->
Start Content server`. Since :command:`calibredb` can make changes to your
calibre libraries, you must setup authentication on the server first. There
are two ways to do that:

    * If you plan to connect only to a server running on the same computer,
      you can simply use the ``--enable-local-write`` option of the
      Content server, to allow any program, including calibredb, running on
      the local computer to make changes to your calibre data. When running
      the server from the main calibre program, this option is in
      :guilabel:`Preferences->Sharing over the net->Advanced`.

    * If you want to enable access over the internet, then you should setup
      user accounts on the server and use the :option:`--username` and :option:`--password`
      options to :command:`calibredb` to give it access. You can setup
      user authentication for :command:`calibre-server` by using the ``--enable-auth``
      option and using ``--manage-users`` to create the user accounts.
      If you are running the server from the main calibre program, use
      :guilabel:`Preferences->Sharing over the net->Require username/password`.

To connect to a running Content server, pass the URL of the server to the
:option:`--with-library` option, see the documentation of that option for
details and examples.
    ''')

    global_parser = get_parser('')
    groups = []
    for grp in global_parser.option_groups:
        groups.append((titlecase(language, grp.title), grp.description, grp.option_list))

    global_options = '\n'.join(render_options('calibredb', groups, False, False))

    lines = []
    for cmd in COMMANDS:
        parser = option_parser_for(cmd)()
        lines += ['.. _calibredb-%s-%s:' % (language, cmd), '']
        lines += [cmd, '~'*20, '']
        usage = parser.usage.strip()
        usage = [i for i in usage.replace('%prog', 'calibredb').splitlines()]
        cmdline = '    '+usage[0]
        usage = usage[1:]
        usage = [re.sub(r'(%s)([^a-zA-Z0-9])'%cmd, r':command:`\1`\2', i) for i in usage]
        lines += ['.. code-block:: none', '', cmdline, '']
        lines += usage
        groups = [(None, None, parser.option_list)]
        lines += ['']
        lines += render_options('calibredb '+cmd, groups, False)
        lines += ['']
        for group in parser.option_groups:
            if not getattr(group, 'is_global_options', False):
                lines.extend(render_options(
                    'calibredb_' + cmd, [[titlecase(language, group.title), group.description, group.option_list]], False, False, header_level='^'))
        lines += ['']

    raw = preamble + '\n\n'+'.. contents::\n  :local:'+ '\n\n' + global_options+'\n\n'+'\n'.join(lines)
    update_cli_doc('calibredb', raw, language)


def generate_ebook_convert_help(preamble, app):
    from calibre.customize.ui import input_format_plugins, output_format_plugins
    from calibre.ebooks.conversion.cli import create_option_parser, manual_index_strings
    from calibre.utils.logging import default_log
    preamble = re.sub(r'http.*\.html', ':ref:`conversion`', preamble)

    raw = preamble + '\n\n' + manual_index_strings() % 'ebook-convert myfile.input_format myfile.output_format -h'
    parser, plumber = create_option_parser(['ebook-convert',
        'dummyi.mobi', 'dummyo.epub', '-h'], default_log)
    groups = [(None, None, parser.option_list)]
    for grp in parser.option_groups:
        if grp.title not in {'INPUT OPTIONS', 'OUTPUT OPTIONS'}:
            groups.append((titlecase(app, grp.title), grp.description, grp.option_list))
    options = '\n'.join(render_options('ebook-convert', groups, False))

    raw += '\n\n.. contents::\n  :local:'

    raw += '\n\n' + options
    for pl in sorted(input_format_plugins(), key=lambda x: x.name):
        parser, plumber = create_option_parser(['ebook-convert',
            'dummyi.'+sorted(pl.file_types)[0], 'dummyo.epub', '-h'], default_log)
        groups = [(pl.name+ ' Options', '', g.option_list) for g in
                parser.option_groups if g.title == "INPUT OPTIONS"]
        prog = 'ebook-convert-'+(pl.name.lower().replace(' ', '-'))
        raw += '\n\n' + '\n'.join(render_options(prog, groups, False, True))
    for pl in sorted(output_format_plugins(), key=lambda x: x.name):
        parser, plumber = create_option_parser(['ebook-convert', 'd.epub',
            'dummyi.'+pl.file_type, '-h'], default_log)
        groups = [(pl.name+ ' Options', '', g.option_list) for g in
                parser.option_groups if g.title == "OUTPUT OPTIONS"]
        prog = 'ebook-convert-'+(pl.name.lower().replace(' ', '-'))
        raw += '\n\n' + '\n'.join(render_options(prog, groups, False, True))

    update_cli_doc('ebook-convert', raw, app)


def update_cli_doc(name, raw, language):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    path = 'generated/%s/%s.rst' % (language, name)
    old_raw = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
    if not os.path.exists(path) or old_raw != raw:
        import difflib
        print(path, 'has changed')
        if old_raw:
            lines = difflib.unified_diff(old_raw.splitlines(), raw.splitlines(),
                    path, path)
            for line in lines:
                print(line)
        info('creating '+os.path.splitext(os.path.basename(path))[0])
        p = os.path.dirname(path)
        if p and not os.path.exists(p):
            os.makedirs(p)
        open(path, 'wb').write(raw.encode('utf-8'))


def render_options(cmd, groups, options_header=True, add_program=True, header_level='~'):
    lines = ['']
    if options_header:
        lines = [_('[options]'), '-'*40, '']
    if add_program:
        lines += ['.. program:: '+cmd, '']
    for title, desc, options in groups:
        if title:
            lines.extend([title, header_level * (len(title) + 4)])
            lines.append('')
        if desc:
            lines.extend([desc, ''])
        for opt in sorted(options, key=lambda x: x.get_opt_string()):
            help = opt.help or ''
            help = help.replace('\n', ' ').replace('*', '\\*').replace('%default', str(opt.default))
            help = help.replace('"', r'\ ``"``\ ')
            help = help.replace("'", r"\ ``'``\ ")
            help = mark_options(help)
            opt_strings = (x.strip() for x in tuple(opt._long_opts or ()) + tuple(opt._short_opts or ()))
            opt = '.. option:: ' + ', '.join(opt_strings)
            lines.extend([opt, '', '    '+help, ''])
    return lines


def mark_options(raw):
    raw = re.sub(r'(\s+)--(\s+)', r'\1``--``\2', raw)

    def sub(m):
        opt = m.group()
        a, b = opt.partition('=')[::2]
        if a in ('--option1', '--option2'):
            return '``' + m.group() + '``'
        a = ':option:`' + a + '`'
        b = (' = ``' + b + '``') if b else ''
        return a + b
    raw = re.sub(r'(--[|()a-zA-Z0-9_=,-]+)', sub, raw)
    return raw


def get_cli_docs():
    documented_cmds = []
    undocumented_cmds = []
    for script in entry_points['console_scripts'] + entry_points['gui_scripts']:
        module = script[script.index('=')+1:script.index(':')].strip()
        cmd = script[:script.index('=')].strip()
        if cmd in ('calibre-complete', 'calibre-parallel'):
            continue
        module = __import__(module, fromlist=[module.split('.')[-1]])
        if hasattr(module, 'option_parser'):
            try:
                documented_cmds.append((cmd, getattr(module, 'option_parser')()))
            except TypeError:
                documented_cmds.append((cmd, getattr(module, 'option_parser')(cmd)))
        else:
            undocumented_cmds.append(cmd)
    return documented_cmds, undocumented_cmds


def cli_docs(language):
    info(bold('creating CLI documentation...'))
    documented_cmds, undocumented_cmds = get_cli_docs()

    documented_cmds.sort(key=lambda x: x[0])
    undocumented_cmds.sort()

    documented = [' '*4 + c[0] for c in documented_cmds]
    undocumented = ['  * ' + c for c in undocumented_cmds]

    raw = (CLI_INDEX % cli_index_strings()[:5]).format(documented='\n'.join(documented),
            undocumented='\n'.join(undocumented))
    if not os.path.exists('cli'):
        os.makedirs('cli')
    update_cli_doc('cli-index', raw, language)

    for cmd, parser in documented_cmds:
        usage = [mark_options(i) for i in parser.usage.replace('%prog', cmd).splitlines()]
        cmdline = usage[0]
        usage = usage[1:]
        usage = [i.replace(cmd, ':command:`%s`'%cmd) for i in usage]
        usage = '\n'.join(usage)
        preamble = CLI_PREAMBLE.format(cmd=cmd, cmdref=cmd + '-' + language, cmdline=cmdline, usage=usage)
        if cmd == 'ebook-convert':
            generate_ebook_convert_help(preamble, language)
        elif cmd == 'calibredb':
            generate_calibredb_help(preamble, language)
        else:
            groups = [(None, None, parser.option_list)]
            for grp in parser.option_groups:
                groups.append((grp.title, grp.description, grp.option_list))
            raw = preamble
            lines = render_options(cmd, groups)
            raw += '\n'+'\n'.join(lines)
            update_cli_doc(cmd, raw, language)


def generate_docs(language):
    cli_docs(language)
    template_docs(language)


def template_docs(language):
    from template_ref_generate import generate_template_language_help
    raw = generate_template_language_help(language, getLogger(__name__))
    update_cli_doc('template_ref', raw, language)


def localized_path(app, langcode, pagename):
    href = app.builder.get_target_uri(pagename)
    href = re.sub(r'generated/[a-z]+/', 'generated/%s/' % langcode, href)
    prefix = '/'
    if langcode != 'en':
        prefix += langcode + '/'
    return prefix + href


def add_html_context(app, pagename, templatename, context, *args):
    context['localized_path'] = partial(localized_path, app)
    context['change_language_text'] = cli_index_strings()[5]
    context['search_box_text'] = cli_index_strings()[6]


def guilabel_role(typ, rawtext, text, *args, **kwargs):
    from sphinx.roles import GUILabel
    text = text.replace(u'->', u'\N{THIN SPACE}\N{RIGHTWARDS ARROW}\N{THIN SPACE}')
    return GUILabel()(typ, rawtext, text, *args, **kwargs)


def setup_man_pages(app):
    documented_cmds = get_cli_docs()[0]
    man_pages = []
    for cmd, option_parser in documented_cmds:
        path = 'generated/%s/%s' % (app.config.language, cmd)
        man_pages.append((
            path, cmd, cmd, 'Kovid Goyal', 1
        ))
    app.config['man_pages'] = man_pages


def setup(app):
    from docutils.parsers.rst import roles
    setup_man_pages(app)
    generate_docs(app.config.language)
    app.add_css_file('custom.css')
    app.add_builder(EPUBHelpBuilder)
    app.connect('source-read', source_read_handler)
    app.connect('html-page-context', add_html_context)
    app.connect('build-finished', finished)
    roles.register_local_role('guilabel', guilabel_role)


def finished(app, exception):
    pass
