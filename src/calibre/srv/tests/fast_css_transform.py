#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import ast

from calibre.srv.tests.base import SimpleTest
from calibre_extensions.fast_css_transform import parse_css_number, transform_properties


class TestTransform(SimpleTest):

    def test_number_parsing(self):
        for x in '.314 -.314 0.314 0 2 +2 -1 1e2 -3.14E+2 2e-2'.split():
            self.ae(parse_css_number(x), ast.literal_eval(x))
        self.ae(parse_css_number('2em'), 2)
        self.ae(parse_css_number('.3em'), 0.3)
        self.ae(parse_css_number('3x3'), 3)

    def test_basic_css_transforms(self):
        def d(src, expected, is_declaration=True, url_callback=None):
            self.ae(transform_properties(src, is_declaration=is_declaration, url_callback=url_callback), expected)

        d(r'f\ont-s\69z\65 : 16\px', 'font-size: 1rem')
        d('font-size: 16px', 'font-size: 1rem')
        d('fOnt-size :16px', 'fOnt-size :1rem')
        d('font-size:2%', 'font-size:2%')
        d('font-size: 72pt; color: red; font-size: 2in', 'font-size: 6rem; color: red; font-size: 12rem')
