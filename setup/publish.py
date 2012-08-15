#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess, glob

from setup import Command, __appname__, __version__


class Stage1(Command):

    description = 'Stage 1 of the publish process'

    sub_commands = [
            'check',
            'pot',
            'build',
            'resources',
            'translations',
            'iso639',
            'gui',
            ]

class Stage2(Command):

   description = 'Stage 2 of the publish process'
   sub_commands = ['linux', 'win', 'osx']

   def pre_sub_commands(self, opts):
       for x in glob.glob(os.path.join(self.d(self.SRC), 'dist', '*')):
           os.remove(x)
       build = os.path.join(self.d(self.SRC), 'build')
       if os.path.exists(build):
           shutil.rmtree(build)

class Stage3(Command):

   description = 'Stage 3 of the publish process'
   sub_commands = ['upload_user_manual', 'upload_demo', 'sdist', 'tag_release']

class Stage4(Command):

    description = 'Stage 4 of the publish process'
    sub_commands = ['upload_installers']

class Stage5(Command):

    description = 'Stage 5 of the publish process'
    sub_commands = ['upload_to_server']

    def run(self, opts):
        subprocess.check_call('rm -rf build/* dist/*', shell=True)

class Publish(Command):

    description = 'Publish a new calibre release'
    sub_commands = ['stage1', 'stage2', 'stage3', 'stage4', 'stage5', ]

class Manual(Command):

    description='''Build the User Manual '''

    def run(self, opts):
        cwd = os.path.abspath(os.getcwd())
        os.chdir(os.path.join(self.SRC, '..', 'manual'))
        try:
            for d in ('.build', 'cli'):
                if os.path.exists(d):
                    shutil.rmtree(d)
                os.makedirs(d)
            if not os.path.exists('.build'+os.sep+'html'):
                os.makedirs('.build'+os.sep+'html')
            os.environ['__appname__'] = __appname__
            os.environ['__version__'] = __version__
            subprocess.check_call(['sphinx-build', '-b', 'html', '-t', 'online',
                                   '-d', '.build/doctrees', '.', '.build/html'])
            subprocess.check_call(['sphinx-build', '-b', 'myepub', '-d',
                                   '.build/doctrees', '.', '.build/epub'])
            epub_dest = self.j('.build', 'html', 'calibre.epub')
            shutil.copyfile(self.j('.build', 'epub', 'calibre.epub'), epub_dest)
            subprocess.check_call(['ebook-convert', epub_dest,
                epub_dest.rpartition('.')[0] + '.azw3',
                '--page-breaks-before=/', '--disable-font-rescaling',
                '--chapter=/'])
        finally:
            os.chdir(cwd)

    def clean(self):
        path = os.path.join(self.SRC, 'calibre', 'manual', '.build')
        if os.path.exists(path):
            shutil.rmtree(path)

class TagRelease(Command):

    description = 'Tag a new release in bzr'

    def run(self, opts):
        self.info('Tagging release')
        subprocess.check_call(('bzr tag '+__version__).split())
        subprocess.check_call('bzr commit --unchanged -m'.split() + ['IGN:Tag release'])


