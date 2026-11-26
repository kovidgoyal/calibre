#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""Tests for the CSS handling of the conversion pipeline, which uses kgcss"""

import os
import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from kgcss import RuleType, Stylesheet
from lxml import etree

from calibre.ebooks.oeb.base import CSS_MIME, XHTML_MIME, OEBBook, rewrite_links, serialize
from calibre.utils.logging import DevNull

if TYPE_CHECKING:
    from calibre.ebooks.oeb.stylizer import Stylizer

HTML = '<html xmlns="http://www.w3.org/1999/xhtml"><head>{head}</head><body>{body}</body></html>'


def make_book(files: dict[str, str]) -> OEBBook:
    oeb = OEBBook(DevNull())
    for i, (href, data) in enumerate(files.items()):
        oeb.manifest.add(f'id{i}', href, CSS_MIME if href.endswith('.css') else XHTML_MIME, data=data)
    return oeb


class ManifestCSS(unittest.TestCase):
    def test_parsing(self) -> None:
        oeb = make_book({
            'css/main.css': '@import "base.css" print; @import url(missing.css); @page { margin: 1em } a { color: red }',
            'css/base.css': 'p { background: url(../img/a.png) }',
        })
        sheet = oeb.manifest.hrefs['css/main.css'].data
        assert isinstance(sheet, Stylesheet)
        # Imports are inlined, wrapped in @media for their media, with their
        # URLs relative to the importing sheet, @page rules are removed. The
        # import of a missing sheet stays, first, as @import rules must be.
        self.assertEqual([r.type for r in sheet.rules if r.type is not RuleType.COMMENT], [RuleType.IMPORT, RuleType.MEDIA, RuleType.STYLE])
        media = sheet.rules.of_type(RuleType.MEDIA)[0]
        self.assertEqual(media.media.media_text, 'print')
        self.assertEqual(media.rules.of_type(RuleType.STYLE)[0].style['background'], 'url(../img/a.png)')
        # The missing sheet is kept as an @import
        self.assertEqual(sheet.rules.of_type(RuleType.IMPORT)[0].href, 'missing.css')
        # Serialized as UTF-8 bytes
        raw = serialize(sheet, CSS_MIME)
        self.assertIsInstance(raw, bytes)
        self.assertIn(b'a {\n  color: red;\n}', raw)
        self.assertEqual(oeb.manifest.hrefs['css/main.css'].bytes_representation, raw)

    def test_rewrite_links(self) -> None:
        root = etree.fromstring(
            HTML.format(
                head='<style>/* keep */ @import "a.css"; p { background: url(a.png) }  </style>',
                body='<p style="background: url( a.png ); color : red">x</p><p style="color: red">y</p>',
            )
        )

        def repl(url: str) -> str | None:
            return None if url == 'a.css' else 'img/' + url

        rewrite_links(root, repl)
        style, p1, p2 = root.iter('{*}style', '{*}p')
        # Only the URLs change, a None replacement leaves the URL as it is
        self.assertEqual(style.text, '/* keep */ @import "a.css"; p { background: url(img/a.png) }  ')
        self.assertEqual(p1.get('style'), 'background: url(img/a.png); color : red')
        self.assertEqual(p2.get('style'), 'color: red')


