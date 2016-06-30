#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from tinycss.fonts3 import CSSFonts3Parser, parse_font_family
from tinycss.tests import BaseTest

class TestFonts3(BaseTest):

    def test_font_face(self):
        'Test parsing of font face rules'
        for css, expected_declarations, expected_errors in [
                ('@font-face {}', [], []),

                ('@font-face { font-family: Moose; src: url(font1.ttf) }',
                 [('font-family', [('IDENT', 'Moose')]), ('src', [('URI', 'font1.ttf')])], []),
        ]:
            stylesheet = CSSFonts3Parser().parse_stylesheet(css)
            self.assert_errors(stylesheet.errors, expected_errors)
            self.ae(len(stylesheet.rules), 1)
            rule = stylesheet.rules[0]
            self.ae(self.jsonify_declarations(rule), expected_declarations)

        stylesheet = CSSFonts3Parser().parse_stylesheet('@font-face;')
        self.assert_errors(stylesheet.errors, ['missing block'])

    def test_parse_font_family(self):
        ' Test parsing of font-family values '
        for raw, q in {
                '"1as"': ['1as'],
                'A B C, serif': ['A B C', 'serif'],
                r'Red\/Black': ['Red/Black'],
                'A  B': ['A B'],
                r'Ahem\!': ['Ahem!'],
                r'"Ahem!"': ['Ahem!'],
                '€42': ['€42'],
                r'Hawaii\ 5-0': ['Hawaii 5-0'],
                r'"X \"Y"': ['X "Y'],
                'A B, C D, "E", serif': ['A B', 'C D', 'E', 'serif'],
        }.iteritems():
            self.ae(q, parse_font_family(raw))
        for single in ('serif', 'sans-serif', 'A B C'):
            self.ae([single], parse_font_family(single))


