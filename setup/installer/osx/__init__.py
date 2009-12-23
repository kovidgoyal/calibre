#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from setup import Command
from setup.installer import VMInstaller

class OSX(Command):

    description = 'Build OS X binary installers'

    sub_commands = ['osx32']

    def run(self, opts):
        pass


class OSX32(VMInstaller):

    description = 'Build 32 bit OS X binary installer'

    INSTALLER_EXT = 'dmg'
    VM_NAME = 'leopard_build'
    VM = '/vmware/bin/%s'%VM_NAME
    FREEZE_TEMPLATE = 'python -OO setup.py {freeze_command}'
    FREEZE_COMMAND = 'osx32_freeze'
    BUILD_PREFIX = VMInstaller.BUILD_PREFIX + ['source ~/.profile']
    SHUTDOWN_CMD = ['sudo', 'halt']
