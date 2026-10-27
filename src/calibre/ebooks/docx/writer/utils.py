#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from tinycss.color4 import parse_color_string


def int_or_zero(raw):
    try:
        return int(raw)
    except ValueError, TypeError, AttributeError:
        return 0


# convert_color() {{{


def convert_color(value):
    if not value:
        return
    val = parse_color_string(value)
    if val == 'currentColor':
        return 'auto'
    if not isinstance(val, tuple) or val.alpha < 0.01:
        return
    # Round rather than truncate as colors converted from other color spaces
    # are not exact multiples of 1/255
    return ''.join(f'{int(x * 255 + 0.5):02X}' for x in val[:3])


def test_convert_color(return_tests=False):
    import unittest

    class TestColors(unittest.TestCase):
        def test_color_conversion(self):
            ae = self.assertEqual
            cc = convert_color
            ae(None, cc(None))
            ae(None, cc('transparent'))
            ae(None, cc('none'))
            ae(None, cc('#12j456'))
            ae('auto', cc('currentColor'))
            ae('auto', cc(' currentColor '))
            ae('F0F8FF', cc('AliceBlue'))
            ae('000000', cc('black'))
            ae('FF0000', cc('red'))
            ae('00FF00', cc('lime'))
            ae(cc('#001'), '000011')
            ae('12345D', cc('#12345d'))
            ae('FFFFFF', cc('rgb(255, 255, 255)'))
            ae('FF0000', cc('rgba(255, 0, 0, 23)'))
            ae('1A334D', cc('rgb(10%, 20%, 30%)'))
            ae('00FF00', cc('rgb(-51, 306, 0)'))
            # CSS Color Level 4
            ae('FF0000', cc('#ff000080'))
            ae(None, cc('#ff000000'))
            ae('FF0000', cc('rgb(255 0 0 / 50%)'))
            ae('663399', cc('rebeccapurple'))
            ae('40BF40', cc('hsl(120deg 50% 50%)'))
            ae('33B333', cc('hwb(120 20% 30%)'))
            ae('FFFFFF', cc('lab(100 0 0)'))
            ae('FF0000', cc('oklch(0.628 0.2577 29.23)'))
            ae('FF0000', cc('color(display-p3 0.9175 0.2003 0.1386)'))
            ae(None, cc('rgb(var(--x))'))

    tests = unittest.defaultTestLoader.loadTestsFromTestCase(TestColors)
    if return_tests:
        return tests
    unittest.TextTestRunner(verbosity=4).run(tests)


# }}}
