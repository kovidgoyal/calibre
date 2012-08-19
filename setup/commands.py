#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

__all__ = [
        'pot', 'translations', 'get_translations', 'iso639',
        'build', 'server', 'mathjax',
        'gui',
        'develop', 'install',
        'kakasi', 'coffee', 'resources',
        'check',
        'sdist',
        'manual', 'tag_release',
        'pypi_register', 'pypi_upload', 'upload_to_server',
        'upload_installers',
        'upload_user_manual', 'upload_demo', 'reupload',
        'linux32', 'linux64', 'linux', 'linux_freeze',
        'osx32_freeze', 'osx', 'rsync', 'push',
        'win32_freeze', 'win32', 'win',
        'stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'publish'
        ]


from setup.translations import POT, GetTranslations, Translations, ISO639
pot = POT()
translations = Translations()
get_translations = GetTranslations()
iso639 = ISO639()

from setup.extensions import Build
build = Build()

from setup.server import Server
server = Server()

from setup.mathjax import MathJax
mathjax = MathJax()

from setup.install import Develop, Install, Sdist
develop = Develop()
install = Install()
sdist = Sdist()

from setup.gui import GUI
gui = GUI()

from setup.check import Check
check = Check()

from setup.resources import Resources, Kakasi, Coffee
resources = Resources()
kakasi = Kakasi()
coffee = Coffee()

from setup.publish import Manual, TagRelease, Stage1, Stage2, \
        Stage3, Stage4, Stage5, Publish
manual = Manual()
tag_release = TagRelease()
stage1 = Stage1()
stage2 = Stage2()
stage3 = Stage3()
stage4 = Stage4()
stage5 = Stage5()
publish = Publish()

from setup.upload import (UploadUserManual, UploadDemo, UploadInstallers,
        UploadToServer, ReUpload)
upload_user_manual = UploadUserManual()
upload_demo = UploadDemo()
upload_to_server = UploadToServer()
upload_installers = UploadInstallers()
reupload = ReUpload()

from setup.installer import Rsync, Push
rsync = Rsync()
push = Push()

from setup.installer.linux import Linux, Linux32, Linux64
linux = Linux()
linux32 = Linux32()
linux64 = Linux64()
from setup.installer.linux.freeze2 import LinuxFreeze
linux_freeze = LinuxFreeze()

from setup.installer.osx import OSX
osx = OSX()
from setup.installer.osx.app.main import OSX32_Freeze
osx32_freeze = OSX32_Freeze()

from setup.installer.windows import Win, Win32
win = Win()
win32 = Win32()
from setup.installer.windows.freeze import Win32Freeze
win32_freeze = Win32Freeze()

from setup.pypi import PyPIRegister, PyPIUpload
pypi_register = PyPIRegister()
pypi_upload   = PyPIUpload()


commands = {}
for x in __all__:
    commands[x] = locals()[x]

command_names = dict(zip(commands.values(), commands.keys()))
