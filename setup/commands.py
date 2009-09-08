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
        'develop',
        'check',
        ]


from setup.translations import POT, GetTranslations, Translations, ISO639
pot = POT()
translations = Translations()
get_translations = GetTranslations()
iso639 = ISO639()

from setup.extensions import Build
build = Build()

from setup.install import Develop
develop = Develop()

from setup.gui import GUI
gui = GUI()

from setup.check import Check
check = Check()

commands = {}
for x in __all__:
    commands[x] = locals()[x]

command_names = dict(zip(commands.values(), commands.keys()))
