#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.ebooks.oeb.polish.kepubify import Options, kepubify_html_data, remove_kobo_markup_from_html, serialize_html
from calibre.ebooks.oeb.polish.parsing import parse
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
            '<p>An image<img src="x">with tail<img src="b"><i>without':
            '<p><span class="koboSpan" id="kobo.1.1">An image</span><span class="koboSpan" id="kobo.2.1"><img src="x"/></span>'
            '<span class="koboSpan" id="kobo.2.2">with tail</span>'
            '<span class="koboSpan" id="kobo.3.1"><img src="b"/></span><i><span class="koboSpan" id="kobo.3.2">without</span></i></p>',

            # comments
            '<p>A comment<!-- xx -->with tail'
            '<p>A comment<!-- xx --><i>without tail':
            '<p><span class="koboSpan" id="kobo.1.1">A comment</span><!-- xx --><span class="koboSpan" id="kobo.1.2">with tail</span></p>'
            '<p><span class="koboSpan" id="kobo.2.1">A comment</span><!-- xx --><i><span class="koboSpan" id="kobo.2.2">without tail</span></i></p>',

            # nested block tags
            '<div>A div<div> nested.<ul><li>A list<p> with nested block</p> tail1</li> tail2</ul> tail3':
            '<div><span class="koboSpan" id="kobo.1.1">A div</span><div> <span class="koboSpan" id="kobo.1.2">nested.</span>'
            '<ul><li><span class="koboSpan" id="kobo.2.1">A list</span><p> <span class="koboSpan" id="kobo.3.1">with nested block</span></p>'
            ' <span class="koboSpan" id="kobo.3.2">tail1</span></li> <span class="koboSpan" id="kobo.3.3">tail2</span></ul>'
            ' <span class="koboSpan" id="kobo.3.4">tail3</span></div></div>',

            # skipped tags
            '<div>Script: <script>a = 1</script> with tail':
            '<div><span class="koboSpan" id="kobo.1.1">Script: </span><script>a = 1</script> <span class="koboSpan" id="kobo.1.2">with tail</span></div>',
            '<div>Svg: <svg>mouse</svg><i> no tail':
            '<div><span class="koboSpan" id="kobo.1.1">Svg: </span><svg xmlns="http://www.w3.org/2000/svg">mouse</svg>'
            '<i> <span class="koboSpan" id="kobo.1.2">no tail</span></i></div>',

            # encoding quirks
            '<p>A\xa0nbsp;&nbsp;':
            '<p><span class="koboSpan" id="kobo.1.1">A&#160;nbsp;&#160;</span></p>',
            '<div><script>1 < 2 & 3</script>':  # escaping with cdata note that kepubify doesnt do this
            '<div><script><![CDATA[1 < 2 & 3]]></script></div>',

            # CSS filtering
            '<div><style>@page { margin: 13px; }\ndiv { color: red; widows: 12 }</style>Something something</div>':
            '<div><style>div {\n  color: red;\n}</style><span class="koboSpan" id="kobo.1.1">Something something</span></div>'
        }.items():
            opts = Options()
            opts = opts._replace(remove_widows_and_orphans=True)
            opts = opts._replace(remove_at_page_rules=True)
            root = kepubify_html_data(src, opts)
            actual = serialize_html(root).decode('utf-8')
            actual = actual[len(prefix):-len(suffix)]
            self.assertEqual(expected, actual)
            if '@page' in src:
                continue
            expected = serialize_html(parse(src)).decode('utf-8')
            remove_kobo_markup_from_html(root)
            actual = serialize_html(root).decode('utf-8')
            self.assertEqual(expected, actual)
