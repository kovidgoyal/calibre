#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, cPickle

from setup import Command, basenames

def get_opts_from_parser(parser):
    def do_opt(opt):
        for x in opt._long_opts:
            yield x
        for x in opt._short_opts:
            yield x
    for o in parser.option_list:
        for x in do_opt(o): yield x
    for g in parser.option_groups:
        for o in g.option_list:
            for x in do_opt(o): yield x

class Resources(Command):

    def get_recipes(self):
        sdir = os.path.join('src', 'calibre', 'web', 'feeds', 'recipes')
        resources= {}
        files = []
        for f in os.listdir(sdir):
            if f.endswith('.py') and f != '__init__.py':
                files.append(os.path.join(sdir, f))
                resources[f.replace('.py', '')] = open(files[-1], 'rb').read()
        return resources, files


    def run(self, opts):
        scripts = {}
        for x in ('console', 'gui'):
            for name in basenames[x]:
                if name in ('calibre-complete', 'calibre_postinstall'):
                    continue
                scripts[name] = x

        dest = self.j(self.RESOURCES, 'scripts.pickle')
        if self.newer(dest, self.j(self.SRC, 'calibre', 'linux.py')):
            self.info('\tCreating scripts.pickle')
            f = open(dest, 'wb')
            cPickle.dump(scripts, f, -1)

        recipes, files = self.get_recipes()

        dest = self.j(self.RESOURCES, 'recipes.pickle')
        if self.newer(dest, files):
            self.info('\tCreating recipes.pickle')
            f = open(dest, 'wb')
            cPickle.dump(recipes, f, -1)

        dest = self.j(self.RESOURCES, 'ebook-convert-complete.pickle')
        files = []
        for x in os.walk(self.j(self.SRC, 'calibre')):
            for f in x[-1]:
                if f.endswith('.py'):
                    files.append(self.j(x[0], f))
        if self.newer(dest, files):
            self.info('\tCreating ebook-convert-complete.pickle')
            complete = {}
            from calibre.ebooks.conversion.plumber import supported_input_formats
            complete['input_fmts'] = set(supported_input_formats())
            from calibre.web.feeds.recipes import recipes
            complete['input_recipes'] = [t.title+'.recipe ' for t in recipes]
            from calibre.customize.ui import available_output_formats
            complete['output'] = set(available_output_formats())
            from calibre.ebooks.conversion.cli import create_option_parser
            from calibre.utils.logging import Log
            log = Log()
            #log.outputs = []
            for inf in supported_input_formats():
                if inf in ('zip', 'rar', 'oebzip'):
                    continue
                for ouf in available_output_formats():
                    of = ouf if ouf == 'oeb' else 'dummy.'+ouf
                    p = create_option_parser(('ec', 'dummy1.'+inf, of, '-h'),
                            log)[0]
                    complete[(inf, ouf)] = [x+' 'for x in
                            get_opts_from_parser(p)]

            cPickle.dump(complete, open(dest, 'wb'), -1)




    def clean(self):
        for x in ('scripts', 'recipes', 'ebook-convert-complete'):
            x = self.j(self.RESOURCES, x+'.pickle')
            if os.path.exists(x):
                os.remove(x)




