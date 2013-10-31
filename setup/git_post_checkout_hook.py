#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, subprocess
base = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
subprocess.check_call(['python', 'setup.py', 'gui'], cwd=base)

