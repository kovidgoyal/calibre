#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from zipfile import ZipFile

from html5_parser import parse
from lxml import etree

from calibre.ebooks.docx.names import DOCXNamespace
from calibre.ebooks.docx.writer.container import DocumentRelationships
from calibre.ebooks.docx.writer.from_html import Block, Blocks, TextRun
from calibre.ebooks.docx.writer.links import LinksManager
from calibre.utils.logging import DevNull
from calibre.utils.resources import get_image_path as I

if TYPE_CHECKING:
    from calibre.ebooks.docx.styles import Styles
    from calibre.ebooks.docx.writer.links import Link
    from calibre.ebooks.docx.writer.styles import DescendantTextStyle, StylesManager, TextStyle
    from calibre.ebooks.oeb.stylizer import Style
    from calibre.utils.logging import Log


class BaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.namespace = DOCXNamespace()
        self.relationships = DocumentRelationships(self.namespace)
        self.links = LinksManager(self.namespace, self.relationships, DevNull())
        self.item = SimpleNamespace(abshref=lambda href: href or 'test.html')
        self.body = etree.Element(self.namespace.expand('w:body'))

    def link(self, url: str = 'https://example.com', tooltip: str | None = None) -> Link:
        return cast('Link', (self.item, url, tooltip))  # self.item is a duck-typed stand-in for a manifest item

    def block(self) -> Block:
        styles = SimpleNamespace(create_block_style=lambda *args, **kwargs: SimpleNamespace(id=None))
        styles.create_text_style = lambda style, **kwargs: style.get('font-weight', 'normal')
        style = {'page-break-before': 'auto', 'page-break-inside': 'auto'}
        # duck-typed stand-ins for the styles manager and the CSS style
        return Block(self.namespace, cast('StylesManager', styles), self.links, etree.Element('p'), cast('Style', style))

    def add_text(self, block: Block, text: str, link: Link | None = None, bold: bool = False, lang: str | None = None, bookmark: str | None = None) -> None:
        style = {'white-space': 'normal', 'font-weight': 'bold' if bold else 'normal'}
        block.add_text(text, cast('Style', style), link=link, lang=lang, bookmark=bookmark)
        block.runs[-1].descendant_style = cast('DescendantTextStyle', SimpleNamespace(id='Bold' if bold else 'Normal'))

    def floating_drawing(self) -> etree._Element:
        ans = self.namespace.makeelement(self.body, 'w:drawing', append=False)
        anchor = self.namespace.makeelement(ans, 'wp:anchor')
        self.namespace.makeelement(anchor, 'wp:docPr')
        graphic_data = self.namespace.makeelement(self.namespace.makeelement(anchor, 'a:graphic'), 'a:graphicData')
        self.namespace.makeelement(self.namespace.makeelement(self.namespace.makeelement(graphic_data, 'pic:pic'), 'pic:nvPicPr'), 'pic:cNvPr')
        return ans

    def xpath(self, expression: str, root: etree._Element | None = None) -> list:  # XPath results can be elements or strings
        return self.namespace.XPath(expression)(self.body if root is None else root)


