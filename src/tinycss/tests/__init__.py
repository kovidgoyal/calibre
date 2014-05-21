#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import unittest

try:
    unicode
except NameError:
    unicode = str

class BaseTest(unittest.TestCase):

    longMessage = True
    maxDiff = None
    ae = unittest.TestCase.assertEqual

    def assert_errors(self, errors, expected_errors):
        """Test not complete error messages but only substrings."""
        self.ae(len(errors), len(expected_errors))
        for error, expected in zip(errors, expected_errors):
            self.assertIn(expected, unicode(error))