class StylizerTest(unittest.TestCase):
    def stylizer(self, body: str, css: str = '', head: str = '') -> Stylizer:
        from calibre.customize.ui import output_profiles
        from calibre.ebooks.oeb.stylizer import Stylizer

        profile = next(x for x in output_profiles() if x.short_name == 'default')
        oeb = make_book({'index.html': HTML.format(head='<link rel="stylesheet" href="s.css"/>' + head, body=body), 's.css': css, 'img/a.png': ''})
        item = oeb.manifest.hrefs['index.html']
        opts = SimpleNamespace(change_justification='original', output_profile=profile)
        root = item.data
        assert isinstance(root, etree._Element)
        return Stylizer(root, item.href, oeb, cast('OptionValues', opts), profile)

    def elem(self, s: Stylizer, eid: str) -> etree._Element:
        return s.oeb.manifest.hrefs['index.html'].data.xpath(f'//*[@id="{eid}"]')[0]  # ty: ignore[unresolved-attribute]

    def test_cascade(self) -> None:
        s = self.stylizer(
            '<p id="a" class="Note">a</p><p id="1x">b</p><p id="c" class="2y">c</p><p id="d" style="color: green; mso-x: y">d</p>'
            '<p id="e" class="imp">e</p><p id="f" class="bad">f</p><p id="g" class="m">g</p>',
            r'''
            .note { color: blue }  /* ids and classes match case-insensitively */
            #\31 x { color: red }
            .\32 y { color: orange }
            .imp { color: navy !important } .imp { color: gray }
            p:hover { color: pink }
            a[x!=y], .bad { color: purple }
            .bad { font: some_font; font-family: X }
            @media screen { .m { color: teal } }
            @media print { .m { color: black } }
            @media (orientation: portrait) { .m { font-weight: bold } }
            @supports (display: grid) { .m { font-style: italic } }
            ''',
        )

        def color(eid: str) -> str | None:
            return s.style(self.elem(s, eid))._style.get('color')

        self.assertEqual(color('a'), 'blue')
        self.assertEqual(color('1x'), 'red')
        self.assertEqual(color('c'), 'orange')
        self.assertEqual(color('d'), 'green')
        self.assertNotIn('mso-x', s.style(self.elem(s, 'd'))._style)
        self.assertEqual(color('e'), 'navy')
        # A rule with an invalid selector is ignored, its valid selectors
        # still apply
        self.assertEqual(color('f'), 'purple')
        # An invalid shorthand does not reset the font
        self.assertEqual(s.style(self.elem(s, 'f'))._style.get('font-family'), 'X')
        g = s.style(self.elem(s, 'g'))._style
        self.assertEqual(g.get('color'), 'teal')
        self.assertEqual(g.get('font-weight'), 'bold')
        # Rules in @supports are not used, as before kgcss
        self.assertNotIn('font-style', g)
        # :hover is recorded as a pseudo-class
        self.assertEqual(s.style(self.elem(s, 'a')).pseudo_classes(frozenset()), {'hover': {'color': 'pink'}})

    def test_style_tag_and_attribute(self) -> None:
        s = self.stylizer(
            '<p id="a" style="background: #EEE url(img/a.png) repeat-x">a</p><p id="b" class="x">b</p>',
            '',
            '<style>@import "s2.css" print; .X { margin: 1px 2px } P.x:FIRST-LETTER { color: red }</style>',
        )
        a = s.style(self.elem(s, 'a'))
        self.assertEqual(a.backgroundColor, '#EEE')
        self.assertIn('url(img/a.png)', a._style['background'])
        b = s.style(self.elem(s, 'b'))
        self.assertEqual((b._style['margin-top'], b._style['margin-right']), ('1px', '2px'))
        # Values are normalized
        s = self.stylizer('<p id="a">a</p>', "p { color: #FF0000; margin: .50em 0px; font-family: 'A',  serif }")
        a = s.style(self.elem(s, 'a'))._style
        self.assertEqual((a['color'], a['margin-top'], a['margin-left'], a['font-family']), ('#F00', '0.5em', '0', '"A", serif'))
        self.assertEqual(b.pseudo_classes(frozenset()), {'first-letter': {'color': 'red'}})