class TestHyperlinks(BaseTest):
    def test_styled_hyperlink(self) -> None:
        block, link = self.block(), self.link(tooltip='Example')
        self.add_text(block, 'Before ')
        self.add_text(block, 'oddities linktext ', link)
        self.add_text(block, '&', link, bold=True, lang='it')
        self.add_text(block, ' ampersands', link)
        self.add_text(block, ' after')
        block.serialize(self.body)
        hyperlinks = self.xpath('./w:p/w:hyperlink')
        self.assertEqual(len(hyperlinks), 1)
        hyperlink = hyperlinks[0]
        self.assertEqual(self.xpath('./w:r/w:t/text()', hyperlink), ['oddities linktext ', '&', ' ampersands'])
        self.assertEqual(self.xpath('./w:r/w:rPr/w:rStyle/@w:val', hyperlink), ['Normal', 'Bold', 'Normal'])
        self.assertEqual(self.xpath('./w:r/w:rPr/w:lang/@w:val', hyperlink), ['it'])
        self.assertEqual(self.xpath('./w:r/w:t/@xml:space', hyperlink), ['preserve', 'preserve'])
        self.assertEqual(self.xpath('./w:p/w:r/w:t/text()'), ['Before ', ' after'])
        self.assertEqual(hyperlink.get(self.namespace.expand('w:tooltip')), 'Example')
        rid = self.relationships.get_relationship_id('https://example.com', self.namespace.names['LINKS'], 'External')
        self.assertEqual(hyperlink.get(self.namespace.expand('r:id')), rid)

    def test_distinct_source_anchors(self) -> None:
        for second in (self.link(), self.link(tooltip='Different'), self.link(url='https://example.org')):
            with self.subTest(second=second):
                self.body.clear()
                block = self.block()
                self.add_text(block, 'one', self.link())
                self.add_text(block, 'two', second)
                self.assertEqual(len(block.runs), 2)
                block.serialize(self.body)
                self.assertEqual(len(self.xpath('./w:p/w:hyperlink')), 2)

    def test_link_interrupted_by_plain_text(self) -> None:
        block, link = self.block(), self.link()
        self.add_text(block, 'one', link)
        self.add_text(block, ' between ')
        self.add_text(block, 'two', link)
        block.serialize(self.body)
        self.assertEqual(len(self.xpath('./w:p/w:hyperlink')), 2)
        self.assertEqual(self.xpath('./w:p/w:r/w:t/text()'), [' between '])

    def test_separate_blocks(self) -> None:
        link = self.link()
        for parent in (self.body, self.namespace.makeelement(self.body, 'w:tc')):
            for text in ('one', 'two'):
                block = self.block()
                self.add_text(block, text, link)
                self.add_text(block, ' bold', link, bold=True)
                block.serialize(parent)
        self.assertEqual(len(self.xpath('.//w:p/w:hyperlink')), 4)
        self.assertTrue(all(len(self.xpath('./w:hyperlink', p)) == 1 for p in self.xpath('.//w:p')))

    def test_internal_link_and_fallback(self) -> None:
        self.links.document_hrefs.add('test.html')
        self.links.anchor_map[('test.html', 'target')] = 'Target'
        for url, expected in (('#target', 1), ('missing.html#target', 0), ('mailto:test@example.com', 0)):
            with self.subTest(url=url):
                self.body.clear()
                block, link = self.block(), self.link(url)
                self.add_text(block, 'one', link)
                self.add_text(block, 'two', link, bold=True)
                block.serialize(self.body)
                self.assertEqual(len(self.xpath('./w:p/w:hyperlink')), expected)
                self.assertEqual(self.xpath('.//w:t/text()'), ['one', 'two'])
                if expected:
                    self.assertEqual(self.xpath('./w:p/w:hyperlink/@w:anchor'), ['Target'])

    def test_run_contents_and_legacy_serialization(self) -> None:
        block, link = self.block(), self.link()
        self.add_text(block, 'one', link, bookmark='bookmark')
        block.add_break()
        drawing = etree.Element(self.namespace.expand('w:drawing'))
        block.add_image(drawing, link=link)
        self.add_text(block, 'two', link, bold=True)
        block.serialize(self.body)
        self.assertEqual(len(self.xpath('./w:p/w:hyperlink')), 1)
        self.assertEqual(len(self.xpath('./w:p/w:hyperlink/w:r/w:br')), 1)
        self.assertEqual(self.xpath('./w:p/w:hyperlink/w:r/w:drawing'), [drawing])
        self.assertEqual(self.xpath('.//w:bookmarkStart/@w:name'), ['bookmark'])
        self.assertEqual(self.xpath('.//w:bookmarkStart/@w:id'), self.xpath('.//w:bookmarkEnd/@w:id'))
        p = self.namespace.makeelement(self.body, 'w:p')
        run = TextRun(self.namespace, cast('TextStyle', None), cast('etree._Element', None))  # not needed for serialization
        run.add_text('legacy', False, link=link)
        run.serialize(p, self.links)
        self.assertEqual(self.xpath('./w:hyperlink/w:r/w:t/text()', p), ['legacy'])

    def test_linked_images(self) -> None:
        block, link = self.block(), self.link()
        drawings = [etree.Element(self.namespace.expand('w:drawing')) for _ in range(3)]
        self.add_text(block, 'text', link)
        block.add_image(drawings[0])
        block.add_image(drawings[1], link=link)
        block.add_image(drawings[2], link=self.link())
        block.serialize(self.body)
        self.assertEqual(self.xpath('./w:p/w:r/w:drawing'), drawings[:1])
        self.assertEqual([self.xpath('./w:r/w:drawing', h) for h in self.xpath('./w:p/w:hyperlink')], [[], drawings[1:2], drawings[2:]])

    def test_linked_floating_images(self) -> None:
        self.links.document_hrefs.add('test.html')
        self.links.anchor_map[('test.html', 'target')] = 'Target'
        block, link = self.block(), self.link(tooltip='Tip')

        self.add_text(block, 'text', link)
        block.add_image(self.floating_drawing(), link=link, floating=True)
        block.add_image(self.floating_drawing(), link=self.link('#target'), floating=True)
        block.add_image(self.floating_drawing(), floating=True)
        block.serialize(self.body)
        # Word ignores <w:hyperlink> around floating images, the link must be on the image itself
        self.assertEqual(self.xpath('./w:p/w:hyperlink/w:r/w:t/text()'), ['text'])
        self.assertFalse(self.xpath('.//w:hyperlink//w:drawing'))
        external = self.relationships.get_relationship_id('https://example.com', self.namespace.names['LINKS'], 'External')
        internal = self.relationships.get_relationship_id('#Target', self.namespace.names['LINKS'])
        for pr in ('wp:docPr', 'pic:cNvPr'):
            hlinks = self.xpath(f'.//{pr}/a:hlinkClick')
            self.assertEqual([self.namespace.get(h, 'r:id') for h in hlinks], [external, internal], pr)
            self.assertEqual([h.get('tooltip') for h in hlinks], ['Tip', None], pr)

    def test_floating_image_does_not_split_link(self) -> None:
        block, link = self.block(), self.link()
        drawings = [self.floating_drawing() for _ in range(2)]
        self.add_text(block, 'before ', link)
        block.add_image(drawings[0], link=link, floating=True)
        self.add_text(block, ' middle ', link)
        block.add_image(drawings[1], link=link, floating=True)
        self.add_text(block, ' after', link)
        block.serialize(self.body)
        hyperlinks = self.xpath('./w:p/w:hyperlink')
        self.assertEqual(len(hyperlinks), 1)
        self.assertEqual(self.xpath('./w:r/w:t/text()', hyperlinks[0]), ['before ', ' middle ', ' after'])
        self.assertEqual(self.xpath('./w:p/w:r/w:drawing'), drawings)
        self.assertEqual(len(self.xpath('.//wp:docPr/a:hlinkClick')), 2)

    def test_unsupported_scheme_is_logged(self) -> None:
        messages: list[str] = []
        self.links.log = cast('Log', SimpleNamespace(warn=messages.append))
        block = self.block()
        block.add_image(self.floating_drawing(), link=self.link('mailto:test@example.com'), floating=True)
        block.serialize(self.body)
        self.assertFalse(self.xpath('.//a:hlinkClick'))
        self.assertEqual(len(messages), 1)
        self.assertIn('mailto:test@example.com', messages[0])

    def test_image_runs_do_not_affect_language(self) -> None:
        block, link = self.block(), self.link()
        for _ in range(2):
            block.add_image(etree.Element(self.namespace.expand('w:drawing')), link=self.link())
        self.add_text(block, 'texte', link, lang='fr')
        blocks = Blocks(self.namespace, cast('StylesManager', SimpleNamespace(document_lang='en')), self.links)
        blocks.all_blocks.append(block)
        blocks.resolve_language()
        self.assertEqual(block.block_lang, 'fr')
        self.assertEqual([r.lang for r in block.runs], [None, None, None])

    def test_html_docx_html_roundtrip(self) -> None:
        from calibre.ebooks.conversion.plumber import Plumber

        source = '''<html><head><title>Hyperlinks</title></head><body>
        <p>Styled: <a href="https://example.com" title="Example">oddities linktext <span style="font-weight:bold">&amp;</span> ampersands</a> outside.</p>
        <p>Adjacent: <a href="https://example.com">one</a><a href="https://example.com">two</a></p>
        <p>Nested: <a href="https://example.com">one<span lang="it"><b>due</b></span>three</a></p>
        <p>Internal: <a href="#target">go <b>there</b></a></p>
        <p id="target">Destination</p>
        <p>Image: <a href="https://example.com"><img src="image.png" alt="image"/></a> after</p>
        <p>Floats: <a href="https://example.com/float" title="Tip"><img src="image.png" style="float:right"/></a>
        <a href="#target"><img src="image.png" style="float:left"/></a> around</p>
        <p>Wrapped: <a href="https://example.com/wrapped">before <img src="image.png" style="float:right"/> after</a></p>
        <table><tr><td><p>Cell one: <a href="https://example.com">one<b>two</b></a></p></td>
        <td><p>Cell two: <a href="https://example.com">three<b>four</b></a></p></td></tr></table>
        </body></html>'''
        with TemporaryDirectory() as tdir:
            base = Path(tdir)
            html, docx, htmlz = (base / name for name in ('input.html', 'output.docx', 'output.htmlz'))
            html.write_text(source, encoding='utf-8')
            (base / 'image.png').write_bytes(I('blank.png', data=True, allow_user_override=False))
            plumber = Plumber(str(html), str(docx), DevNull())
            plumber.merge_ui_recommendations([('docx_no_toc', True, 3), ('docx_no_cover', True, 3)])
            plumber.run()
            with ZipFile(docx) as zf:
                document = etree.fromstring(zf.read('word/document.xml'))
            paragraphs = {''.join(self.xpath('.//w:t/text()', p)).split(':')[0]: p for p in self.xpath('.//w:p', document)}
            for label, count in (
                ('Styled', 1),
                ('Adjacent', 2),
                ('Nested', 1),
                ('Internal', 1),
                ('Cell one', 1),
                ('Cell two', 1),
                ('Image', 1),
                ('Wrapped', 1),
            ):
                self.assertEqual(len(self.xpath('./w:hyperlink', paragraphs[label])), count, label)
            self.assertEqual(len(self.xpath('./w:hyperlink/w:r/w:drawing', paragraphs['Image'])), 1)
            self.assertFalse(self.xpath('//w:hyperlink//wp:anchor', document))
            self.assertEqual(len(self.xpath('//wp:anchor/wp:docPr/a:hlinkClick', document)), 3)
            self.assertEqual(self.xpath('./w:hyperlink/w:r/w:t/text()', paragraphs['Styled']), ['oddities linktext ', '&', ' ampersands'])
            plumber = Plumber(str(docx), str(htmlz), DevNull())
            plumber.merge_ui_recommendations([('docx_inline_subsup', True, 3)])
            plumber.run()
            with ZipFile(htmlz) as zf:
                result = etree.fromstring(zf.read('index.html'))
            paragraphs = {''.join(p.itertext()).split(':')[0]: p for p in result.iter('p')}
            for label, count in (
                ('Styled', 1),
                ('Adjacent', 2),
                ('Nested', 1),
                ('Internal', 1),
                ('Cell one', 1),
                ('Cell two', 1),
                ('Image', 1),
                ('Wrapped', 2),
            ):
                self.assertEqual(len(paragraphs[label].xpath('.//a')), count, label)
            self.assertEqual(len(paragraphs['Image'].xpath('.//a[@href="https://example.com"]//img')), 1)
            self.assertEqual(len(result.xpath('//a[@href="https://example.com/float" and @title="Tip"]/img')), 1)
            float_target = result.xpath('//a[starts-with(@href, "#")][img]/@href')
            self.assertEqual(len(float_target), 1)
            self.assertTrue(result.xpath('//*[@id=$target]', target=float_target[0][1:]))
            a = paragraphs['Styled'].find('a')
            assert a is not None
            self.assertEqual(''.join(a.itertext()), 'oddities linktext & ampersands')
            self.assertEqual(a.get('href'), 'https://example.com')
            self.assertEqual(a.get('title'), 'Example')
            self.assertEqual(''.join(paragraphs['Styled'].itertext()), 'Styled: oddities linktext & ampersands outside.')
            a = paragraphs['Internal'].find('a')
            assert a is not None
            href = a.get('href')
            assert href is not None
            self.assertTrue(href.startswith('#'))
            self.assertTrue(result.xpath('//*[@id=$target]', target=href[1:]))


