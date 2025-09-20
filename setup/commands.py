#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

__all__ = [
    'bootstrap',
    'build',
    'build_dep',
    'cacerts',
    'check',
    'develop',
    'export_packages',
    'extdev',
    'get_translations',
    'git_hooks',
    'git_version',
    'gui',
    'hyphenation',
    'install',
    'iso639',
    'iso3166',
    'iso_data',
    'liberation_fonts',
    'linux',
    'linux64',
    'linuxarm64',
    'man_pages',
    'manual',
    'mathjax',
    'osx',
    'piper_voices',
    'pot',
    'publish',
    'publish_betas',
    'publish_preview',
    'rapydscript',
    'recent_uas',
    'resources',
    'reupload',
    'sdist',
    'stage1',
    'stage2',
    'stage3',
    'stage4',
    'stage5',
    'stylelint',
    'tag_release',
    'test',
    'test_rs',
    'translations',
    'upgrade_source_code',
    'upload_demo',
    'upload_installers',
    'upload_to_server',
    'upload_user_manual',
    'win',
    'win64',
    'xwin',
]

from setup.installers import OSX, BuildDep, ExportPackages, ExtDev, Linux, Linux64, LinuxArm64, Win, Win64

linux, linux64, linuxarm64 = Linux(), Linux64(), LinuxArm64()
win, win64 = Win(), Win64()
osx = OSX()
extdev = ExtDev()
build_dep = BuildDep()
export_packages = ExportPackages()

from setup.iso_codes import iso_data
from setup.translations import ISO639, ISO3166, POT, GetTranslations, Translations

pot = POT()
translations = Translations()
get_translations = GetTranslations()
iso639 = ISO639()
iso3166 = ISO3166()

from setup.csslint import CSSLint

stylelint = CSSLint()

from setup.build import Build

build = Build()

from setup.mathjax import MathJax

mathjax = MathJax()

from setup.hyphenation import Hyphenation

hyphenation = Hyphenation()

from setup.piper import PiperVoices

piper_voices = PiperVoices()

from setup.liberation import LiberationFonts

liberation_fonts = LiberationFonts()

from setup.git_hooks import GitHooks

git_hooks = GitHooks()

from setup.git_version import GitVersion

git_version = GitVersion()

from setup.install import Bootstrap, Develop, Install, Sdist

develop = Develop()
install = Install()
sdist = Sdist()
bootstrap = Bootstrap()

from setup.gui import GUI

gui = GUI()

from setup.check import Check, UpgradeSourceCode

check = Check()
upgrade_source_code = UpgradeSourceCode()

from setup.test import Test, TestRS

test = Test()
test_rs = TestRS()

from setup.resources import CACerts, RapydScript, RecentUAs, Resources

resources = Resources()
cacerts = CACerts()
recent_uas = RecentUAs()
rapydscript = RapydScript()

from setup.publish import ManPages, Manual, Publish, PublishBetas, PublishPreview, Stage1, Stage2, Stage3, Stage4, Stage5, TagRelease

manual = Manual()
tag_release = TagRelease()
stage1 = Stage1()
stage2 = Stage2()
stage3 = Stage3()
stage4 = Stage4()
stage5 = Stage5()
publish = Publish()
publish_betas = PublishBetas()
publish_preview = PublishPreview()
man_pages = ManPages()

from setup.upload import ReUpload, UploadDemo, UploadInstallers, UploadToServer, UploadUserManual

upload_user_manual = UploadUserManual()
upload_demo = UploadDemo()
upload_to_server = UploadToServer()
upload_installers = UploadInstallers()
reupload = ReUpload()


from setup.xwin import XWin

xwin = XWin()

commands = {}
for x in __all__:
    commands[x] = locals()[x]

command_names = dict(zip(commands.values(), commands.keys()))
