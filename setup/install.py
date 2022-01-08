#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid at kovidgoyal.net>


import atexit
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time

from setup import (
    Command, __appname__, __version__, basenames, functions,
    isbsd, ishaiku, islinux, modules
)

HEADER = '''\
#!/usr/bin/env python{py_major_version}

"""
This is the standard runscript for all of calibre's tools.
Do not modify it unless you know what you are doing.
"""

import sys, os

path = os.environ.get('CALIBRE_PYTHON_PATH', {path!r})
if path not in sys.path:
    sys.path.insert(0, path)

sys.resources_location = os.environ.get('CALIBRE_RESOURCES_PATH', {resources!r})
sys.extensions_location = os.environ.get('CALIBRE_EXTENSIONS_PATH', {extensions!r})
sys.executables_location = os.environ.get('CALIBRE_EXECUTABLES_PATH', {executables!r})
sys.system_plugins_location = {system_plugins_loc!r}

'''

TEMPLATE = HEADER+'''
from {module} import {func!s}
sys.exit({func!s}())
'''

COMPLETE_TEMPLATE = HEADER+'''
sys.path.insert(0, os.path.join(path, 'calibre', 'utils'))
import complete
sys.path = sys.path[1:]

sys.exit(complete.main())
'''


class Develop(Command):

    description = textwrap.dedent('''\
            Setup a development environment for calibre.
            This allows you to run calibre directly from the source tree.
            Binaries will be installed in <prefix>/bin where <prefix> is
            the prefix of your python installation. This can be controlled
            via the --prefix option.
            ''')
    short_description = 'Setup a development environment for calibre'
    MODE = 0o755

    sub_commands = ['build', 'resources', 'iso639', 'iso3166', 'gui',]

    def add_postinstall_options(self, parser):
        parser.add_option('--make-errors-fatal', action='store_true', default=False,
                      dest='fatal_errors', help='If set die on post install errors.')
        parser.add_option('--no-postinstall', action='store_false',
            dest='postinstall', default=True,
            help='Don\'t run post install actions like creating MAN pages, setting'+
                    ' up desktop integration and so on')

    def add_options(self, parser):
        parser.add_option('--prefix',
                help='Binaries will be installed in <prefix>/bin')
        parser.add_option('--system-plugins-location',
                help='Path to a directory from which the installed calibre will load plugins')
        self.add_postinstall_options(parser)

    def consolidate_paths(self):
        opts = self.opts
        if not opts.prefix:
            opts.prefix = sys.prefix
        for x in ('prefix', 'libdir', 'bindir', 'sharedir', 'staging_root',
                'staging_libdir', 'staging_bindir', 'staging_sharedir'):
            o = getattr(opts, x, None)
            if o:
                setattr(opts, x, os.path.abspath(o))
        self.libdir = getattr(opts, 'libdir', None)
        if self.libdir is None:
            self.libdir = self.j(opts.prefix, 'lib')
        self.bindir = getattr(opts, 'bindir', None)
        if self.bindir is None:
            self.bindir = self.j(opts.prefix, 'bin')
        self.sharedir = getattr(opts, 'sharedir', None)
        if self.sharedir is None:
            self.sharedir = self.j(opts.prefix, 'share')
        if not getattr(opts, 'staging_root', None):
            opts.staging_root = opts.prefix
        self.staging_libdir = getattr(opts, 'staging_libdir', None)
        if self.staging_libdir is None:
            self.staging_libdir = opts.staging_libdir = self.j(opts.staging_root, 'lib')
        self.staging_bindir = getattr(opts, 'staging_bindir', None)
        if self.staging_bindir is None:
            self.staging_bindir = opts.staging_bindir = self.j(opts.staging_root, 'bin')
        self.staging_sharedir = getattr(opts, 'staging_sharedir', None)
        if self.staging_sharedir is None:
            self.staging_sharedir = opts.staging_sharedir = self.j(opts.staging_root, 'share')

        self.staging_libdir = opts.staging_libdir = self.j(self.staging_libdir, 'calibre')
        self.staging_sharedir = opts.staging_sharedir = self.j(self.staging_sharedir, 'calibre')
        self.system_plugins_loc = opts.system_plugins_location

        if self.__class__.__name__ == 'Develop':
            self.libdir = self.SRC
            self.sharedir = self.RESOURCES
        else:
            self.libdir = self.j(self.libdir, 'calibre')
            self.sharedir = self.j(self.sharedir, 'calibre')
            self.info('INSTALL paths:')
            self.info('\tLIB:', self.staging_libdir)
            self.info('\tSHARE:', self.staging_sharedir)

    def pre_sub_commands(self, opts):
        if not (islinux or isbsd or ishaiku):
            self.info('\nSetting up a source based development environment is only '
                    'supported on linux. On other platforms, see the User Manual'
                    ' for help with setting up a development environment.')
            raise SystemExit(1)

        if os.geteuid() == 0:
            # We drop privileges for security, regaining them when installing
            # files. Also ensures that any config files created as a side
            # effect of the build process are not owned by root.
            self.drop_privileges()

        # Ensure any config files created as a side effect of importing calibre
        # during the build process are in /tmp
        os.environ['CALIBRE_CONFIG_DIRECTORY'] = os.environ.get('CALIBRE_CONFIG_DIRECTORY', '/tmp/calibre-install-config')

    def run(self, opts):
        self.manifest = []
        self.opts = opts
        self.regain_privileges()
        self.consolidate_paths()
        self.install_files()
        self.write_templates()
        self.install_env_module()
        self.run_postinstall()
        self.success()

    def install_env_module(self):
        import sysconfig
        libdir = os.path.join(
            self.opts.staging_root, sysconfig.get_config_var('PLATLIBDIR') or 'lib',
            os.path.basename(sysconfig.get_config_var('DESTLIB') or sysconfig.get_config_var('LIBDEST') or f'python{sysconfig.get_python_version()}'),
            'site-packages')
        try:
            if not os.path.exists(libdir):
                os.makedirs(libdir)
        except OSError:
            self.warn('Cannot install calibre environment module to: '+libdir)
        else:
            path = os.path.join(libdir, 'init_calibre.py')
            self.info('Installing calibre environment module: '+path)
            with open(path, 'wb') as f:
                f.write(HEADER.format(**self.template_args()).encode('utf-8'))
            self.manifest.append(path)

    def install_files(self):
        pass

    def run_postinstall(self):
        if self.opts.postinstall:
            from calibre.linux import PostInstall
            PostInstall(self.opts, info=self.info, warn=self.warn,
                    manifest=self.manifest)

    def success(self):
        self.info('\nDevelopment environment successfully setup')

    def write_templates(self):
        for typ in ('console', 'gui'):
            for name, mod, func in zip(basenames[typ], modules[typ],
                    functions[typ]):
                self.write_template(name, mod, func)

    def template_args(self):
        return {
            'py_major_version': sys.version_info.major,
            'path':self.libdir,
            'resources':self.sharedir,
            'executables':self.bindir,
            'extensions':self.j(self.libdir, 'calibre', 'plugins'),
            'system_plugins_loc': self.system_plugins_loc,
        }

    def write_template(self, name, mod, func):
        template = COMPLETE_TEMPLATE if name == 'calibre-complete' else TEMPLATE
        args = self.template_args()
        args['module'] = mod
        args['func'] = func
        script = template.format(**args)
        path = self.j(self.staging_bindir, name)
        if not os.path.exists(self.staging_bindir):
            os.makedirs(self.staging_bindir)
        self.info('Installing binary:', path)
        if os.path.lexists(path) and not os.path.exists(path):
            os.remove(path)
        with open(path, 'wb') as f:
            f.write(script.encode('utf-8'))
        os.chmod(path, self.MODE)
        self.manifest.append(path)


