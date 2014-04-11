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


if __name__ == '__main__':
    pass

