#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, cPickle

from setup import Command, basenames

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


    def clean(self):
        for x in ('scripts', 'recipes'):
            x = self.j(self.RESOURCES, x+'.pickle')
            if os.path.exists(x):
                os.remove(x)