class Install(Develop):

    description = textwrap.dedent('''\
            Install calibre to your system. By default, calibre
            is installed to <prefix>/bin, <prefix>/lib/calibre,
            <prefix>/share/calibre. These can all be controlled via options.

            The default <prefix> is the prefix of your python installation.

            The .desktop, .mime and icon files are installed using XDG. The
            location they are installed to can be controlled by setting
            the environment variables:
            XDG_DATA_DIRS=/usr/share equivalent
            XDG_UTILS_INSTALL_MODE=system
            For staged installs this will be automatically set to:
            <staging_root>/share
    ''')
    short_description = 'Install calibre from source'

    sub_commands = ['build', 'gui']

    def add_options(self, parser):
        parser.add_option('--prefix', help='Installation prefix.')
        parser.add_option('--libdir',
            help='Where to put calibre library files. Default is <prefix>/lib')
        parser.add_option('--bindir',
            help='Where to put the calibre binaries. Default is <prefix>/bin')
        parser.add_option('--sharedir',
            help='Where to put the calibre data files. Default is <prefix>/share')
        parser.add_option('--staging-root', '--root', default=None,
                help=('Use a different installation root (mainly for packaging).'
                    ' The prefix option controls the paths written into '
                    'the launcher scripts. This option controls the prefix '
                    'to which the install will actually copy files. By default '
                    'it is set to the value of --prefix.'))
        parser.add_option('--staging-libdir',
            help='Where to put calibre library files. Default is <root>/lib')
        parser.add_option('--staging-bindir',
            help='Where to put the calibre binaries. Default is <root>/bin')
        parser.add_option('--staging-sharedir',
            help='Where to put the calibre data files. Default is <root>/share')
        parser.add_option('--system-plugins-location',
                help='Path to a directory from which the installed calibre will load plugins')
        self.add_postinstall_options(parser)

    def install_files(self):
        dest = self.staging_libdir
        if os.path.exists(dest):
            shutil.rmtree(dest)
        self.info('Installing code to', dest)
        self.manifest.append(dest)
        for x in os.walk(self.SRC):
            reldir = os.path.relpath(x[0], self.SRC)
            destdir = os.path.join(dest, reldir)
            for f in x[-1]:
                if os.path.splitext(f)[1] in ('.py', '.so'):
                    if not os.path.exists(destdir):
                        os.makedirs(destdir)
                    shutil.copy2(self.j(x[0], f), destdir)
        dest = self.staging_sharedir
        if os.path.exists(dest):
            shutil.rmtree(dest)
        self.info('Installing resources to', dest)
        shutil.copytree(self.RESOURCES, dest, symlinks=True)
        self.manifest.append(dest)

    def success(self):
        self.info('\n\ncalibre successfully installed. You can start'
                ' it by running the command calibre')


