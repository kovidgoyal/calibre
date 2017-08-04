#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__ = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess, glob, tempfile, json, time, filecmp, atexit, sys

from setup import Command, __version__, require_clean_git, require_git_master
from setup.upload import installers
from setup.parallel_build import parallel_build


class Stage1(Command):

    description = 'Stage 1 of the publish process'

    sub_commands = [
        'check',
        'test',
        'cacerts',
        'pot',
        'build',
        'resources',
        'translations',
        'iso639',
        'iso3166',
        'gui',
    ]


class Stage2(Command):

    description = 'Stage 2 of the publish process, builds the binaries'

    def run(self, opts):
        from setup.multitail import pipe, multitail
        for x in glob.glob(os.path.join(self.d(self.SRC), 'dist', '*')):
            os.remove(x)
        build = os.path.join(self.d(self.SRC), 'build')
        if os.path.exists(build):
            shutil.rmtree(build)
        processes = []
        tdir = tempfile.mkdtemp('_build_logs')
        atexit.register(shutil.rmtree, tdir)
        self.info('Starting builds for all platforms, this will take a while...')

        def kill_child_on_parent_death():
            import ctypes, signal
            libc = ctypes.CDLL("libc.so.6")
            libc.prctl(1, signal.SIGTERM)

        for x in ('linux', 'osx', 'win'):
            r, w = pipe()
            p = subprocess.Popen([sys.executable, 'setup.py', x],
                                 stdout=w,
                                 stderr=subprocess.STDOUT,
                                 cwd=self.d(self.SRC),
                                 preexec_fn=kill_child_on_parent_death)
            p.log, p.start_time, p.bname = r, time.time(), x
            p.save = open(os.path.join(tdir, x), 'w+b')
            p.duration = None
            processes.append(p)

        def workers_running():
            running = False
            for p in processes:
                rc = p.poll()
                if rc is not None:
                    if p.duration is None:
                        p.duration = int(time.time() - p.start_time)
                else:
                    running = True
            return running

        stop_multitail = multitail([proc.log for proc in processes],
                                   name_map={
                                       proc.log: proc.bname
                                       for proc in processes
                                   },
                                   copy_to=[proc.save for proc in processes])[0]

        while workers_running():
            os.waitpid(-1, 0)

        stop_multitail()

        failed = False
        for p in processes:
            if p.poll() != 0:
                failed = True
                log = p.save
                log.flush()
                log.seek(0)
                raw = log.read()
                self.info('Building of %s failed' % p.bname)
                sys.stderr.write(raw)
                sys.stderr.write(b'\n\n')
        if failed:
            raise SystemExit('Building of installers failed!')

        for p in sorted(processes, key=lambda p: p.duration):
            self.info(
                'Built %s in %d minutes and %d seconds' %
                (p.bname, p.duration // 60, p.duration % 60)
            )

        for installer in installers(include_source=False):
            if not os.path.exists(self.j(self.d(self.SRC), installer)):
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
            subprocess.check_call([sys.executable, 'setup.py', 'build'])
            os.environ['PUBLISH_BUILD_DONE'] = '1'
            os.execl(os.path.abspath('setup.py'), './setup.py', 'publish')


class PublishBetas(Command):

    sub_commands = ['rapydscript', 'stage2', 'sdist']

    def pre_sub_commands(self, opts):
        require_clean_git()
        require_git_master()

    def run(self, opts):
        dist = self.a(self.j(self.d(self.SRC), 'dist'))
        subprocess.check_call((
            'rsync --partial -rh --progress --delete-after %s/ download.calibre-ebook.com:/srv/download/betas/'
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
            jobs.append(([
                sys.executable, self.j(self.d(self.SRC), 'manual', 'build.py'),
                language, self.j(tdir, language)
            ], '\n\n**************** Building translations for: %s' % language))
        self.info('Building manual for %d languages' % len(jobs))
        subprocess.check_call(jobs[0][0])
        if not parallel_build(jobs[1:], self.info):
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
        import BaseHTTPServer
        from SimpleHTTPServer import SimpleHTTPRequestHandler
        HandlerClass = SimpleHTTPRequestHandler
        ServerClass = BaseHTTPServer.HTTPServer
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
            except EnvironmentError:
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
        except EnvironmentError:
            pass
        jobs = []
        for l in languages:
            jobs.append((
                [sys.executable, self.j(base, 'build.py'), '--man-pages', l, dest],
                '\n\n**************** Building translations for: %s' % l)
            )
        self.info('\tCreating man pages in {} for {} languages...'.format(dest, len(jobs)))
        subprocess.check_call(jobs[0][0])
        if not parallel_build(jobs[1:], self.info, verbose=False):
            raise SystemExit(1)
        cwd = os.getcwdu()
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
                            jobs.append((['gzip', '--best', self.j(dirpath, f)], ''))
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
        subprocess.check_call('git push origin v{0}'.format(__version__).split())
