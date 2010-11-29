#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from setup.installer import VMInstaller
from setup import Command

class Linux32(VMInstaller):

    description = 'Build 32bit linux binary installer'

    INSTALLER_EXT = 'tar.bz2'
    VM_NAME = 'gentoo32_build'
    VM = '/vmware/bin/gentoo32_build'
    FREEZE_COMMAND = 'linux_freeze'
    FREEZE_TEMPLATE = 'sudo python -OO setup.py {freeze_command}'


class Linux64(Linux32):

    description = 'Build 64bit linux binary installer'
    VM_NAME = 'gentoo64_build'
    VM = '/vmware/bin/gentoo64_build'
    IS_64_BIT = True

class Linux(Command):

    description = 'Build linux binary installers'

    sub_commands = ['linux64', 'linux32']
