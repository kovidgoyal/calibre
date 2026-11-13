# License: GPLv3 Copyright: 2026

"""Run with calibre-debug -e src/calibre/ebooks/pdf/pdftohtml_test.py."""

import tempfile
import unittest

from lxml import etree

from calibre import CurrentDir
from calibre.ebooks.pdf.pdftohtml import parse_outline
from calibre.ebooks.pdf.reflow import PDFDocument


class TestMissingDestinations(unittest.TestCase):

    def test_page_anchor_survives_paragraph_unwrapping(self):
        from calibre.ebooks.conversion.utils import HeuristicProcessor
        from calibre.ebooks.pdf.reflow_test import build
        from calibre.utils.logging import default_log

        page = build([(10, 10, 400, 'the continuation on the next page')])
        html = '<p>The previous page ends in the middle of a sentence</p>' + ''.join(page.to_html())
        unwrapped = HeuristicProcessor(None, default_log).punctuation_unwrap(5, html, 'html')
        self.assertEqual(unwrapped.count('<p>'), 1)
        self.assertIn('<a id="page_1"></a>', unwrapped)
        self.assertIn('the continuation on the next page', unwrapped)

    def test_empty_parents_do_not_adopt_unrelated_siblings(self):
        raw = b'''<pdf2xml><outline>
          <item page="1">First</item><item>Unresolved</item>
          <outline><item page="2">Resolved child</item></outline>
          <item page="3">Third</item>
        </outline></pdf2xml>'''
        with tempfile.TemporaryDirectory() as work, CurrentDir(work):
            for engine, title in ((e, t) for e in ('calibre', 'pdftohtml') for t in (b'Unresolved', b'')):
                current = raw.replace(b'Unresolved', title)
                with self.subTest(engine=engine, title=title):
                    if engine == 'calibre':
                        document = PDFDocument.__new__(PDFDocument)
                        document.root = etree.fromstring(current)
                        document.generate_toc()
                        prefix = 'page_'
                    else:
                        parse_outline(current, work)
                        prefix = 'p'
                    root = etree.parse('toc.ncx')
                    ns = {'n': 'http://www.daisy.org/z3986/2005/ncx/'}
                    points = root.findall('n:navMap/n:navPoint', ns)
                    # A titled parent retains the existing page-1 fallback.
                    # An empty parent hoists its child, not under First.
                    self.assertEqual(len(points), 3)
                    pages = (1, 1, 3) if title else (1, 2, 3)
                    self.assertEqual([p.find('n:content', ns).get('src') for p in points],
                                     [f'index.html#{prefix}{i}' for i in pages])
                    if title:
                        child = points[1].find('n:navPoint/n:content', ns)
                        self.assertIsNotNone(child)
                        self.assertEqual(child.get('src'), f'index.html#{prefix}2')

    def test_consumed_page_keeps_its_anchor(self):
        from calibre.ebooks.pdf.reflow_test import TestPageBoundaries
        fixture = TestPageBoundaries()
        first = [(337, 223 + i * 35, 1100, f'A sufficiently long wrapped body line continuing with word {i}', 0) for i in range(28)]
        second = [(337, 223, 1100, 'and a continuation that occupies all text on the next page.', 0)]
        root = etree.fromstring(fixture.convert([first, second]).encode())
        self.assertEqual(len(root.xpath('//*[@id="page_2"]')), 1)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestMissingDestinations)


if __name__ == '__main__':
    unittest.main(module='calibre.ebooks.pdf.pdftohtml_test')
