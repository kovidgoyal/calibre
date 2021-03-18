#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import ast

from calibre.srv.tests.base import SimpleTest


class TestTransform(SimpleTest):

    def test_number_parsing(self):
        from calibre_extensions.fast_css_transform import parse_css_number
        for x in '.314 -.314 0.314 0 2 +2 -1 1e2 -3.14E+2 2e-2'.split():
            self.ae(parse_css_number(x), ast.literal_eval(x))
        self.ae(parse_css_number('2em'), 2)
        self.ae(parse_css_number('.3em'), 0.3)
        self.ae(parse_css_number('3x3'), 3)
