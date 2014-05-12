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
base = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
os.chdir(base)

if flags == '1':  # A branch checkout
    prev_branch, cur_branch = map(get_branch_name, (prev_rev, current_rev))

    subprocess.check_call(['python', 'setup.py', 'gui', '--summary'])

    # Remove .pyc files as some of them might have been orphaned
    for dirpath, dirnames, filenames in os.walk('.'):
        for f in filenames:
            fpath = os.path.join(dirpath, f)
            if f.endswith('.pyc'):
                os.remove(fpath)

elif flags in ('master', 'qt5'):
    cur_branch = get_branch_name('HEAD')
    next_branch = flags
    if cur_branch == next_branch:
        print ('Already on branch', next_branch, file=sys.stderr)
        raise SystemExit(1)
    is_qt5_transition = 'qt5' in (next_branch, cur_branch)
    print ('Transitioning from', cur_branch, 'to', next_branch)

    if is_qt5_transition:
        # Remove compiled .ui files as they must be re-generated
        for dirpath, dirnames, filenames in os.walk('.'):
            for f in filenames:
                if f.endswith('_ui.py'):
                    os.remove(os.path.join(dirpath, f))

    subprocess.check_call(['git', 'checkout', next_branch])

    if is_qt5_transition:
        # Rebuild PyQt extensions
        if not os.path.exists('.git/rebase-merge'):  # Dont rebuild if we are rebasing
            for ext in ('progress_indicator', 'pictureflow', 'qt_hack'):
                extdir = os.path.join('build', 'pyqt', ext)
                if os.path.exists(extdir):
                    shutil.rmtree(extdir)
                subprocess.check_call(['python', 'setup.py', 'build', '--only', ext])

    if next_branch == 'qt5':
        for dirpath, dirnames, filenames in os.walk('.'):
            for f in filenames:
                fpath = os.path.join(dirpath, f)
                if f.endswith('.py') and 'qtcurve' not in fpath and (b'PyQt' + b'4') in open(fpath, 'rb').read():
                    red = ('\033[%dm'%31).encode('ascii')
                    reset = ('\033[%dm'%31).encode('ascii')
                    sys.stdout.write(red)
                    print ('\nPyQt' + '4 present in:', fpath)
                    sys.stdout.write(reset)
        print ('\n')
        subprocess.check_call(['python', 'setup/qt5-migrate.py'])


