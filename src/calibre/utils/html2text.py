#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)


def rudimentary_html2text(html):
    from lxml import html as h
    root = h.fromstring(html)
    return h.tostring(root, method='text', encoding='unicode')


def html2text(html):
    try:
        from html2text import HTML2Text
    except ImportError:
        # for people running from source
        from calibre.constants import numeric_version
        if numeric_version <= (3, 40, 1):
            return rudimentary_html2text(html)
        raise

    import re
    if isinstance(html, bytes):
        from calibre.ebooks.chardet import xml_to_unicode
        html = xml_to_unicode(html, strip_encoding_pats=True, resolve_entities=True)[0]
    # replace <u> tags with <span> as <u> becomes emphasis in html2text
    html = re.sub(
            r'<\s*(?P<solidus>/?)\s*[uU]\b(?P<rest>[^>]*)>',
            r'<\g<solidus>span\g<rest>>', html)
    h2t = HTML2Text()
    h2t.default_image_alt = _('Unnamed image')
    return h2t.handle(html)


def find_tests():
    import unittest

    class TestH2T(unittest.TestCase):

        def test_html2text_behavior(self):
            for src, expected in {
                '<u>test</U>': 'test\n\n',
                '<i>test</i>': '_test_\n\n',
                '<a href="http://else.where/other">other</a>': '[other](http://else.where/other)\n\n',
                '<img src="test.jpeg">': '![Unnamed image](test.jpeg)\n\n',
                '<a href="#t">test</a> <span id="t">dest</span>': 'test dest\n\n',
                '<>a': '<>a\n\n',
            }.items():
                self.assertEqual(html2text(src), expected)

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestH2T)
