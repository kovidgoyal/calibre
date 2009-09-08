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
        parser.add_option('--prefix',
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
        self.install_files(opts)
        self.run_postinstall()
        self.success()

    def install_files(self, opts):
        pass

    def run_postinstall(self):
        subprocess.check_call(['calibre_postinstall'])

    def success(self):
        self.info('\nDevelopment environment successfully setup')

    def find_locations(self, opts):
        self.path = self.SRC
        self.resources = self.j(self.d(self.SRC), 'resources')
        self.extensions = self.j(self.SRC, 'calibre', 'plugins')

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
        prefix = opts.prefix
        if prefix is None:
            prefix = sys.prefix
        path = self.j(prefix, 'bin', name)
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

    sub_commands = ['build']

    def add_options(self, parser):
        parser.add_option('--prefix', help='Installation prefix')
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
        self.info('\tCreating tarfile...')
        subprocess.check_call(' '.join(['tar', '-czf', self.a(self.DEST), '*']),
                cwd=tdir, shell=True)

    def clean(self):
        if os.path.exists(self.DEST):
            os.remove(self.DEST)