class FontsTest(unittest.TestCase):
    def test_font_properties(self) -> None:
        from kgcss import FontFaceRule, StyleRule, parse_stylesheet

        from calibre.ebooks.oeb.transforms.subset import class_font_styles, find_font_face_rules, get_font_properties

        css = (
            '@font-face { font-family: "A B"; src: url(../f.ttf) format("truetype"), local(x); font-weight: bold }'
            r'.\31 x:before { font-family: inherit; font-weight: 750 } .c, p.d { font-weight: 700; font-style: ITALIC; text-transform: uppercase }'
            r'.\32 y { font-style: oblique }'
        )
        sheet = parse_stylesheet(css)
        ff, r1, r2 = sheet.rules[:3]
        assert isinstance(ff, FontFaceRule) and isinstance(r1, StyleRule) and isinstance(r2, StyleRule)
        self.assertEqual(
            get_font_properties(ff, default='normal'),
            {
                'font-family': ['A B'],
                'src': '../f.ttf',
                'font-weight': '700',
                'font-stretch': 'normal',
                'font-style': 'normal',
                'text-transform': 'normal',
            },
        )
        # inherit is no family, 750 is not a CSS 2 weight
        self.assertEqual(get_font_properties(r1), dict.fromkeys(('font-family', 'src', 'font-weight', 'font-stretch', 'font-style', 'text-transform')))
        oeb = make_book({'css/s.css': css, 'f.ttf': ''})
        oeb.manifest.hrefs['f.ttf'].media_type = 'font/ttf'
        (info,) = find_font_face_rules(oeb.manifest.hrefs['css/s.css'], oeb)
        self.assertEqual((info['item'].href, info['weight']), ('f.ttf', 700))
        # By the class of the first simple selector, escapes decoded, rules
        # without font properties are left out
        self.assertEqual(
            class_font_styles(oeb),
            {'c': {'font-weight': '700', 'font-style': 'italic', 'text-transform': 'uppercase'}, '2y': {'font-style': 'oblique'}},
        )

    def test_odt_class_merging(self) -> None:
        from calibre.ebooks.odt.input import Extract

        css, sel_map = Extract().do_filter_css(r'.P1, .P2 { margin: 0 } .a p, .b { color: red } .\31 x, .y { x: y } .P1 { color: blue }')
        self.assertEqual(sel_map, {'P1': ['c_odt0'], 'P2': ['c_odt0'], '1x': ['c_odt1'], 'y': ['c_odt1']})
        self.assertEqual(
            css,
            '.c_odt0 {\n  margin: 0;\n}\n.a p, .b {\n  color: red;\n}\n.c_odt1 {\n  x: y;\n}\n.P1 {\n  color: blue;\n}',
        )


class ConversionTest(unittest.TestCase):
    def test_flatten_and_split(self) -> None:
        from calibre.ebooks.conversion.plumber import Plumber
        from calibre.ebooks.oeb.polish.container import get_container

        with TemporaryDirectory() as tdir:
            src = os.path.join(tdir, 'index.html')
            with open(src, 'w') as f:
                f.write(
                    HTML.format(
                        head=r'<style>.\32 y { font-style: italic } h1 { page-break-before: always } h2 { page-break-after: always }</style>',
                        body='<h1>One</h1><p class="2y">a</p><h2>Two</h2><p>b</p><h1>Three</h1><p>c</p>',
                    )
                )
            dest = os.path.join(tdir, 'out.epub')
            p = Plumber(src, dest, DevNull())
            p.merge_ui_recommendations([('no_default_epub_cover', True, 1)])
            p.run()
            c = get_container(dest, tweak_mode=True)
            html_names = sorted(n for n, mt in c.mime_map.items() if mt in ('application/xhtml+xml', 'text/html'))

            def text(name: str) -> list[str]:
                root = c.parsed(name)
                assert isinstance(root, etree._Element)
                return [x.strip() for x in root.xpath('//*[local-name()="body"]//text()') if x.strip()]

            # Split before the second h1 and after the h2
            self.assertEqual([text(name) for name in html_names], [['One', 'a', 'Two'], ['b'], ['Three', 'c']])
            css = c.raw_data('stylesheet.css', decode=True)
            assert isinstance(css, str)
            # Class names from the source are escaped
            self.assertIn('.\\32 y {', css)


def find_tests() -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    return unittest.TestSuite(loader.loadTestsFromTestCase(x) for x in (ManifestCSS, StylizerTest, FontsTest, ConversionTest))


if TYPE_CHECKING:
    from calibre.ebooks.conversion.plumber import OptionValues
