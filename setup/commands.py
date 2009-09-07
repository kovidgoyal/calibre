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
        'clean', 'clean_backups',
        ]

import os, shutil

from setup.translations import POT, GetTranslations, Translations, ISO639
from setup import Command
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

class CleanBackups(Command):

    description='Delete all backup files in the calibre source tree'

    def clean(self):
        return self.run(None)

    def run(self, opts=None):
        for root, _, files in os.walk(self.d(self.SRC)):
            for name in files:
                for t in ('.pyc', '.pyo', '~', '.swp', '.swo'):
                    if name.endswith(t):
                        os.remove(os.path.join(root, name))

clean_backups = CleanBackups()

class Clean(Command):

    description='''Delete all computer generated files in the source tree'''

    sub_commands = __all__

    def add_options(self, parser):
        opt = parser.remove_option('--only')
        help = 'Only run clean for the specified command. Choices: '+\
                ', '.join(__all__)
        parser.add_option('-1', '--only', default='all',
        choices=__all__+['all'], help=help)

    def run_all(self, opts):
        self.info('Cleaning...')
        only = None if opts.only == 'all' else commands[opts.only]
        for cmd in self.sub_commands:
            if only is not None and only is not cmd:
                continue
            self.info('\tCleaning', command_names[cmd])
            cmd.clean()

    def clean(self):
        for dir in ('dist', os.path.join('src', 'calibre.egg-info')):
            shutil.rmtree(dir, ignore_errors=True)

clean = Clean()


commands = {}
for x in __all__:
    commands[x] = locals()[x]

command_names = dict(zip(commands.values(), commands.keys()))
