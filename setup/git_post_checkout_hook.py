#!/usr/bin/env python
# vim:fileencoding=utf-8

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, subprocess, sys

prev_rev, current_rev, flags = sys.argv[1:]


def get_branch_name(rev):
    return subprocess.check_output(['git', 'name-rev', '--name-only', '--refs=refs/heads/*', rev]).decode('utf-8').strip()


base = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
os.chdir(base)

if flags == '1':  # A branch checkout
    prev_branch, cur_branch = list(map(get_branch_name, (prev_rev, current_rev)))
    rebase_in_progress = os.path.exists('.git/rebase-apply') or os.path.exists('.git/rebase-merge')

    if {prev_branch, cur_branch} == {'master', 'qt6'} and not rebase_in_progress:
        b = 'qt6' if cur_branch == 'qt6' else 'qt5'
        for x in os.listdir(f'bypy/b/{b}'):
            link = f'bypy/b/{x}'
            try:
                os.remove(link)
            except FileNotFoundError:
                pass
            os.symlink(f'{b}/{x}', link)
        subprocess.check_call('./setup.py build --clean'.split())
        subprocess.check_call('./setup.py gui --clean'.split())
        subprocess.check_call('./setup.py build'.split())

    subprocess.check_call('./setup.py gui --summary'.split())

    # Remove .pyc files as some of them might have been orphaned
    for dirpath, dirnames, filenames in os.walk('.'):
        for f in filenames:
            fpath = os.path.join(dirpath, f)
            if f.endswith('.pyc') and '/chroot/' not in fpath:
                os.remove(fpath)
