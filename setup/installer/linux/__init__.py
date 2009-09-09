#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from setup.installer import VMInstaller
from setup import Command, installer_name

class Linux32(VMInstaller):

    INSTALLER_EXT = 'tar.bz2'
    VM_NAME = 'gentoo32_build'
    VM = '/vmware/bin/gentoo32_build'
    FREEZE_COMMAND = 'linux_freeze'


class Linux64(Command):

    sub_commands = ['linux_freeze']

    def run(self, opts):
        installer = installer_name('tar.bz2', True)
        if not os.path.exists(installer):
            raise Exception('Failed to build installer '+installer)
        return os.path.basename(installer)

class Linux(Command):

    sub_commands = ['linux64', 'linux32']
