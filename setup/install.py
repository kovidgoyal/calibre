#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, textwrap, subprocess, shutil, tempfile, atexit

from setup import Command, islinux, basenames, modules, functions, \
        __appname__, __version__

TEMPLATE = '''\
#!/usr/bin/env python

"""
This is the standard runscript for all of calibre's tools.
Do not modify it unless you know what you are doing.
"""

import sys
sys.path.insert(0, {path!r})

sys.resources_location = {resources!r}
sys.extensions_location = {extensions!r}

from {module} import {func!s}
sys.exit({func!s}())
'''

class Develop(Command):

    description = textwrap.dedent('''\
            Setup a development environment for calibre.
            This allows you to run calibre directly from the source tree.
            Binaries will be installed in <prefix>/bin where <prefix> is
            the prefix of your python installation. This can be controlled
            via the --prefix option.
            ''')
    MODE = 0755

    sub_commands = ['build', 'resources', 'gui']

    def add_options(self, parser):
        parser.add_option('--prefix', '--root',
            help='Binaries will be installed in <prefix>/bin')

    def pre_sub_commands(self, opts):
        if not islinux:
            self.info('\nSetting up a development environment is only '
                    'supported on linux. On other platforms, install the calibre '
                    'binary and use the calibre-debug command.')
            raise SystemExit(1)

        if not os.geteuid() == 0:
            self.info('\nError: This command must be run as root.')
            raise SystemExit(1)
        self.drop_privileges()

    def run(self, opts):
        self.regain_privileges()
        self.find_locations(opts)
        self.write_templates(opts)
        self.setup_mount_helper()
        self.install_files(opts)
        self.run_postinstall()
        self.success()

    def setup_mount_helper(self):
        def warn():
            self.warn('Failed to compile mount helper. Auto mounting of',
                'devices will not work')

        if os.geteuid() != 0:
            return warn()
        import stat
        src = os.path.join(self.SRC, 'calibre', 'devices', 'linux_mount_helper.c')
        dest = os.path.join(self.bindir, 'calibre-mount-helper')
        self.info('Installing mount helper to '+ dest)
        p = subprocess.Popen(['gcc', '-Wall', src, '-o', dest])
        ret = p.wait()
        if ret != 0:
            return warn()
        os.chown(dest, 0, 0)
        os.chmod(dest,
        stat.S_ISUID|stat.S_ISGID|stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH)
        return dest

    def install_files(self, opts):
        pass

    def run_postinstall(self):
        env = dict(**os.environ)
        env['DESTDIR'] = self.prefix
        subprocess.check_call(['calibre_postinstall', '--use-destdir'], env=env)

    def success(self):
        self.info('\nDevelopment environment successfully setup')

    def find_locations(self, opts):
        self.prefix = opts.prefix
        if self.prefix is None:
            self.prefix = sys.prefix
        self.path = self.SRC
        self.resources = self.j(self.d(self.SRC), 'resources')
        self.extensions = self.j(self.SRC, 'calibre', 'plugins')
        self.bindir = self.j(self.prefix, 'bin')

    def write_templates(self, opts):
        for typ in ('console', 'gui'):
            for name, mod, func in zip(basenames[typ], modules[typ],
                    functions[typ]):
                self.write_template(opts, name, mod, func)
        if islinux:
            self.write_template(opts, 'calibre_postinstall', 'calibre.linux', 'main')

    def write_template(self, opts, name, mod, func):
        script = TEMPLATE.format(
                module=mod, func=func,
                path=self.path, resources=self.resources,
                extensions=self.extensions)
        path = self.j(self.bindir, name)
        if not os.path.exists(self.bindir):
            os.makedirs(self.bindir)
        self.info('Installing binary:', path)
        open(path, 'wb').write(script)
        os.chmod(path, self.MODE)


class Install(Develop):

    description = textwrap.dedent('''\
            Install calibre to your system. By default, calibre
            is installed to <prefix>/bin, <prefix>/lib/calibre,
            <prefix>/share/calibre. These can all be controlled via options.

            The default <prefix> is the prefix of your python installation.
    ''')

    sub_commands = ['build', 'gui']

    def add_options(self, parser):
        parser.add_option('--prefix', '--root', help='Installation prefix')
        parser.add_option('--libdir', help='Where to put calibre library files')
        parser.add_option('--bindir', help='Where to install calibre binaries')
        parser.add_option('--sharedir', help='Where to install calibre data files')

    def find_locations(self, opts):
        if opts.prefix is None:
            opts.prefix = sys.prefix
        if opts.libdir is None:
            opts.libdir = self.j(opts.prefix, 'lib', 'calibre')
        if opts.bindir is None:
            opts.bindir = self.j(opts.prefix, 'bin')
        if opts.sharedir is None:
            opts.sharedir = self.j(opts.prefix, 'share', 'calibre')
        self.prefix = opts.prefix
        self.bindir = opts.bindir
        self.path = opts.libdir
        self.resources = opts.sharedir
        self.extensions = self.j(self.path, 'calibre', 'plugins')

    def install_files(self, opts):
        dest = self.path
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(self.SRC, dest)
        dest = self.resources
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(self.RESOURCES, dest)

    def success(self):
        self.info('\n\ncalibre successfully installed. You can start'
                ' it by running the command calibre')

class Sdist(Command):

    description = 'Create a source distribution'
    DEST = os.path.join('dist', '%s-%s.tar.gz'%(__appname__, __version__))


    def run(self, opts):
        if not self.e(self.d(self.DEST)):
            os.makedirs(self.d(self.DEST))
        tdir = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, tdir)
        self.info('\tRunning bzr export...')
        subprocess.check_call(['bzr', 'export', '--format', 'dir', tdir])
        for x in open('.bzrignore').readlines():
            if not x.startswith('resources/'): continue
            p = x.strip().replace('/', os.sep)
            d = self.j(tdir, os.path.dirname(p))
            if not self.e(d):
                os.makedirs(d)
            if os.path.isdir(p):
                shutil.copytree(p, self.j(tdir, p))
            else:
                shutil.copy2(p, d)
        for x in os.walk(os.path.join(self.SRC, 'calibre')):
            for f in x[-1]:
                if not f.endswith('_ui.py'): continue
                f = os.path.join(x[0], f)
                f = os.path.relpath(f)
                dest = os.path.join(tdir, self.d(f))
                shutil.copy2(f, dest)

        self.info('\tCreating tarfile...')
        subprocess.check_call(' '.join(['tar', '-czf', self.a(self.DEST), '*']),
                cwd=tdir, shell=True)

    def clean(self):
        if os.path.exists(self.DEST):
            os.remove(self.DEST)



