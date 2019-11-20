#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import unittest
from .html_writer import merge_w_arrays, merge_cmaps


class TestPDFWriter(unittest.TestCase):

    maxDiff = None

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

    def test_merge_cmaps(self):
        roundtrip = '/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo\n<<  /Registry (Adobe)\n/Ordering (UCS)\n/Supplement 0\n>> def\n/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n12 beginbfchar\n<0003> <0020>\n<000F> <002C>\n<0011> <002E>\n<0013> <0030>\n<001A> <0037>\n<002C> <0049>\n<002E> <004B>\n<0030> <004D>\n<003D> <005A>\n<0070> <201C>\n<007B> <00A0>\n<01AC> <FB01>\nendbfchar\n9 beginbfrange\n<000B> <000C> <0028>\n<0015> <0016> <0032>\n<0024> <0028> <0041>\n<0032> <0033> <004F>\n<0036> <0038> <0053>\n<003A> <003B> <0057>\n<0044> <004C> <0061>\n<004E> <0053> <006B>\n<0055> <005C> <0072>\nendbfrange\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend'  # noqa
        self.assertEqual(roundtrip, merge_cmaps((roundtrip,)))
        self.assertEqual(roundtrip, merge_cmaps((roundtrip, roundtrip)))
        res = merge_cmaps((
            'a\nbegincmap\nb\n1 begincodespacerange\n<0010> <00FF>\nendcodespacerange\n'
            '1 beginbfchar\n<0001> <0020>\nendbfchar\n1 beginbfrange\n<0002> <000a> <00021>\nendbfrange\nendcmap\nc',
            'x\nbegincmap\ny\n1 begincodespacerange\n<0001> <0100>\nendcodespacerange\n'
            '1 beginbfchar\n<0011> <0040>\nendbfchar\n1 beginbfrange\n<0012> <001a> <00051>\nendbfrange\nendcmap\nz'
        ))
        self.assertEqual(
            'a\nbegincmap\nb\n1 begincodespacerange\n<0001> <0100>\nendcodespacerange\n'
            '2 beginbfchar\n<0001> <0020>\n<0011> <0040>\nendbfchar\n'
            '2 beginbfrange\n<0002> <000A> <0021>\n<0012> <001A> <0051>\nendbfrange\nendcmap\nc',
            res)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestPDFWriter)
