# License: GPLv3 Copyright: 2026

"""Run with calibre-debug -e src/calibre/ebooks/pdf/diagrams_test.py."""

import os
import tempfile
import unittest
from pathlib import Path

from lxml import etree

try:
    import pymupdf as pdf
except ImportError:
    pdf = None

from calibre import CurrentDir
from calibre.ebooks.pdf.diagrams import diagram_regions, preserve_diagrams
from calibre.ebooks.pdf.pdftohtml import pdftohtml
from calibre.ebooks.pdf.reflow import Image
from calibre.utils.logging import default_log


@unittest.skipUnless(pdf is not None and hasattr(pdf.Page, 'clip_to_rect'), 'Requires recent PyMuPDF')
class TestPDFDiagrams(unittest.TestCase):

    def test_svg_replaces_labels_before_reflow(self):
        with tempfile.TemporaryDirectory() as work, CurrentDir(work), pdf.open() as document:
            page = document.new_page(width=400, height=400)
            page.insert_text((60, 75), 'Prose above the diagrams.')
            for top in (100, 220):
                page.draw_rect((100, top, 160, top + 60))
                page.draw_line((80, top + 30), (100, top + 30))
                page.draw_line((160, top + 30), (180, top + 30))
                page.insert_text((65, top + 34), '25')
                page.insert_text((110, top + 34), 'SQRT')
                page.insert_text((185, top + 34), '5.0')
            page.insert_text((60, 195), 'Prose between the diagrams.')
            page.draw_line((20, 320), (350, 320))
            page.draw_rect((5, 5, 15, 15))
            regions = diagram_regions(page)
            self.assertEqual(len(regions), 2)
            for region in regions:
                self.assertEqual(set(page.get_text(clip=region).split()), {'25', 'SQRT', '5.0'})
            document.save('source.pdf')
            pdftohtml(work, os.path.join(work, 'source.pdf'), False, as_xml=True)
            original = Path('index.xml').read_bytes()
            result = preserve_diagrams('source.pdf', original, work, default_log)
            root = etree.fromstring(result)
            self.assertEqual(len(root.findall('.//image')), 2)
            self.assertEqual(''.join(root.itertext()).count('SQRT'), 0)
            self.assertIn('Prose above the diagrams.', ''.join(root.itertext()))
            self.assertIn('Prose between the diagrams.', ''.join(root.itertext()))
            for image in root.findall('.//image'):
                page_xml = image.getparent()
                img = Image(image, float(page_xml.get('width')), float(page_xml.get('height')),
                            None, default_log, iter(range(10)))
                html_image = etree.fromstring(img.to_html())
                self.assertIn('display:block', html_image.get('style'))
                self.assertIn('SQRT', html_image.get('alt'))
                data = Path(image.get('src')).read_bytes()
                svg = etree.fromstring(data)
                self.assertTrue(svg.tag.endswith('}svg'))
                self.assertTrue(svg.findall('.//{http://www.w3.org/2000/svg}path'))
                # No bitmap fallback, and no unrelated page content in the SVG.
                self.assertFalse(svg.findall('.//{http://www.w3.org/2000/svg}image'))
                self.assertLess(len(data), 20000)

    def test_rotated_page_is_left_alone(self):
        with tempfile.TemporaryDirectory() as work, pdf.open() as document:
            page = document.new_page(width=400, height=400)
            page.draw_rect((100, 100, 160, 160))
            page.set_rotation(90)
            source = os.path.join(work, 'rotated.pdf')
            document.save(source)
            original = b'<pdf2xml><page number="1" width="600" height="600"><text top="1" left="1" width="3" height="4">Keep</text></page></pdf2xml>'
            result = preserve_diagrams(source, original, work, default_log)
            root = etree.fromstring(result)
            self.assertEqual(root.find('.//text').text, 'Keep')
            self.assertFalse(root.findall('.//image'))


if __name__ == '__main__':
    unittest.main(module='calibre.ebooks.pdf.diagrams_test')
