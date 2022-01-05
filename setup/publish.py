#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess, tempfile, json, time, filecmp, sys

from setup import Command, __version__, require_clean_git, require_git_master, installer_names
from setup.parallel_build import parallel_build, create_job


class Stage1(Command):

    description = 'Stage 1 of the publish process'

    sub_commands = [
        'cacerts',
        'resources',
        'iso639',
        'iso3166',
        'gui',
        'recent_uas',
    ]


class Stage2(Command):

    description = 'Stage 2 of the publish process, builds the binaries'

    def run(self, opts):
        base = os.path.join(self.d(self.SRC))
        for x in ('dist', 'build'):
            x = os.path.join(base, x)
            if os.path.exists(x):
                shutil.rmtree(x)
            os.mkdir(x)

        self.info('Starting builds for all platforms, this will take a while...')

        session = ['layout vertical']
        platforms = 'linux64', 'linuxarm64', 'osx', 'win'
        for x in platforms:
            cmd = (
                '''{exe} -c "import subprocess; subprocess.Popen(['{exe}', './setup.py', '{x}']).wait() != 0 and'''
                ''' input('Build of {x} failed, press Enter to exit');"'''
            ).format(exe=sys.executable, x=x)
            session.append('title ' + x)
            session.append('launch ' + cmd)

        p = subprocess.Popen([
            'kitty', '-o', 'enabled_layouts=vertical,stack', '-o', 'scrollback_lines=20000',
            '-o', 'close_on_child_death=y', '--session=-'
        ], stdin=subprocess.PIPE)

        p.communicate('\n'.join(session).encode('utf-8'))
        p.wait()

        for installer in installer_names(include_source=False):
            installer = self.j(self.d(self.SRC), installer)
            if not os.path.exists(installer) or os.path.getsize(installer) < 10000:
                raise SystemExit(
                    'The installer %s does not exist' % os.path.basename(installer)
                )


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
    sub_commands = [
        'stage1',
        'stage2',
        'stage3',
        'stage4',
        'stage5',
    ]

    def pre_sub_commands(self, opts):
        require_git_master()
        require_clean_git()
        if 'PUBLISH_BUILD_DONE' not in os.environ:
            subprocess.check_call([sys.executable, 'setup.py', 'check'])
            subprocess.check_call([sys.executable, 'setup.py', 'build'])
            subprocess.check_call([sys.executable, 'setup.py', 'test'])
            subprocess.check_call([sys.executable, 'setup.py', 'pot'])
            subprocess.check_call([sys.executable, 'setup.py', 'translations'])
            os.environ['PUBLISH_BUILD_DONE'] = '1'
            os.execl(os.path.abspath('setup.py'), './setup.py', 'publish')


class PublishBetas(Command):

    sub_commands = ['stage1', 'stage2', 'sdist']

    def pre_sub_commands(self, opts):
        require_clean_git()
        # require_git_master()

    def run(self, opts):
        dist = self.a(self.j(self.d(self.SRC), 'dist'))
        subprocess.check_call((
            'rsync --partial -rh --info=progress2 --delete-after %s/ download.calibre-ebook.com:/srv/download/betas/'
            % dist
        ).split())


