#!/usr/bin/env python

import os
import subprocess
import sys

base = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
os.chdir(base)
setup_py = os.path.realpath('./setup.py')


def testfile(file):
    def t(f, start, end, exclude_end=None):
        return f.startswith(start) and f.endswith(end) and not (f.endswith(exclude_end) if exclude_end else False)
    if t(file, ('src/odf', 'src/calibre'), '.py', exclude_end='_ui.py'):
        return True
    if t(file, 'recipes', '.recipe'):
        return True
    if t(file, 'src/pyj', '.pyj'):
        return True
    return False


output = subprocess.check_output((
    'git', 'diff', '--staged', '--name-only', '--no-ext-diff', '-z',
    # Everything except for D
    '--diff-filter=ACMRTUXB',
)).decode('utf-8')

output = output.strip('\0')
if not output:
    output = []
else:
    output = output.split('\0')

filenames = tuple(filter(testfile, output))
if not filenames:
    sys.exit(0)

check_args = [sys.executable, './setup.py', 'check', '--no-editor']
# let's hope that too many arguments do not hold any surprises
for f in filenames:
    check_args.append('-f')
    check_args.append(f)

returncode = subprocess.call(check_args)
sys.exit(returncode)
