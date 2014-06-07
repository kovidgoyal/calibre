#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from setup.installer import VMInstaller

class OSX(VMInstaller):

    description = 'Build OS X binary installer'

    INSTALLER_EXT = 'dmg'
    VM_NAME = 'osx-build'
    FREEZE_TEMPLATE = 'python -OO setup.py {freeze_command}'
    FREEZE_COMMAND = 'osx32_freeze'
    FORCE_SHUTDOWN = 10  # number of seconds to wait before doing a forced power off
