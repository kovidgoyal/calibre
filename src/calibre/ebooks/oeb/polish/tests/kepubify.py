#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.ebooks.oeb.base import serialize
from calibre.ebooks.oeb.polish.kepubify import kepubify_html_data
from calibre.ebooks.oeb.polish.tests.base import BaseTest


class KepubifyTests(BaseTest):

    def test_kepubify_html(self):
        prefix = '''<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><style type="text/css" class="kobostylehacks">\
div#book-inner { margin-top: 0; margin-bottom: 0; }</style></head><body><div id="book-columns"><div id="book-inner">'''
        suffix =  '</div></div></body></html>'
        for src, expected in {
            # basics
            '<p>Simple sentences. In a single paragraph.'
            '<p>A sentence <i>with <b>nested</b>, tailed</i> formatting. Another.':

            '<p><span class="koboSpan" id="kobo.1.1">Simple sentences. </span><span class="koboSpan" id="kobo.1.2">In a single paragraph.</span></p>'
            '<p><span class="koboSpan" id="kobo.2.1">A sentence </span><i><span class="koboSpan" id="kobo.2.2">with </span>'
            '<b><span class="koboSpan" id="kobo.2.3">nested</span></b><span class="koboSpan" id="kobo.2.4">, tailed</span></i> '
            '<span class="koboSpan" id="kobo.2.5">formatting. </span>'
            '<span class="koboSpan" id="kobo.2.6">Another.</span></p>',

            # img tags
            '<p>An image<img src="x">with tail':
            '<p><span class="koboSpan" id="kobo.1.1">An image</span><span class="koboSpan" id="kobo.2.1">'
            '<img src="x"/></span><span class="koboSpan" id="kobo.2.2">with tail</span></p>'

            # comments

            # nested block tags

            # skipped tags
        }.items():
            with self.subTest(src=src):
                root = kepubify_html_data(src)
                actual = serialize(root, 'text/html').decode('utf-8')
                actual = actual[len(prefix):-len(suffix)]
                self.assertEqual(expected, actual)
