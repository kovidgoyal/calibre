#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

# QT5XX: Delete this file after migration is completed

import os

def all_py_files():
    base = os.path.dirname(os.path.dirname(os.path.basename(__file__)))
    for dirpath, dirname, filenames in os.walk(os.path.join(base, 'src', 'calibre')):
        for n in filenames:
            if n.endswith('.py'):
                yield os.path.join(dirpath, n)

def port_imports():
    for path in all_py_files():
        with open(path, 'r+b') as f:
            raw = f.read()
            nraw = raw.replace(b'from PyQt4.', b'from PyQt5.')
            if nraw != raw:
                f.seek(0), f.truncate()
                f.write(nraw)


if __name__ == '__main__':
    port_imports()