class TestWhitespace(BaseTest):
    """Non-breaking spaces must survive HTML -> DOCX, see https://bugs.launchpad.net/calibre/+bug/2167710"""

    def texts(self, text: str, white_space: str = 'normal', ignore_leading_whitespace: bool = False) -> list:
        block = self.block()
        block.add_text(text, cast('Style', {'white-space': white_space}), ignore_leading_whitespace=ignore_leading_whitespace)
        block.serialize(self.body)
        return self.xpath('.//w:t/text()')

    def test_nbsp_is_not_collapsible_whitespace(self) -> None:
        for ch in ('\xa0', '\u2007', '\u202f'):
            with self.subTest(ch=ch):
                self.body.clear()
                self.assertEqual(self.texts(f'one{ch}two  three{ch}{ch}four'), [f'one{ch}two three{ch}{ch}four'])

    def test_leading_nbsp_is_preserved(self) -> None:
        # ignore_leading_whitespace must not eat a leading NBSP
        self.assertEqual(self.texts(' \t\n\xa0 indented', ignore_leading_whitespace=True), ['\xa0 indented'])

    def test_ascii_whitespace_is_still_collapsed(self) -> None:
        # In particular the form feed, which lxml refuses to serialize
        self.assertEqual(self.texts('one \t\r\n\f\vtwo'), ['one two'])

    def test_preserved_whitespace_is_untouched(self) -> None:
        self.assertEqual(self.texts('  one\xa0 two  ', white_space='pre'), ['  one\xa0 two  '])
        self.assertEqual(self.xpath('.//w:t/@xml:space'), ['preserve'])

    def test_html_docx_html_roundtrip(self) -> None:
        from calibre.ebooks.conversion.plumber import Plumber

        source = (
            '<html><head><title>Whitespace</title></head><body>'
            '<p>Inline: one&#160;two  three&#160;&#160;four</p>'
            '<p>&#160;Leading: indented</p>'
            '<p>Trailing: text&#160;</p>'
            '</body></html>'
        )
        with TemporaryDirectory() as tdir:
            base = Path(tdir)
            html, docx, htmlz = (base / name for name in ('input.html', 'output.docx', 'output.htmlz'))
            html.write_text(source, encoding='utf-8')
            plumber = Plumber(str(html), str(docx), DevNull())
            plumber.merge_ui_recommendations([('docx_no_toc', True, 3), ('docx_no_cover', True, 3)])
            plumber.run()
            with ZipFile(docx) as zf:
                document = etree.fromstring(zf.read('word/document.xml'))
            paragraphs = [''.join(self.xpath('.//w:t/text()', p)) for p in self.xpath('.//w:p', document)]
            self.assertIn('Inline: one\xa0two three\xa0\xa0four', paragraphs)
            self.assertIn('\xa0Leading: indented', paragraphs)
            self.assertIn('Trailing: text\xa0', paragraphs)
            plumber = Plumber(str(docx), str(htmlz), DevNull())
            plumber.merge_ui_recommendations([('docx_inline_subsup', True, 3)])
            plumber.run()
            with ZipFile(htmlz) as zf:
                # html5_parser rather than etree as the NBSP comes back as an &nbsp; entity
                result = parse(zf.read('index.html').decode('utf-8'))
            paragraphs = [''.join(p.itertext()) for p in result.iter('{*}p')]
            self.assertIn('Inline: one\xa0two three\xa0\xa0four', paragraphs)
            self.assertIn('\xa0Leading: indented', paragraphs)
            self.assertIn('Trailing: text\xa0', paragraphs)


