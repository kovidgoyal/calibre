#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess

from setup import Command, __appname__
from setup.installer import VMInstaller
from setup.installer.windows import build_installer

class Win(Command):

    sub_commands = ['win32']

    def run(self, opts):
        pass


class Win32(VMInstaller):

    INSTALLER_EXT = 'exe'
    VM_NAME = 'xp_build'
    VM = '/vmware/bin/%s'%VM_NAME
    FREEZE_COMMAND = 'win32_freeze'

    def download_installer(self):
        installer = self.installer()
        if os.path.exists('build/py2exe'):
            shutil.rmtree('build/py2exe')
        subprocess.check_call(('scp', '-rp', 'xp_build:build/%s/build/py2exe'%__appname__,
                     'build'))
        if not os.path.exists('build/py2exe'):
            self.warn('Failed to run py2exe')
            raise SystemExit(1)
        self.run_windows_install_jammer(installer)

    def run_windows_install_jammer(self, installer):
        build_installer.run_install_jammer(
                                    installer_name=os.path.basename(installer))
        if not os.path.exists(installer):
            self.warn('Failed to run installjammer')
            raise SystemExit(1)


