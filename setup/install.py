#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, textwrap

from setup import Command, islinux, basenames, modules, functions

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

    description = 'Setup a development environment'
    MODE = 0755

    sub_commands = ['build']

    def add_options(self, parser):
        parser.set_usage(textwrap.dedent('''\
                ***

                Setup a development environment for calibre.
                This allows you to run calibre directly from the source tree.
                Binaries will be installed in <prefix>/bin where <prefix> is
                the prefix of your python installation. This can be controlled
                via the --prefix option.
                '''))
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
        self.success()

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

