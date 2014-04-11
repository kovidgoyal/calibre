#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, subprocess, sys

prev_rev, current_rev, flags = [x.decode('utf-8') if isinstance(x, bytes) else x for x in sys.argv[1:]]
def get_branch_name(rev):
    return subprocess.check_output(['git', 'name-rev', '--name-only', rev]).decode('utf-8').strip()

if flags == '1':  # A branch checkout

    prev_branch, cur_branch = map(get_branch_name, (prev_rev, current_rev))
    is_qt5_transition = 'qt5' in (prev_branch, cur_branch)

    if is_qt5_transition:
        # Remove compiled .ui files as they must be re-generated
        for dirpath, dirnames, filenames in os.walk('.'):
            for f in filenames:
                if f.endswith('_ui.py'):
                    os.remove(os.path.join(dirpath, f))

    base = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    os.chdir(base)
    subprocess.check_call(['python', 'setup.py', 'gui'])

    # Remove .pyc files as some of them might have been orphaned
    for dirpath, dirnames, filenames in os.walk('.'):
        for f in filenames:
            if f.endswith('.pyc'):
                os.remove(os.path.join(dirpath, f))


