#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

__all__ = [
        'pot', 'translations', 'get_translations', 'iso639', 'iso3166',
        'build', 'mathjax',
        'gui',
        'develop', 'install',
        'kakasi', 'coffee', 'rapydscript', 'cacerts', 'recent_uas', 'resources',
        'check', 'test',
        'sdist', 'bootstrap',
        'manual', 'tag_release',
        'pypi_register', 'pypi_upload', 'upload_to_server',
        'upload_installers',
        'upload_user_manual', 'upload_demo', 'reupload',
        'stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'publish', 'publish_betas',
        'linux', 'linux32', 'linux64', 'win', 'win32', 'win64', 'osx',
        ]

from setup.installers import Linux, Win, OSX, Linux32, Linux64, Win32, Win64
linux, linux32, linux64 = Linux(), Linux32(), Linux64()
win, win32, win64 = Win(), Win32(), Win64()
osx = OSX()

from setup.translations import POT, GetTranslations, Translations, ISO639, ISO3166
pot = POT()
translations = Translations()
get_translations = GetTranslations()
iso639 = ISO639()
iso3166 = ISO3166()

from setup.build import Build
build = Build()

from setup.mathjax import MathJax
mathjax = MathJax()

from setup.install import Develop, Install, Sdist, Bootstrap
develop = Develop()
install = Install()
sdist = Sdist()
bootstrap = Bootstrap()

from setup.gui import GUI
gui = GUI()

from setup.check import Check
check = Check()

from setup.test import Test
test = Test()

from setup.resources import Resources, Kakasi, Coffee, CACerts, RapydScript, RecentUAs
resources = Resources()
kakasi = Kakasi()
coffee = Coffee()
cacerts = CACerts()
recent_uas = RecentUAs()
rapydscript = RapydScript()

from setup.publish import Manual, TagRelease, Stage1, Stage2, \
        Stage3, Stage4, Stage5, Publish, PublishBetas
manual = Manual()
tag_release = TagRelease()
stage1 = Stage1()
stage2 = Stage2()
stage3 = Stage3()
stage4 = Stage4()
stage5 = Stage5()
publish = Publish()
publish_betas = PublishBetas()

from setup.upload import (UploadUserManual, UploadDemo, UploadInstallers,
        UploadToServer, ReUpload)
upload_user_manual = UploadUserManual()
upload_demo = UploadDemo()
upload_to_server = UploadToServer()
upload_installers = UploadInstallers()
reupload = ReUpload()

from setup.pypi import PyPIRegister, PyPIUpload
pypi_register = PyPIRegister()
pypi_upload   = PyPIUpload()


commands = {}
for x in __all__:
    commands[x] = locals()[x]

command_names = dict(zip(commands.values(), commands.keys()))
