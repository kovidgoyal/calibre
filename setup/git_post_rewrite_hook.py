#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import subprocess, os, sys

base = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
os.chdir(base)

action = [x.decode('utf-8') if isinstance(x, bytes) else x for x in sys.argv[1:]][0]

if action == 'rebase':
    subprocess.check_call([sys.executable, 'setup.py', 'gui'])
