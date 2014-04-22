#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

# QT5XX: Implement a minimal QPA plugin to allow headless operation, see the
# minimal example in the Qt source code and see
# https://github.com/ariya/phantomjs/pull/173 for info on how to enable fonts
# with fontconfig (probably needed for PDF output and SVG rendering)

# QT5XX: Port def wheelEvent() (orientation() and delta() to be replaced by
# angleDelta())

# QT5XX: Add a import checker that looks for all from PyQt5.* imports and runs
# them to check that they work. This can probably be made part of python
# setup.py check.

# QT5XX: Check that DeviceCategoryEditor and TagListEditor work

# QT5XX: Delete this file after migration is completed

import os, re

def all_py_files():
    base = os.path.dirname(os.path.dirname(os.path.basename(__file__)))
    for dirpath, dirname, filenames in os.walk(os.path.join(base, 'src', 'calibre')):
        for n in filenames:
            if n.endswith('.py'):
                yield os.path.join(dirpath, n)

def detect_qvariant():
    count = 0
    pat = re.compile(b'|'.join(br'QVariant NONE toInt toBool toString\(\) toPyObject canConvert toBitArray toByteArray toHash toFloat toMap toLine toPoint toReal toRect toTime toUInt toUrl'.split()))  # noqa
    exclusions = {}
    for path in all_py_files():
        if os.path.basename(path) in {
                'BeautifulSoup.py', 'icu.py', 'smtp.py', 'Zeroconf.py', 'date.py', 'apsw_shell.py', } or 'pylrs' in path:
            continue
        raw = open(path, 'rb').read()
        matches = set(pat.findall(raw)) - exclusions.get(path, set())
        if matches:
            print (path, '\t', ', '.join(matches))
            count += 1
    print ('Detected %d files with possible usage of QVariant' % count)


if __name__ == '__main__':
    detect_qvariant()

