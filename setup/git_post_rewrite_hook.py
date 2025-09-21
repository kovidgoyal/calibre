#!/usr/bin/env python

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import runpy
import sys

base = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
os.chdir(base)

action = [x.decode('utf-8') if isinstance(x, bytes) else x for x in sys.argv[1:]][0]

if action == 'rebase':
    before = sys.argv
    try:
        sys.argv = ['setup.py', 'gui', '--summary']
        runpy.run_path('setup.py', run_name='__main__')
    finally:
        sys.argv = before
