#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""Tests for the CSS handling of polish and Edit book, which uses kgcss"""

import os
from itertools import count
from typing import TYPE_CHECKING

from kgcss import RuleType, SerializeOptions, StyleRule, Stylesheet
from kgcss import compat as css_compat
from lxml import etree

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.polish.tests.structure import cmi, create_epub

if TYPE_CHECKING:
    from calibre.ebooks.oeb.polish.container import Container

counter = count()


def html(body: str, head: str = '') -> str:
    return f'<html xmlns="http://www.w3.org/1999/xhtml"><head><link rel="stylesheet" href="s.css"/>{head}</head><body>{body}</body></html>'


class PolishCSS(BaseTest):
    def container(self, files: dict[str, str | bytes]) -> Container:
        n = next(counter)
        ep = os.path.join(self.tdir, f'{n}.epub')
        with open(ep, 'wb') as f:
            f.write(create_epub([cmi(k, v) for k, v in files.items()]).getvalue())
        return get_container(ep, tdir=os.path.join(self.tdir, f'container{n}'), tweak_mode=True)

    def style_rules(self, sheet: Stylesheet) -> list[str]:
        return [r.selector_text for r in sheet.iter_rules(RuleType.STYLE)]

    def test_container(self) -> None:
        c = self.container({'a.html': html('<p>x</p>'), 's.css': '#\\31 x { color: red } @supports (x: y) { p { background: url(i.png) } }', 'i.png': b'x'})
        # Plugins get css_parser-style views of the kgcss stylesheets
        view = c.parsed('s.css')
        assert isinstance(view, css_compat.CSSStyleSheet)
        sheet = c.parsed_stylesheet('s.css')
        self.assertIs(css_compat.unwrap(view), sheet)
        view.cssRules[0].style.setProperty('color', 'blue')
        self.assertEqual(sheet.rules[0].style['color'], 'blue')
        c.dirty('s.css')
        # Escapes in selectors are kept, the indent is configurable
        c.css_serialize_options = SerializeOptions(indent='\t')
        c.commit_item('s.css', keep_parsed=True)
        self.assertEqual(c.raw_data('s.css'), '#\\31 x {\n\tcolor: blue;\n}\n@supports (x: y) {\n\tp {\n\t\tbackground: url(i.png);\n\t}\n}\n')
        decl = c.parse_css('color: red', is_declaration=True)
        self.assertEqual(decl.getPropertyValue('color'), 'red')
        new_sheet = c.parse_css('a { color: green }')
        c.replace('s.css', new_sheet)
        self.assertIs(c.parsed_stylesheet('s.css'), css_compat.unwrap(new_sheet))
        # Links in grouping rules
        c.replace('s.css', c.parse_stylesheet('@media screen { @supports (x: y) { p { background: url(i.png) } } }'))
        self.assertEqual(list(c.iterlinks('s.css', get_line_numbers=False)), ['i.png'])
        from calibre.ebooks.oeb.polish.replace import rename_files

        rename_files(c, {'i.png': 'images/i.png'})
        self.assertEqual(list(c.iterlinks('s.css', get_line_numbers=False)), ['images/i.png'])

    def test_remove_unused_css(self) -> None:
        from calibre.ebooks.oeb.polish.css import remove_unused_css

        c = self.container({
            'a.html': html('<p id="1x" class="USED other">x</p>', '<style>.nothing { color: red } p { color: blue }</style>'),
            's.css': '#\\31 x { a: b } .used, .unused { c: d } @media screen { .unused2 { e: f } .used { g: h } } p:hover { x: y } a[x!=y] { z: z }',
        })
        self.assertTrue(remove_unused_css(c, remove_unused_classes=True))
        # Rules at any depth, escapes and case-insensitive classes, invalid
        # selectors are kept
        self.assertEqual(self.style_rules(c.parsed_stylesheet('s.css')), ['#\\31 x', '.used', '.used', 'p:hover', 'a[x!=y]'])
        root = c.parsed('a.html')
        assert isinstance(root, etree._Element)
        self.assertEqual(root.xpath('//*[local-name()="p"]/@class'), ['USED'])
        style = root.xpath('//*[local-name()="style"]')[0]
        self.assertNotIn('nothing', style.text)

        c = self.container({'a.html': html('<p>x</p>'), 's.css': 'p { x: 1 } p { y: 2 } @media print { p { x: 1 } p { y: 2 } } a { z: 3 } b { z: 3 }'})
        self.assertTrue(remove_unused_css(c, merge_rules=True, merge_rules_with_identical_properties=True))
        sheet = c.parsed_stylesheet('s.css')
        # Merged in the same list of rules only
        self.assertEqual(sheet.css_text, 'p {\n  x: 1;\n  y: 2;\n}\n@media print {\n  p {\n    x: 1;\n    y: 2;\n  }\n}')

    def test_filter_and_rename(self) -> None:
        from calibre.ebooks.oeb.polish.css import filter_css, rename_class, rename_ids_in_css, sort_sheet

        c = self.container({
            'a.html': html(
                '<p class="old old-x" style="margin: 1px; color: red">x</p><p style="margin-top: 1px">y</p>',
                '<style>.old { color: red }</style>',
            ),
            's.css': '@media screen { p.old, .old-x, #old { margin: 1px 2px; color: red } }',
        })
        self.assertTrue(filter_css(c, {'margin-left', 'color'}))
        sheet = c.parsed_stylesheet('s.css')
        style = sheet.iter_rules(RuleType.STYLE).__next__().style
        self.assertEqual(style.to_css(single_line=True), 'margin-top: 1px; margin-right: 2px; margin-bottom: 1px')
        root = c.parsed('a.html')
        assert isinstance(root, etree._Element)
        self.assertEqual(root.xpath('//*[local-name()="p"]/@style'), ['margin-top: 1px; margin-right: 1px; margin-bottom: 1px', 'margin-top: 1px'])
        self.assertEqual(root.xpath('//*[local-name()="style"]')[0].text.strip(), '')

        self.assertTrue(rename_class(c, 'old', '1new'))
        # Whole class names only, escaped as needed
        self.assertEqual(self.style_rules(sheet), ['p.\\31 new, .old-x, #old'])
        self.assertEqual(root.xpath('//*[local-name()="p"]/@class'), ['1new old-x'])
        self.assertTrue(rename_ids_in_css(c, {'old': 'new'}))
        self.assertEqual(self.style_rules(sheet), ['p.\\31 new, .old-x, #new'])

        sheet = sort_sheet(c, '@import "x.css"; b { x: y } /* c */ #a, .b { x: y } @font-face { font-family: Z } a { x: y } @font-face { font-family: A }')
        self.assertEqual(
            [r.css_text.partition('{')[0].strip() for r in sheet.rules],
            ['/* c */', '@import "x.css";', '@font-face', '@font-face', 'a', 'b', '.b, #a'],
        )
        ff = [r for r in sheet.rules if r.type is RuleType.FONT_FACE]
        self.assertEqual([r.css_text for r in ff], ['@font-face {\n  font-family: A;\n}', '@font-face {\n  font-family: Z;\n}'])

    def test_fonts(self) -> None:
        from calibre.ebooks.oeb.polish.fonts import change_font, font_family_data

        c = self.container({
            'a.html': html(
                '<p style="font-family: Old, serif">x</p><p style="font: 12px Old">y</p>',
                '<style>@media screen { p { font-family: "Old" } }</style>',
            ),
            's.css': '@font-face { font-family: Old; src: local(x), url("f 1.ttf") } h1 { font: bold 2em Old, Other }',
            'f 1.ttf': b'font',
        })
        self.assertEqual(font_family_data(c), {'Old': True, 'serif': False, 'Other': False})
        self.assertTrue(change_font(c, 'Old', 'New One'))
        root = c.parsed('a.html')
        assert isinstance(root, etree._Element)
        # Strings in style attributes use single quotes
        self.assertEqual(root.xpath('//*[local-name()="p"]/@style'), ["font-family: 'New One', serif", "font: 12px 'New One'"])
        # <style> sheets are written back
        self.assertIn('"New One"', root.xpath('//*[local-name()="style"]')[0].text)
        sheet = c.parsed_stylesheet('s.css')
        # The embedded font is removed, found by its URL
        self.assertEqual([r.type for r in sheet.rules], [RuleType.STYLE])
        self.assertFalse(c.has_name('f 1.ttf'))
        rule = sheet.rules[0]
        assert isinstance(rule, StyleRule)
        self.assertEqual(rule.style['font'], 'bold 2em "New One", Other')

    def test_jump_to_class(self) -> None:
        from calibre.gui2.tweak_book.jump_to_class import NoMatchingRuleFound, RuleLocation, find_first_matching_rule

        raw = html('\n<p class="x">x</p>\n<p class="z">z</p>', '<style>.z { color: red }</style>')
        c = self.container({
            'a.html': raw,
            's.css': '@charset "utf-8";\n/* c */\n@import "i.css";\na { x: y }\n@media screen { .y { x: y } .X { x: y } }',
            'i.css': '/* c */ .z { x: y }',
        })

        def find(cls: str, line: int) -> RuleLocation:
            return find_first_matching_rule(c, 'a.html', raw, {'class': cls, 'sourceline_address': (line, ['p'])})

        # Addresses count rules as browsers do: without comments and @charset
        self.assertEqual(find('x', 2), RuleLocation([2, 1], 's.css'))
        # Through @import, the linked sheet comes before the <style> tag
        self.assertEqual(find('z', 3), RuleLocation([0], 'i.css'))
        with self.assertRaises(NoMatchingRuleFound):
            find('q', 2)

    def test_edit_book_helpers(self) -> None:
        from calibre.gui2.tweak_book import css_serialize_options, current_container, set_current_container, tprefs
        from calibre.gui2.tweak_book.diff.view import beautify_text
        from calibre.gui2.tweak_book.editor.smarts.css import find_rule

        # Rule addresses as browsers count rules: no comments or @charset,
        # grouping rules such as @supports included
        raw = '@charset "utf-8";\n/* c */\n@supports (x: y) {\n  a { b: c }\n}\np { x: y }'
        self.assertEqual(find_rule(raw, (0, 0)), (4, 3))
        self.assertEqual(find_rule(raw, (1,)), (6, 1))
        self.assertEqual(find_rule(raw, (2,)), (None, None))

        indent = ' ' * tprefs['editor_tab_stop_width']
        self.assertEqual(css_serialize_options().indent, indent)
        self.assertEqual(beautify_text('a{b:c}', 'css'), f'a {{\n{indent}b: c;\n}}\n')
        c = self.container({'s.css': 'a{b:c}'})
        previous = current_container()
        try:
            set_current_container(c)
            self.assertEqual(c.css_serialize_options.indent, indent)
        finally:
            set_current_container(previous)

    def test_css_parser_style_plugins(self) -> None:
        # The code of the editor demo plugin as it was written for css_parser,
        # which must keep working on the css_parser-style views
        from kgcss.compat import CSSRule

        from calibre.ebooks.oeb.polish.container import OEB_DOCS, OEB_STYLES, serialize

        c = self.container({
            'a.html': html('<p style="font-size: 10pt; color: red">x</p>', '<style>p { font-size: 2em }</style>'),
            's.css': 'h1 { font-size: 12pt } @media screen { h2 { font-size: 1em } }',
        })

        def magnify_declaration(style: css_compat.CSSStyleDeclaration) -> None:
            val = style.getPropertyValue('font-size')
            if val:
                style.setProperty('font-size', val.replace(val.rstrip('emptx'), str(2 * float(val.rstrip('emptx')))))

        for name, media_type in c.mime_map.items():
            if media_type in OEB_STYLES:
                sheet = c.parsed(name)
                assert isinstance(sheet, css_compat.CSSStyleSheet)
                for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
                    magnify_declaration(rule.style)
                c.dirty(name)
            elif media_type in OEB_DOCS:
                root = c.parsed(name)
                assert isinstance(root, etree._Element)
                for style_tag in root.xpath('//*[local-name()="style"]'):
                    sheet = c.parse_css(style_tag.text)
                    for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
                        magnify_declaration(rule.style)
                    style_tag.text = serialize(sheet, 'text/css', pretty_print=True).decode('utf-8')
                for elem in root.xpath('//*[@style]'):
                    block = c.parse_css(elem.get('style'), is_declaration=True)
                    magnify_declaration(block)
                    elem.set('style', block.getCssText(separator=' '))
                c.dirty(name)
        self.assertEqual(c.parsed_stylesheet('s.css').css_text, 'h1 {\n  font-size: 24pt;\n}\n@media screen {\n  h2 {\n    font-size: 1em;\n  }\n}')
        root = c.parsed('a.html')
        assert isinstance(root, etree._Element)
        self.assertEqual(root.xpath('//*[local-name()="style"]')[0].text, 'p {\n  font-size: 4em;\n}\n')
        self.assertEqual(root.xpath('//*[local-name()="p"]/@style'), ['font-size: 20pt; color: red'])
