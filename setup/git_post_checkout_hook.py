#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, subprocess, sys, shutil

prev_rev, current_rev, flags = [x.decode('utf-8') if isinstance(x, bytes) else x for x in sys.argv[1:]]
def get_branch_name(rev):
    return subprocess.check_output(['git', 'name-rev', '--name-only', rev]).decode('utf-8').strip()

if flags == '1':  # A branch checkout
    base = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    os.chdir(base)

    prev_branch, cur_branch = map(get_branch_name, (prev_rev, current_rev))
    is_qt5_transition = 'qt5' in (prev_branch, cur_branch)

    if is_qt5_transition:
        # Remove compiled .ui files as they must be re-generated
        for dirpath, dirnames, filenames in os.walk('.'):
            for f in filenames:
                if f.endswith('_ui.py'):
                    os.remove(os.path.join(dirpath, f))

        # Rebuild PyQt extensions
        for ext in ('progress_indicator',):
            extdir = os.path.join('build', 'pyqt', ext)
            if os.path.exists(extdir):
                shutil.rmtree(extdir)
            subprocess.check_call(['python', 'setup.py', 'build', '--only', ext])

    subprocess.check_call(['python', 'setup.py', 'gui', '--summary'])

    # Remove .pyc files as some of them might have been orphaned
    for dirpath, dirnames, filenames in os.walk('.'):
        for f in filenames:
            fpath = os.path.join(dirpath, f)
            if f.endswith('.pyc'):
                os.remove(fpath)
            elif cur_branch == 'qt5' and f.endswith('.py') and 'qtcurve' not in fpath and (b'PyQt' + b'4') in open(fpath, 'rb').read():
                red = ('\033[%dm'%31).encode('ascii')
                reset = ('\033[%dm'%31).encode('ascii')
                sys.stdout.write(red)
                print ('\nPyQt' + '4 present in:', fpath)
                sys.stdout.write(reset)


