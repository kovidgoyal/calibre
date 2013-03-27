#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest, os

def find_tests():
    return unittest.defaultTestLoader.discover(os.path.dirname(os.path.abspath(__file__)), pattern='*.py')

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(find_tests())

