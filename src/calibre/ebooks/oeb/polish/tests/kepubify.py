#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.container import EpubContainer, get_container
from calibre.ebooks.oeb.polish.kepubify import (
    CSS_COMMENT_COOKIE,
    DUMMY_COVER_IMAGE_NAME,
    DUMMY_TITLE_PAGE_NAME,
    KOBO_JS_NAME,
    Options,
    kepubify_html_data,
    kepubify_parsed_html,
    kepubify_path,
    serialize_html,
    unkepubify_path,
)
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.polish.tests.base import BaseTest, get_book_for_kepubify


class KepubifyTests(BaseTest):

    def test_kepubify(self):
        def b(has_cover=True, epub_version='3'):
            path = get_book_for_kepubify(has_cover=has_cover, epub_version=epub_version)
            opts = Options()._replace(remove_widows_and_orphans=True, remove_at_page_rules=True)
            outpath = kepubify_path(path, opts=opts, allow_overwrite=True)
            c = get_container(outpath, tweak_mode=True, ebook_cls=EpubContainer)
            spine_names = tuple(n for n, is_linear in c.spine_names)
            cname = 'titlepage.xhtml' if has_cover else f'{DUMMY_TITLE_PAGE_NAME}.xhtml'
            self.assertEqual(spine_names, (cname, 'index_split_000.html', 'index_split_001.html'))
            ps = c.open('page_styles.css', 'r').read()
            for q in (f'{CSS_COMMENT_COOKIE}: @page', f'-{CSS_COMMENT_COOKIE}-widows', f'-{CSS_COMMENT_COOKIE}-orphans'):
                self.assertIn(q, ps)
            cimage = ('cover.png',) if has_cover else (f'{DUMMY_COVER_IMAGE_NAME}.jpeg',)
            self.assertEqual(cimage, tuple(c.manifest_items_with_property('cover-image')))
            # unkepubify
            outpath = unkepubify_path(outpath)
            expected = get_container(path, tweak_mode=True)
            actual = get_container(outpath, tweak_mode=True)
            self.assertEqual(
                tuple(expected.manifest_items_with_property('cover-image')), tuple(actual.manifest_items_with_property('cover-image')))
            self.assertEqual(tuple(expected.mime_map), tuple(actual.mime_map))
            for name, mt in expected.mime_map.items():
                if mt in OEB_DOCS or mt in OEB_STYLES or name.endswith('.opf'):
                    self.assertEqual(expected.open(name, 'rb').read(), actual.open(name, 'rb').read())

        for has_cover in (True, False):
            for epub_version in '23':
                b(has_cover, epub_version)

    def test_kepubify_html(self):
        prefix = f'''<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><style type="text/css" id="kobostylehacks">\
div#book-inner {{ margin-top: 0; margin-bottom: 0; }}</style><script type="text/javascript" src="{KOBO_JS_NAME}"/></head>\
<body><div id="book-columns"><div id="book-inner">'''
        suffix =  '</div></div></body></html>'
        for src, expected in {
            # basics
            '<p>one</p>  <p>\xa0</p><p>\xa0<i>a</i></p>':
            '<p><span class="koboSpan" id="kobo.1.1">one</span></p>  <p><span class="koboSpan" id="kobo.2.1">&#160;</span></p>'
            '<p>&#160;<i><span class="koboSpan" id="kobo.3.1">a</span></i></p>',

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
            '<div><style>@page {\n  margin: 13px;\n}\ndiv {\n  widows: 12;\n  color: red;\n}</style>Some</div>':
            f'<div><style>/* {CSS_COMMENT_COOKIE}: @page {{\n  margin: 13px;\n}} */\n'
            f'div {{\n  -{CSS_COMMENT_COOKIE}-widows: 12;\n  color: red;\n}}</style>'
            '<span class="koboSpan" id="kobo.1.1">Some</span></div>'
        }.items():
            opts = Options()._replace(remove_widows_and_orphans=True, remove_at_page_rules=True)
            root = kepubify_html_data(src, KOBO_JS_NAME, opts)
            actual = serialize_html(root).decode('utf-8')
            actual = actual[len(prefix):-len(suffix)]
            self.assertEqual(expected, actual)
            expected = serialize_html(parse(src)).decode('utf-8')
            opts = opts._replace(for_removal=True)
            kepubify_parsed_html(root, KOBO_JS_NAME, opts)
            actual = serialize_html(root).decode('utf-8')
            self.assertEqual(expected, actual)
