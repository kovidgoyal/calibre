#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'


try:
    import init_calibre  # noqa
except ImportError:
    pass

import os, unittest, importlib

def find_tests():
    base = os.path.dirname(os.path.abspath(__file__))
    suits = []
    for x in os.listdir(base):
        if x.endswith('.py') and x != 'main.py':
            m = importlib.import_module('calibre.ebooks.oeb.polish.tests.' + x.partition('.')[0])
            suits.append(unittest.defaultTestLoader.loadTestsFromModule(m))
    return unittest.TestSuite(suits)

if __name__ == '__main__':
    from calibre.db.tests.main import run_tests
    run_tests(find_tests=find_tests)


