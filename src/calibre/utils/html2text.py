#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


def html2text(html):
    from html2text import HTML2Text
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
    h2t.body_width = 0
    h2t.single_line_break = True
    h2t.emphasis_mark = '*'
    return h2t.handle(html)


def find_tests():
    import unittest

    class TestH2T(unittest.TestCase):

        def test_html2text_behavior(self):
            for src, expected in {
                '<u>test</U>': 'test\n',
                '<i>test</i>': '*test*\n',
                '<a href="http://else.where/other">other</a>': '[other](http://else.where/other)\n',
                '<img src="test.jpeg">': '![Unnamed image](test.jpeg)\n',
                '<a href="#t">test</a> <span id="t">dest</span>': 'test dest\n',
                '<>a': '<>a\n',
                '<p>a<p>b': 'a\nb\n',
            }.items():
                self.assertEqual(html2text(src), expected)

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestH2T)
