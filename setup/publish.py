#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess, glob

from setup import Command, __appname__, __version__, require_clean_git, require_git_master


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

    def pre_sub_commands(self, opts):
        require_git_master()
        require_clean_git()

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
            subprocess.check_call(['sphinx-build', '-b', 'mylatex', '-d',
                                   '.build/doctrees', '.', '.build/latex'])
            pwd = os.getcwdu()
            os.chdir('.build/latex')
            subprocess.check_call(['make', 'all-pdf'], stdout=open(os.devnull,
                'wb'))
            os.chdir(pwd)
            epub_dest = self.j('.build', 'html', 'calibre.epub')
            pdf_dest = self.j('.build', 'html', 'calibre.pdf')
            shutil.copyfile(self.j('.build', 'epub', 'calibre.epub'), epub_dest)
            shutil.copyfile(self.j('.build', 'latex', 'calibre.pdf'), pdf_dest)
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

    description = 'Tag a new release in git'

    def run(self, opts):
        self.info('Tagging release')
        subprocess.check_call('git tag -a v{0} -m "version-{0}"'.format(__version__).split())
        subprocess.check_call('git push origin v{0}'.format(__version__).split())