class Sdist(Command):

    description = 'Create a source distribution'
    DEST = os.path.join('dist', '%s-%s.tar.xz'%(__appname__, __version__))

    def run(self, opts):
        if not self.e(self.d(self.DEST)):
            os.makedirs(self.d(self.DEST))
        tdir = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, tdir)
        tdir = self.j(tdir, 'calibre-%s' % __version__)
        self.info('\tRunning git export...')
        os.mkdir(tdir)
        subprocess.check_call('git archive HEAD | tar -x -C ' + tdir, shell=True)
        for x in open('.gitignore').readlines():
            if not x.startswith('resources/'):
                continue
            p = x.strip().replace('/', os.sep)
            for p in glob.glob(p):
                d = self.j(tdir, os.path.dirname(p))
                if not self.e(d):
                    os.makedirs(d)
                if os.path.isdir(p):
                    shutil.copytree(p, self.j(tdir, p))
                else:
                    shutil.copy2(p, d)
        for x in os.walk(os.path.join(self.SRC, 'calibre')):
            for f in x[-1]:
                if not f.endswith('_ui.py'):
                    continue
                f = os.path.join(x[0], f)
                f = os.path.relpath(f)
                dest = os.path.join(tdir, self.d(f))
                shutil.copy2(f, dest)

        tbase = self.j(self.d(self.SRC), 'translations')
        for x in ('iso_639', 'calibre'):
            destdir = self.j(tdir, 'translations', x)
            if not os.path.exists(destdir):
                os.makedirs(destdir)
            for y in glob.glob(self.j(tbase, x, '*.po')) + glob.glob(self.j(tbase, x, '*.pot')):
                dest = self.j(destdir, self.b(y))
                if not os.path.exists(dest):
                    shutil.copy2(y, dest)
        shutil.copytree(self.j(tbase, 'manual'), self.j(tdir, 'translations', 'manual'))
        self.add_man_pages(self.j(tdir, 'man-pages'))

        self.info('\tCreating tarfile...')
        dest = self.DEST.rpartition('.')[0]
        shutil.rmtree(os.path.join(tdir, '.github'))
        subprocess.check_call(['tar', '-cf', self.a(dest), 'calibre-%s' % __version__], cwd=self.d(tdir))
        self.info('\tCompressing tarfile...')
        if os.path.exists(self.a(self.DEST)):
            os.remove(self.a(self.DEST))
        subprocess.check_call(['xz', '-9', self.a(dest)])

    def add_man_pages(self, dest):
        from setup.commands import man_pages
        man_pages.build_man_pages(dest)

    def clean(self):
        if os.path.exists(self.DEST):
            os.remove(self.DEST)


class Bootstrap(Command):

    description = 'Bootstrap a fresh checkout of calibre from git to a state where it can be installed. Requires various development tools/libraries/headers'
    TRANSLATIONS_REPO = 'kovidgoyal/calibre-translations'
    sub_commands = 'build iso639 iso3166 translations gui resources cacerts recent_uas'.split()

    def add_options(self, parser):
        parser.add_option('--ephemeral', default=False, action='store_true',
            help='Do not download all history for the translations. Speeds up first time download but subsequent downloads will be slower.')

    def pre_sub_commands(self, opts):
        tdir = self.j(self.d(self.SRC), 'translations')
        clone_cmd = [
            'git', 'clone', f'https://github.com/{self.TRANSLATIONS_REPO}.git', 'translations']
        if opts.ephemeral:
            if os.path.exists(tdir):
                shutil.rmtree(tdir)

            st = time.time()
            clone_cmd.insert(2, '--depth=1')
            subprocess.check_call(clone_cmd, cwd=self.d(self.SRC))
            print('Downloaded translations in %d seconds' % int(time.time() - st))
        else:
            if os.path.exists(tdir):
                subprocess.check_call(['git', 'pull'], cwd=tdir)
            else:
                subprocess.check_call(clone_cmd, cwd=self.d(self.SRC))

    def run(self, opts):
        self.info('\n\nAll done! You should now be able to run "%s setup.py install" to install calibre' % sys.executable)
