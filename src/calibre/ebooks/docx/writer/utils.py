#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from tinycss.color3 import parse_color_string


def int_or_zero(raw):
    try:
        return int(raw)
    except (ValueError, TypeError, AttributeError):
        return 0

# convert_color() {{{


def convert_color(value):
    if not value:
        return
    if value.lower() == 'currentcolor':
        return 'auto'
    val = parse_color_string(value)
    if val is None:
        return
    if val.alpha < 0.01:
        return
    return '%02X%02X%02X' % (int(val.red * 255), int(val.green * 255), int(val.blue * 255))


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
            ae('F0F8FF', cc('AliceBlue'))
            ae('000000', cc('black'))
            ae('FF0000', cc('red'))
            ae('00FF00', cc('lime'))
            ae(cc('#001'), '000011')
            ae('12345D', cc('#12345d'))
            ae('FFFFFF', cc('rgb(255, 255, 255)'))
            ae('FF0000', cc('rgba(255, 0, 0, 23)'))
    tests = unittest.defaultTestLoader.loadTestsFromTestCase(TestColors)
    if return_tests:
        return tests
    unittest.TextTestRunner(verbosity=4).run(tests)
# }}}
