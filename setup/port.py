#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import subprocess
import sys

from setup import Command


class To6(Command):

    description = 'Toggle between the Qt6 and master branches building everything needed'

    def run(self, opts):
        subprocess.check_call(['git', 'switch', '-'])
        subprocess.check_call([sys.executable, 'setup.py', 'build', '--clean'])
        subprocess.check_call([sys.executable, 'setup.py', 'build'])
        subprocess.check_call([sys.executable, 'setup.py', 'gui', '--clean'])
        subprocess.check_call([sys.executable, 'setup.py', 'gui'])