class TestStyles(BaseTest):
    def test_html_docx_html_roundtrip(self) -> None:
        from calibre.ebooks.conversion.plumber import Plumber

        source = (
            '<html><head><title>Styles</title></head><body>'
            '<p>Spaced: <span style="letter-spacing: 2pt">wide</span> text</p>'
            '<p>Border: <span style="border: 1pt solid red">one</span><span style="border: 1pt solid red; font-weight: bold">two</span> after</p>'
            '</body></html>'
        )
        with TemporaryDirectory() as tdir:
            base = Path(tdir)
            html, docx, htmlz = (base / name for name in ('input.html', 'output.docx', 'output.htmlz'))
            html.write_text(source, encoding='utf-8')
            plumber = Plumber(str(html), str(docx), DevNull())
            plumber.merge_ui_recommendations([('docx_no_toc', True, 3), ('docx_no_cover', True, 3)])
            plumber.run()
            with ZipFile(docx) as zf:
                styles = etree.fromstring(zf.read('word/styles.xml'))
            self.assertIn('40', self.xpath('//w:rPr/w:spacing/@w:val', styles))
            plumber = Plumber(str(docx), str(htmlz), DevNull())
            plumber.run()
            with ZipFile(htmlz) as zf:
                result = etree.fromstring(zf.read('index.html'))
            wrappers = result.xpath('//*[local-name()="span" and starts-with(@class, "text_border")]')
            self.assertEqual(len(wrappers), 1)
            self.assertEqual(''.join(wrappers[0].itertext()), 'onetwo')

    def test_indent_chars_zero(self) -> None:
        # w:leftChars="0" next to w:left means use the twips value, as written by Word and calibre
        from calibre.ebooks.docx.block_styles import ParagraphStyle, read_indent

        w = self.namespace.namespaces['w']
        ppr = etree.fromstring(f'<w:pPr xmlns:w="{w}"><w:ind w:left="720" w:leftChars="0" w:firstLine="360" w:firstLineChars="0"/></w:pPr>')
        style = ParagraphStyle(self.namespace)
        read_indent(ppr, style, self.namespace.XPath, self.namespace.get)
        self.assertEqual((style.margin_left, style.text_indent), ('36pt', '18pt'))
        ppr = etree.fromstring(f'<w:pPr xmlns:w="{w}"><w:ind w:left="720" w:leftChars="200"/></w:pPr>')
        style = ParagraphStyle(self.namespace)
        read_indent(ppr, style, self.namespace.XPath, self.namespace.get)
        self.assertEqual(style.margin_left, '2em')

    def test_numbering_overrides(self) -> None:
        from calibre.ebooks.docx.numbering import Numbering

        w = self.namespace.namespaces['w']
        root = etree.fromstring(f'''<w:numbering xmlns:w="{w}">
        <w:abstractNum w:abstractNumId="0">
        <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/></w:lvl>
        <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/></w:lvl>
        </w:abstractNum>
        <w:num w:numId="1"><w:abstractNumId w:val="0"/>
        <w:lvlOverride w:ilvl="0"><w:startOverride w:val="5"/></w:lvlOverride>
        <w:lvlOverride w:ilvl="1"><w:startOverride w:val="7"/></w:lvlOverride>
        <w:lvlOverride><w:lvl w:ilvl="2"><w:start w:val="3"/><w:numFmt w:val="upperRoman"/></w:lvl></w:lvlOverride>
        </w:num></w:numbering>''')
        numbering = Numbering(self.namespace)
        styles = cast('Styles', SimpleNamespace(numbering_style_links={}))  # only numbering_style_links is used
        numbering(root, styles, {})
        self.assertEqual(numbering.starts['1'], {0: 5, 1: 7, 2: 3})
        self.assertEqual(numbering.instances['1'].levels[2].fmt, 'upper-roman')


def find_tests() -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    return unittest.TestSuite(loader.loadTestsFromTestCase(cls) for cls in (TestHyperlinks, TestWhitespace, TestStyles))
