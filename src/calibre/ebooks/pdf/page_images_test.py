#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Omaralsaabi

"""
Tests for the images engine of PDF Input, which turns every page of the PDF
into an image, instead of extracting its text
"""

import os
import re
import unittest
from zipfile import ZipFile

from calibre.ebooks.conversion.plugins.pdf_input import PAGE_IMAGE_SIZE
from calibre.ebooks.metadata.pdf import get_tools, page_images
from calibre.ebooks.pdf.pdftohtml_test import BODY, FULL_PAGE_IMAGE, make_pdf
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.imghdr import identify


@unittest.skipUnless(os.path.exists(get_tools()[1]), 'pdftoppm is not available')
class TestPageImages(unittest.TestCase):
    def test_page_images_renders_all_pages_when_last_is_none(self) -> None:
        with TemporaryDirectory() as tdir:
            src = os.path.join(tdir, 'test.pdf')
            make_pdf(src, [BODY, FULL_PAGE_IMAGE, BODY])
            page_images(src, tdir, last=None, prefix='page')
            self.assertEqual(sorted(x for x in os.listdir(tdir) if x.endswith('.jpg')), ['page-1.jpg', 'page-2.jpg', 'page-3.jpg'])

    def test_page_images_are_scaled_so_that_their_longer_side_has_the_given_size(self) -> None:
        with TemporaryDirectory() as tdir:
            src = os.path.join(tdir, 'test.pdf')
            make_pdf(src, [BODY])
            page_images(src, tdir, prefix='page', scale_to=500)
            with open(os.path.join(tdir, 'page-1.jpg'), 'rb') as f:
                width, height = identify(f)[1:]
            # The pages of the PDF are 612x792 points
            self.assertEqual(height, 500)
            self.assertAlmostEqual(width, 500 * 612 / 792, delta=1)

    def test_every_page_becomes_a_page_of_the_book_showing_its_image(self) -> None:
        from calibre.ebooks.conversion.plumber import Plumber
        from calibre.utils.logging import DevNull

        with TemporaryDirectory() as tdir:
            # A non-ASCII file name, as the PDF is passed to pdftoppm on the command line
            src = os.path.join(tdir, 'كتاب.pdf')
            dest = os.path.join(tdir, 'book.epub')
            make_pdf(src, [BODY, FULL_PAGE_IMAGE, BODY])
            plumber = Plumber(src, dest, DevNull())
            plumber.merge_ui_recommendations([('pdf_engine', 'images', 3), ('language', 'ar', 3)])
            plumber.run()
            with ZipFile(dest) as zf:
                names = set(zf.namelist())
                opf = zf.read('content.opf').decode('utf-8')
                pages = {name: zf.read(name).decode('utf-8') for name in names if name.endswith('.xhtml')}
                images = {name: identify(zf.read(name))[1:] for name in names if name.endswith('.jpg')}

        self.assertTrue(plumber.input_plugin.is_image_collection)
        self.assertNotIn('src.pdf', names)
        # One page for each page of the PDF in order, with no cover page added before them
        ids = dict(re.findall(r'<item id="([^"]+)" href="([^"]+)"', opf))
        spine = [ids[x] for x in re.findall(r'<itemref idref="([^"]+)"', opf)]
        self.assertEqual(spine, ['page-1.xhtml', 'page-2.xhtml', 'page-3.xhtml'])
        self.assertEqual(sorted(images), ['page-1.jpg', 'page-2.jpg', 'page-3.jpg'])
        # The image of the first page is the cover
        self.assertEqual(re.search(r'<meta name="cover" content="([^"]+)"', opf).group(1), 'cover')
        self.assertEqual(ids['cover'], 'page-1.jpg')
        # Right to left books turn their pages from right to left
        self.assertIn('page-progression-direction="rtl"', opf)
        for i in range(1, 4):
            page, img = pages[f'page-{i}.xhtml'], f'page-{i}.jpg'
            width, height = images[img]
            self.assertEqual(max(width, height), PAGE_IMAGE_SIZE)
            # The image is scaled to fit the screen, keeping its aspect ratio, so no part of the page is cut off
            self.assertIn(f'viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet"', page)
            self.assertIn(f'<image width="{width}" height="{height}" xlink:href="{img}"/>', page)
            # No text is extracted from the PDF
            self.assertNotIn('body text', page)


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestPageImages)


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=4).run(find_tests())
