#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from tinycss.fonts3 import CSSFonts3Parser, parse_font_family, parse_font, serialize_font
from tinycss.tests import BaseTest

from polyglot.builtins import iteritems


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
        for raw, q in iteritems({
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
                '': [],
                '"", a': ['a'],
        }):
            self.ae(q, parse_font_family(raw))
        for single in ('serif', 'sans-serif', 'A B C'):
            self.ae([single], parse_font_family(single))

    def test_parse_font(self):
        def t(raw, **kw):
            q = {('line' if k == 'height' else 'font') + '-' + k:v for k, v in iteritems(kw)}
            self.ae(q, parse_font(raw))
            self.ae(q, parse_font(serialize_font(q)))
        t('caption', family=['sans-serif'])
        t('serif', family=['serif'])
        t('12pt/14pt sans-serif', size='12pt', height='14pt', family=['sans-serif'])
        t('80% sans-serif', size='80%', family=['sans-serif'])
        t('x-large/110% "new century schoolbook", serif', size='x-large', height='110%', family=['new century schoolbook', 'serif'])
        t('bold italic large Palatino, serif', weight='bold', style='italic', size='large', family=['Palatino', 'serif'])
        t('normal small-caps 120%/120% fantasy', style='normal', variant='small-caps', size='120%', height='120%', family=['fantasy'])
        t('condensed oblique 12pt Helvetica Neue, serif', stretch='condensed', style='oblique', size='12pt', family=['Helvetica Neue', 'serif'])
        t('300 italic 1.3em/1.7em FB Armada, sans-serif', weight='300', style='italic', size='1.3em', height='1.7em', family=['FB Armada', 'sans-serif'])
