#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

__all__ = [
    'pot', 'translations', 'get_translations', 'iso639', 'iso3166',
    'build', 'mathjax', 'man_pages',
    'gui',
    'git_version',
    'develop', 'install',
    'kakasi', 'rapydscript', 'cacerts', 'recent_uas', 'resources',
    'check', 'to3', 'unicode_check', 'iterators_check', 'test', 'test_rs',
    'sdist', 'bootstrap', 'extdev',
    'manual', 'tag_release',
    'upload_to_server',
    'upload_installers',
    'upload_user_manual', 'upload_demo', 'reupload',
    'stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'publish', 'publish_betas',
    'linux', 'linux32', 'linux64', 'win', 'win32', 'win64', 'osx', 'build_dep',
    'export_packages', 'hyphenation', 'csslint'
]

from setup.installers import Linux, Win, OSX, Linux32, Linux64, Win32, Win64, ExtDev, BuildDep, ExportPackages
linux, linux32, linux64 = Linux(), Linux32(), Linux64()
win, win32, win64 = Win(), Win32(), Win64()
osx = OSX()
extdev = ExtDev()
build_dep = BuildDep()
export_packages = ExportPackages()

from setup.translations import POT, GetTranslations, Translations, ISO639, ISO3166
pot = POT()
translations = Translations()
get_translations = GetTranslations()
iso639 = ISO639()
iso3166 = ISO3166()

from setup.csslint import CSSLint
csslint = CSSLint()

from setup.build import Build
build = Build()

from setup.mathjax import MathJax
mathjax = MathJax()

from setup.hyphenation import Hyphenation
hyphenation = Hyphenation()

from setup.git_version import GitVersion
git_version = GitVersion()

from setup.install import Develop, Install, Sdist, Bootstrap
develop = Develop()
install = Install()
sdist = Sdist()
bootstrap = Bootstrap()

from setup.gui import GUI
gui = GUI()

from setup.check import Check
check = Check()
from setup.port import To3, UnicodeCheck, IteratorsCheck
to3 = To3()
unicode_check = UnicodeCheck()
iterators_check = IteratorsCheck()

from setup.test import Test, TestRS
test = Test()
test_rs = TestRS()

from setup.resources import Resources, Kakasi, CACerts, RapydScript, RecentUAs
resources = Resources()
kakasi = Kakasi()
cacerts = CACerts()
recent_uas = RecentUAs()
rapydscript = RapydScript()

from setup.publish import Manual, TagRelease, Stage1, Stage2, \
        Stage3, Stage4, Stage5, Publish, PublishBetas, ManPages
manual = Manual()
tag_release = TagRelease()
stage1 = Stage1()
stage2 = Stage2()
stage3 = Stage3()
stage4 = Stage4()
stage5 = Stage5()
publish = Publish()
publish_betas = PublishBetas()
man_pages = ManPages()

from setup.upload import (UploadUserManual, UploadDemo, UploadInstallers,
        UploadToServer, ReUpload)
upload_user_manual = UploadUserManual()
upload_demo = UploadDemo()
upload_to_server = UploadToServer()
upload_installers = UploadInstallers()
reupload = ReUpload()

commands = {}
for x in __all__:
    commands[x] = locals()[x]

command_names = dict(zip(commands.values(), commands.keys()))