class Manual(Command):

    description = '''Build the User Manual '''

    def add_options(self, parser):
        parser.add_option(
            '-l',
            '--language',
            action='append',
            default=[],
            help=(
                'Build translated versions for only the specified languages (can be specified multiple times)'
            )
        )
        parser.add_option(
            '--serve',
            action='store_true',
            default=False,
            help='Run a webserver on the built manual files'
        )

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
        languages = opts.language or list(
            json.load(open(self.j(base, 'locale', 'completed.json'), 'rb'))
        )
        languages = ['en'] + list(set(languages) - {'en'})
        os.environ['ALL_USER_MANUAL_LANGUAGES'] = ' '.join(languages)
        for language in languages:
            jobs.append(create_job([
                sys.executable, self.j(self.d(self.SRC), 'manual', 'build.py'),
                language, self.j(tdir, language)
            ], '\n\n**************** Building translations for: %s' % language))
        self.info('Building manual for %d languages' % len(jobs))
        subprocess.check_call(jobs[0].cmd)
        if not parallel_build(jobs[1:], self.info):
            raise SystemExit(1)
        cwd = os.getcwd()
        with open('resources/localization/website-languages.txt') as wl:
            languages = frozenset(filter(None, (x.strip() for x in wl.read().split())))
        try:
            os.chdir(self.j(tdir, 'en', 'html'))
            for x in os.listdir(tdir):
                if x != 'en':
                    shutil.copytree(self.j(tdir, x, 'html'), x)
                    self.replace_with_symlinks(x)
                else:
                    os.symlink('.', 'en')
            for x in languages:
                if x and not os.path.exists(x):
                    os.symlink('.', x)
            self.info(
                'Built manual for %d languages in %s minutes' %
                (len(jobs), int((time.time() - st) / 60.))
            )
        finally:
            os.chdir(cwd)

        if opts.serve:
            self.serve_manual(self.j(tdir, 'en', 'html'))

    def serve_manual(self, root):
        os.chdir(root)
        from polyglot.http_server import HTTPServer, SimpleHTTPRequestHandler
        HandlerClass = SimpleHTTPRequestHandler
        ServerClass = HTTPServer
        Protocol = "HTTP/1.0"
        server_address = ('127.0.0.1', 8000)

        HandlerClass.protocol_version = Protocol
        httpd = ServerClass(server_address, HandlerClass)

        print("Serving User Manual on localhost:8000")
        from calibre.gui2 import open_url
        open_url('http://localhost:8000')
        httpd.serve_forever()

    def replace_with_symlinks(self, lang_dir):
        ' Replace all identical files with symlinks to save disk space/upload bandwidth '
        from calibre import walk
        base = self.a(lang_dir)
        for f in walk(base):
            r = os.path.relpath(f, base)
            orig = self.j(self.d(base), r)
            try:
                sz = os.stat(orig).st_size
            except OSError:
                continue
            if sz == os.stat(f).st_size and filecmp._do_cmp(f, orig):
                os.remove(f)
                os.symlink(os.path.relpath(orig, self.d(f)), f)

    def clean(self):
        path = os.path.join(self.SRC, 'calibre', 'manual', '.build')
        if os.path.exists(path):
            shutil.rmtree(path)


class ManPages(Command):

    description = '''Build the man pages '''

    def add_options(self, parser):
        parser.add_option('--man-dir', help='Where to generate the man pages')
        parser.add_option('--compress-man-pages', default=False, action='store_true', help='Compress the generated man pages')

    def run(self, opts):
        self.build_man_pages(opts.man_dir or 'man-pages', opts.compress_man_pages)

    def build_man_pages(self, dest, compress=False):
        from calibre.utils.localization import available_translations
        dest = os.path.abspath(dest)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        os.makedirs(dest)
        base = self.j(self.d(self.SRC), 'manual')
        languages = list(available_translations())
        languages = ['en'] + list(set(languages) - {'en', 'en_GB'})
        os.environ['ALL_USER_MANUAL_LANGUAGES'] = ' '.join(languages)
        try:
            os.makedirs(dest)
        except OSError:
            pass
        jobs = []
        for l in languages:
            jobs.append(create_job(
                [sys.executable, self.j(base, 'build.py'), '--man-pages', l, dest],
                '\n\n**************** Building translations for: %s' % l)
            )
        self.info(f'\tCreating man pages in {dest} for {len(jobs)} languages...')
        subprocess.check_call(jobs[0].cmd)
        if not parallel_build(jobs[1:], self.info, verbose=False):
            raise SystemExit(1)
        cwd = os.getcwd()
        os.chdir(dest)
        try:
            for x in tuple(os.listdir('.')):
                if x in languages:
                    if x == 'en':
                        os.rename(x, 'man1')
                    else:
                        os.mkdir(self.j(x, 'man1'))
                        for y in os.listdir(x):
                            if y != 'man1':
                                os.rename(self.j(x, y), self.j(x, 'man1', y))
                else:
                    shutil.rmtree(x) if os.path.isdir(x) else os.remove(x)
            if compress:
                jobs = []
                for dirpath, dirnames, filenames in os.walk('.'):
                    for f in filenames:
                        if f.endswith('.1'):
                            jobs.append(create_job(['gzip', '--best', self.j(dirpath, f)], ''))
                if not parallel_build(jobs, self.info, verbose=False):
                    raise SystemExit(1)
        finally:
            os.chdir(cwd)


class TagRelease(Command):

    description = 'Tag a new release in git'

    def run(self, opts):
        self.info('Tagging release')
        subprocess.check_call(
            'git tag -s v{0} -m "version-{0}"'.format(__version__).split()
        )
        subprocess.check_call(f'git push origin v{__version__}'.split())
