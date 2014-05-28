#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

# QT5XX: Add a import checker that looks for all from PyQt5.* imports and runs
# them to check that they work. This can probably be made part of python
# setup.py check.

# QT5XX: Test touchscreen support on windows 8 in the viewer

# QT5XX: See if you can figure out why the splash screen does not work in linux

# QT5XX: Look for obsolete classes and functions from the list here:
# http://qt-project.org/doc/qt-5/obsoleteclasses.html as these will not be
# present in PyQt5

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
    pat = re.compile(b'|'.join(br'QVariant NONE toDateTime toDate toInt toBool toString\(\) toPyObject canConvert toBitArray toByteArray toHash toFloat toMap toLine toPoint toReal toRect toTime\(\) toUInt toUrl'.split()))  # noqa
    exclusions = {
        'src/calibre/gui2/viewer/gestures.py': {'toPoint'},
        'src/calibre/utils/serve_coffee.py': {'toString()'},
        'src/calibre/gui2/job_indicator.py': {'toPoint'},
        'src/calibre/ebooks/pdf/render/engine.py': {'toRect'},
        'src/calibre/gui2/wizard/send_email.py': {'NONE'},
    }
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

