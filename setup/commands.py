#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

__all__ = [
        'pot', 'translations', 'get_translations', 'iso639',
        'build',
        'gui',
        'develop', 'install',
        'resources',
        'check',
        'sdist',
        'manual', 'tag_release', 'upload_rss',
        'upload_user_manual', 'upload_installers', 'upload_demo',
        'linux32', 'linux64', 'linux', 'linux_freeze',
        'osx32_freeze', 'osx32', 'osx',
        'win32_freeze', 'win32', 'win',
        ]


from setup.translations import POT, GetTranslations, Translations, ISO639
pot = POT()
translations = Translations()
get_translations = GetTranslations()
iso639 = ISO639()

from setup.extensions import Build
build = Build()

from setup.install import Develop, Install, Sdist
develop = Develop()
install = Install()
sdist = Sdist()

from setup.gui import GUI
gui = GUI()

from setup.check import Check
check = Check()

from setup.resources import Resources
resources = Resources()

from setup.publish import Manual, TagRelease, UploadRss
manual = Manual()
tag_release = TagRelease()
upload_rss = UploadRss()

from setup.upload import UploadUserManual, UploadInstallers, UploadDemo
upload_user_manual = UploadUserManual()
upload_installers = UploadInstallers()
upload_demo = UploadDemo()

from setup.installer.linux import Linux, Linux32, Linux64
linux = Linux()
linux32 = Linux32()
linux64 = Linux64()
from setup.installer.linux.freeze import LinuxFreeze
linux_freeze = LinuxFreeze()

from setup.installer.osx import OSX, OSX32
osx = OSX()
osx32 = OSX32()
from setup.installer.osx.freeze import OSX32_Freeze
osx32_freeze = OSX32_Freeze()

from setup.installer.windows import Win, Win32
win = Win()
win32 = Win32()
from setup.installer.windows.freeze import Win32Freeze
win32_freeze = Win32Freeze()


commands = {}
for x in __all__:
    commands[x] = locals()[x]

command_names = dict(zip(commands.values(), commands.keys()))
