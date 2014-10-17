#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess, glob, tempfile, json, time, filecmp

from setup import Command, __version__, require_clean_git, require_git_master
from setup.parallel_build import parallel_build

class Stage1(Command):

    description = 'Stage 1 of the publish process'

    sub_commands = [
            'check',
            'pot',
            'build',
            'resources',
            'translations',
            'iso639',
            'iso3166',
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

class PublishBetas(Command):

    sub_commands = ['stage2', 'sdist']

    def pre_sub_commands(self, opts):
        require_clean_git()

    def run(self, opts):
        dist = self.a(self.j(self.d(self.SRC), 'dist'))
        subprocess.check_call(
            ('rsync --partial -rh --progress --delete-after %s/ download.calibre-ebook.com:/srv/download/betas/' % dist).split())

class Manual(Command):

    description='''Build the User Manual '''

    def add_options(self, parser):
        parser.add_option('-l', '--language', action='append', default=[],
                          help='Build translated versions for only the specified languages (can be specified multiple times)')

    def run(self, opts):
        tdir = self.j(tempfile.gettempdir(), 'user-manual-build')
        if os.path.exists(tdir):
            shutil.rmtree(tdir)
        os.mkdir(tdir)
        st = time.time()
        base = self.j(self.d(self.SRC), 'manual')
        for d in ('generated', ):
            d = self.j(base, d)
            if os.path.exists(d):
                shutil.rmtree(d)
            os.makedirs(d)
        jobs = []
        languages = opts.language or list(json.load(open(self.j(base, 'locale', 'completed.json'), 'rb')))
        languages = ['en'] + list(set(languages) - {'en'})
        os.environ['ALL_USER_MANUAL_LANGUAGES'] = ' '.join(languages)
        for language in languages:
            jobs.append((['calibre-debug', self.j(self.d(self.SRC), 'manual', 'build.py'), '--',
                          language, self.j(tdir, language)],
                         '\n\n**************** Building translations for: %s'%language))
        self.info('Building manual for %d languages' % len(jobs))
        if not parallel_build(jobs, self.info):
            raise SystemExit(1)
        cwd = os.getcwdu()
        try:
            os.chdir(self.j(tdir, 'en', 'html'))
            for x in os.listdir(tdir):
                if x != 'en':
                    shutil.copytree(self.j(tdir, x, 'html'), x)
                    self.replace_with_symlinks(x)
                else:
                    os.symlink('..', 'en')
            self.info('Built manual for %d languages in %s minutes' % (len(jobs), int((time.time() - st)/60.)))
        finally:
            os.chdir(cwd)

    def replace_with_symlinks(self, lang_dir):
        ' Replace all identical files with symlinks to save disk space/upload bandwidth '
        from calibre import walk
        base = self.a(lang_dir)
        for f in walk(base):
            r = os.path.relpath(f, base)
            orig = self.j(self.d(base), r)
            try:
                sz = os.stat(orig).st_size
            except EnvironmentError:
                continue
            if sz == os.stat(f).st_size and filecmp._do_cmp(f, orig):
                os.remove(f)
                os.symlink(os.path.relpath(orig, self.d(f)), f)

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

