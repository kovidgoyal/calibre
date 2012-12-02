#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess

from setup import Command, __appname__, __version__, installer_name
from setup.installer import VMInstaller

class Win(Command):

    description = 'Build windows binary installers'

    sub_commands = ['win64', 'win32']

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

    @property
    def msi64(self):
        return installer_name('msi', is64bit=True)

    def sign_msi(self):
        import xattr
        print ('Signing installers ...')
        sign64 = False
        msi64 = self.msi64
        if os.path.exists(msi64) and 'user.signed' not in xattr.list(msi64):
            subprocess.check_call(['scp', msi64, self.VM_NAME +
                    ':build/%s/%s'%(__appname__, msi64)])
            sign64 = True
        subprocess.check_call(['ssh', self.VM_NAME, '~/sign.sh'], shell=False)
        return sign64

    def do_dl(self, installer, errmsg):
        subprocess.check_call(('scp',
            '%s:build/%s/%s'%(self.VM_NAME, __appname__, installer), 'dist'))
        if not os.path.exists(installer):
            self.warn(errmsg)
            raise SystemExit(1)

    def download_installer(self):
        installer = self.installer()
        if os.path.exists('build/winfrozen'):
            shutil.rmtree('build/winfrozen')
        sign64 = self.sign_msi()
        if sign64:
            self.do_dl(self.msi64, 'Failed to d/l signed 64 bit installer')
            import xattr
            xattr.set(self.msi64, 'user.signed', 'true')

        self.do_dl(installer, 'Failed to freeze')

        installer = 'dist/%s-portable-installer-%s.exe'%(__appname__, __version__)
        self.do_dl(installer, 'Failed to get portable installer')

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



