#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.ebooks.oeb.base import serialize
from calibre.ebooks.oeb.polish.kepubify import kepubify_html
from calibre.ebooks.oeb.polish.parsing import parse_html5 as parse
from calibre.ebooks.oeb.polish.tests.base import BaseTest


class KepubifyTests(BaseTest):

    def test_kepubify_html(self):
        for src, expected in {
        }.items():
            root = parse(src)
            kepubify_html(root)
            actual = serialize(root, 'text/html').decode('utf-8')
            self.assertEqual(expected, actual)
