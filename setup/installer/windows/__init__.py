#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess

from setup import Command, __appname__, __version__
from setup.installer import VMInstaller

class Win(Command):

    description = 'Build windows binary installers'

    sub_commands = ['win32']

    def run(self, opts):
        pass

class WinBase(VMInstaller):
    FREEZE_COMMAND = 'win32_freeze'
    FREEZE_TEMPLATE = 'python -OO setup.py {freeze_command} --no-ice'
    INSTALLER_EXT = 'msi'
    SHUTDOWN_CMD = ['shutdown.exe', '-s', '-f', '-t', '0']


class Win32(WinBase):

    description = 'Build 32bit windows binary installer'

    VM_NAME = 'xp_build'
    VM = '/vmware/bin/%s'%VM_NAME
    VM_CHECK = 'calibre_windows_xp_home'

    def sign_msi(self):
        print ('Signing installers ...')
        subprocess.check_call(['ssh', self.VM_NAME, '~/sign.sh'], shell=False)

    def download_installer(self):
        installer = self.installer()
        if os.path.exists('build/winfrozen'):
            shutil.rmtree('build/winfrozen')
        self.sign_msi()

        subprocess.check_call(('scp',
            'xp_build:build/%s/%s'%(__appname__, installer), 'dist'))
        if not os.path.exists(installer):
            self.warn('Failed to freeze')
            raise SystemExit(1)

        installer = 'dist/%s-portable-installer-%s.exe'%(__appname__, __version__)
        subprocess.check_call(('scp',
            'xp_build:build/%s/%s'%(__appname__, installer), 'dist'))
        if not os.path.exists(installer):
            self.warn('Failed to get portable installer')
            raise SystemExit(1)

class Win64(WinBase):

    description = 'Build 64bit windows binary installer'

    VM_NAME = 'win64'
    VM = '/vmware/bin/%s'%VM_NAME
    VM_CHECK = 'win64'
    IS_64_BIT = True
    BUILD_PREFIX = WinBase.BUILD_PREFIX + [
        'if [ -f "$HOME/.bash_profile" ] ; then',
        '    source "$HOME/.bash_profile"',
        'fi',
    ]



