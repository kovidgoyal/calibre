#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from cssutils.css.colors import COLORS

def int_or_zero(raw):
    try:
        return int(raw)
    except (ValueError, TypeError, AttributeError):
        return 0

# convert_color() {{{
hex_pat = re.compile(r'#([0-9a-f]{6})')
hex3_pat = re.compile(r'#([0-9a-f]{3})')
rgb_pat = re.compile(r'rgba?\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)')

def convert_color(c):
    if not c:
        return None
    c = c.lower().strip()
    if c == 'transparent':
        return None
    try:
        cval = COLORS[c]
    except KeyError:
        m = hex_pat.match(c)
        if m is not None:
            return c.upper()
        m = hex3_pat.match(c)
        if m is not None:
            return '#' + (c[1]*2) + (c[2]*2) + (c[3]*2)
        m = rgb_pat.match(c)
        if m is not None:
            return '#' + ''.join('%02X' % int(m.group(i)) for i in (1, 2, 3))
    else:
        return '#' + ''.join('%02X' % int(x) for x in cval[:3])
    return None

def test_convert_color():
    import unittest
    class TestColors(unittest.TestCase):

        def test_color_conversion(self):
            ae = self.assertEqual
            cc = convert_color
            ae(None, cc(None))
            ae(None, cc('transparent'))
            ae(None, cc('none'))
            ae(None, cc('#12j456'))
            ae('#F0F8FF', cc('AliceBlue'))
            ae('#000000', cc('black'))
            ae(cc('#001'), '#000011')
            ae('#12345D', cc('#12345d'))
            ae('#FFFFFF', cc('rgb(255, 255, 255)'))
            ae('#FF0000', cc('rgba(255, 0, 0, 23)'))
    tests = unittest.defaultTestLoader.loadTestsFromTestCase(TestColors)
    unittest.TextTestRunner(verbosity=4).run(tests)
# }}}
