#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import unittest
from .html_writer import merge_w_arrays


class TestPDFWriter(unittest.TestCase):

    def test_merge_w_arrays(self):
        self.assertEqual(merge_w_arrays((  # merge neighbor arrays
            [1, 3, 0.1], [3, [0.1, 0.2]])), [1, 3, 0.1, 4, 4, 0.2])
        self.assertEqual(merge_w_arrays((  # merge neighbor ranges
            [1, 5, 0.1], [6, 8, 0.1])), [1, 8, 0.1])
        self.assertEqual(merge_w_arrays((  # merge neighbor ranges
            [1, 5, 0.1], [6, 8, 0.2])), [1, 5, 0.1, 6, 8, 0.2])

        self.assertEqual(merge_w_arrays((  # disjoin overlap
            [1, 4, 0.1], [3, [0.1, 0.1, 0.2, 0.3]])), [1, 4, 0.1, 5, [0.2, 0.3]])
        self.assertEqual(merge_w_arrays((  # disjoin overlap
            [1, [0.1, 0.2]], [2, 4, 0.2])), [1, [0.1, 0.2], 3, 4, 0.2])

        self.assertEqual(merge_w_arrays((  # split overlapping arrays
            [1, [0.1, 0.2, 0.3]], [3, 5, 0.3])), [1, [0.1, 0.2, 0.3], 4, 5, 0.3])
        self.assertEqual(merge_w_arrays((  # merge overlapping ranges, using first width
            [1, 5, 0.1], [2, 4, 0.2])), [1, 5, 0.1])
        self.assertEqual(merge_w_arrays((  # merge overlapping arrays
            [1, [0.1, 0.1]], [3, [0.2, 0.2]])), [1, [0.1, 0.1, 0.2, 0.2]])

        self.assertEqual(merge_w_arrays((
            [1, 10, 99, 20, [1, 2, 3, 4]],
            [3, 10, 99, 11, 13, 77, 19, [77, 1]])),
            [1, 10, 99, 11, 13, 77, 19, [77, 1, 2, 3, 4]]
        )


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestPDFWriter)
