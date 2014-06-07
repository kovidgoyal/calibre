#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from tinycss.fonts3 import CSSFonts3Parser
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


