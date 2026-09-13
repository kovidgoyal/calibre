#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from zipfile import ZipFile

from lxml import etree

from calibre.ebooks.docx.names import DOCXNamespace
from calibre.ebooks.docx.writer.container import DocumentRelationships
from calibre.ebooks.docx.writer.from_html import Block, TextRun
from calibre.ebooks.docx.writer.links import LinksManager
from calibre.utils.logging import DevNull


class TestHyperlinks(unittest.TestCase):
    def setUp(self):
        self.namespace = DOCXNamespace()
        self.relationships = DocumentRelationships(self.namespace)
        self.links = LinksManager(self.namespace, self.relationships, DevNull())
        self.item = SimpleNamespace(abshref=lambda href: href or 'test.html')
        self.body = etree.Element(self.namespace.expand('w:body'))

    def link(self, url='https://example.com', tooltip=None):
        return self.item, url, tooltip

    def block(self):
        styles = SimpleNamespace(create_block_style=lambda *args, **kwargs: SimpleNamespace(id=None))
        styles.create_text_style = lambda style, **kwargs: style.get('font-weight', 'normal')
        style = {'page-break-before': 'auto', 'page-break-inside': 'auto'}
        return Block(self.namespace, styles, self.links, etree.Element('p'), style)

    def add_text(self, block, text, link=None, bold=False, lang=None, bookmark=None):
        style = {'white-space': 'normal', 'font-weight': 'bold' if bold else 'normal'}
        block.add_text(text, style, link=link, lang=lang, bookmark=bookmark)
        block.runs[-1].descendant_style = SimpleNamespace(id='Bold' if bold else 'Normal')

    def xpath(self, expression, root=None):
        return self.namespace.XPath(expression)(self.body if root is None else root)

    def test_styled_hyperlink(self):
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

    def test_distinct_source_anchors(self):
        for second in (self.link(), self.link(tooltip='Different'), self.link(url='https://example.org')):
            with self.subTest(second=second):
                self.body.clear()
                block = self.block()
                self.add_text(block, 'one', self.link())
                self.add_text(block, 'two', second)
                self.assertEqual(len(block.runs), 2)
                block.serialize(self.body)
                self.assertEqual(len(self.xpath('./w:p/w:hyperlink')), 2)

    def test_link_interrupted_by_plain_text(self):
        block, link = self.block(), self.link()
        self.add_text(block, 'one', link)
        self.add_text(block, ' between ')
        self.add_text(block, 'two', link)
        block.serialize(self.body)
        self.assertEqual(len(self.xpath('./w:p/w:hyperlink')), 2)
        self.assertEqual(self.xpath('./w:p/w:r/w:t/text()'), [' between '])

    def test_separate_blocks(self):
        link = self.link()
        for parent in (self.body, self.namespace.makeelement(self.body, 'w:tc')):
            for text in ('one', 'two'):
                block = self.block()
                self.add_text(block, text, link)
                self.add_text(block, ' bold', link, bold=True)
                block.serialize(parent)
        self.assertEqual(len(self.xpath('.//w:p/w:hyperlink')), 4)
        self.assertTrue(all(len(self.xpath('./w:hyperlink', p)) == 1 for p in self.xpath('.//w:p')))

    def test_internal_link_and_fallback(self):
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

    def test_run_contents_and_legacy_serialization(self):
        block, link = self.block(), self.link()
        self.add_text(block, 'one', link, bookmark='bookmark')
        block.add_break()
        drawing = etree.Element(self.namespace.expand('w:drawing'))
        block.add_image(drawing)
        self.add_text(block, 'two', link, bold=True)
        block.serialize(self.body)
        self.assertEqual(len(self.xpath('./w:p/w:hyperlink')), 1)
        self.assertEqual(len(self.xpath('./w:p/w:hyperlink/w:r/w:br')), 1)
        self.assertEqual(self.xpath('./w:p/w:hyperlink/w:r/w:drawing'), [drawing])
        self.assertEqual(self.xpath('.//w:bookmarkStart/@w:name'), ['bookmark'])
        self.assertEqual(self.xpath('.//w:bookmarkStart/@w:id'), self.xpath('.//w:bookmarkEnd/@w:id'))
        p = self.namespace.makeelement(self.body, 'w:p')
        run = TextRun(self.namespace, None, None)
        run.add_text('legacy', False, link=link)
        run.serialize(p, self.links)
        self.assertEqual(self.xpath('./w:hyperlink/w:r/w:t/text()', p), ['legacy'])

    def test_html_docx_html_roundtrip(self):
        from calibre.ebooks.conversion.plumber import Plumber

        source = '''<html><head><title>Hyperlinks</title></head><body>
        <p>Styled: <a href="https://example.com" title="Example">oddities linktext <span style="font-weight:bold">&amp;</span> ampersands</a> outside.</p>
        <p>Adjacent: <a href="https://example.com">one</a><a href="https://example.com">two</a></p>
        <p>Nested: <a href="https://example.com">one<span lang="it"><b>due</b></span>three</a></p>
        <p>Internal: <a href="#target">go <b>there</b></a></p>
        <p id="target">Destination</p>
        <table><tr><td><p>Cell one: <a href="https://example.com">one<b>two</b></a></p></td>
        <td><p>Cell two: <a href="https://example.com">three<b>four</b></a></p></td></tr></table>
        </body></html>'''
        with TemporaryDirectory() as tdir:
            base = Path(tdir)
            html, docx, htmlz = (base / name for name in ('input.html', 'output.docx', 'output.htmlz'))
            html.write_text(source, encoding='utf-8')
            plumber = Plumber(str(html), str(docx), DevNull())
            plumber.merge_ui_recommendations([('docx_no_toc', True, 3), ('docx_no_cover', True, 3)])
            plumber.run()
            with ZipFile(docx) as zf:
                document = etree.fromstring(zf.read('word/document.xml'))
            paragraphs = {''.join(self.xpath('.//w:t/text()', p)).split(':')[0]: p for p in self.xpath('.//w:p', document)}
            for label, count in (('Styled', 1), ('Adjacent', 2), ('Nested', 1), ('Internal', 1), ('Cell one', 1), ('Cell two', 1)):
                self.assertEqual(len(self.xpath('./w:hyperlink', paragraphs[label])), count, label)
            self.assertEqual(self.xpath('./w:hyperlink/w:r/w:t/text()', paragraphs['Styled']), ['oddities linktext ', '&', ' ampersands'])
            plumber = Plumber(str(docx), str(htmlz), DevNull())
            plumber.merge_ui_recommendations([('docx_inline_subsup', True, 3)])
            plumber.run()
            with ZipFile(htmlz) as zf:
                result = etree.fromstring(zf.read('index.html'))
            paragraphs = {''.join(p.itertext()).split(':')[0]: p for p in result.iter('p')}
            for label, count in (('Styled', 1), ('Adjacent', 2), ('Nested', 1), ('Internal', 1), ('Cell one', 1), ('Cell two', 1)):
                self.assertEqual(len(paragraphs[label].xpath('.//a')), count, label)
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


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestHyperlinks)
