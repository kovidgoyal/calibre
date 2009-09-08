#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess

from setup import Command, __appname__, __version__

class Manual(Command):

    description='''Build the User Manual '''

    def run(self, opts):
        cwd = os.path.abspath(os.getcwd())
        os.chdir(os.path.join(self.SRC, 'calibre', 'manual'))
        try:
            for d in ('.build', 'cli'):
                if os.path.exists(d):
                    shutil.rmtree(d)
                os.makedirs(d)
            if not os.path.exists('.build'+os.sep+'html'):
                os.makedirs('.build'+os.sep+'html')
            os.environ['__appname__']= __appname__
            os.environ['__version__']= __version__
            subprocess.check_call(['sphinx-build', '-b', 'custom', '-t', 'online',
                                   '-d', '.build/doctrees', '.', '.build/html'])
            subprocess.check_call(['sphinx-build', '-b', 'epub', '-d',
                                   '.build/doctrees', '.', '.build/epub'])
            shutil.copyfile(self.j('.build', 'epub', 'calibre.epub'), self.j('.build',
                'html', 'calibre.epub'))
        finally:
            os.chdir(cwd)

    def clean(self):
        path = os.path.join(self.SRC, 'calibre', 'manual', '.build')
        if os.path.exists(path):
            shutil.rmtree(path)


