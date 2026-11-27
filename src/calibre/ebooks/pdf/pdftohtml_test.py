#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Tests for extracting the invisible text of the scanned pages of searchable
PDFs made by OCR programs, see OCR_PAGE_MAX_VISIBLE_CHARS
"""

import os
import re
import shutil
import unittest
from typing import TYPE_CHECKING, Unpack
from unittest.mock import patch

from calibre.ebooks.pdf import pdftohtml as mod
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.podofo import get_page_content_stats

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Sequence

    from calibre.type_hints import PopenKwargs

# Draws an image covering the whole page, as of a scanned page
FULL_PAGE_IMAGE = 'q 612 0 0 792 0 0 cm /Im1 Do Q\n'
# The footer that some libraries add to every page of the PDFs they provide
WATERMARK = 'BT 0 Tr /F1 8 Tf 60 20 Td (Downloaded from example.org) Tj ET\n'
COVER = 'BT 0 Tr /F1 30 Tf 100 600 Td (Visible Cover Title) Tj ET\n'


def lines(count: int, word: str, invisible: bool) -> str:
    # Lines of text, drawn with text render mode 3, which is invisible, as OCR
    # programs draw their text, if invisible
    mode = 3 if invisible else 0
    return ''.join(f'BT {mode} Tr /F1 11 Tf 60 {740 - i * 16} Td (Line {i} of the {word} text of this page.) Tj ET\n' for i in range(count))


SCANNED = FULL_PAGE_IMAGE + lines(30, 'scanned', True)
BODY = lines(30, 'body', False)


def make_pdf(path: str, pages: Sequence[str], outline_page: int = 0) -> None:
    """
    Write a PDF whose pages are drawn by the content streams in pages, which
    can use the font F1, the 2x2 image Im1, and the form Fm1, which draws Im1
    over the left half of the unit square. With an entry in its outline for
    outline_page, if not 0.
    """
    first_page = 8
    objs: dict[int, bytes] = {
        1: b'<< /Type /Catalog /Pages 2 0 R /Outlines 6 0 R >>' if outline_page else b'<< /Type /Catalog /Pages 2 0 R >>',
        2: b'<< /Type /Pages /Kids [%s] /Count %d >>' % (b' '.join(b'%d 0 R' % (first_page + 2 * i + 1) for i in range(len(pages))), len(pages)),
        3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        4: b'<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray /BitsPerComponent 8 /Length 4 >>\n'
        b'stream\n\x80\x90\xa0\xb0\nendstream',
        5: b'<< /Type /XObject /Subtype /Form /BBox [0 0 1 1] /Matrix [0.5 0 0 1 0 0]'
        b' /Resources << /XObject << /Im1 4 0 R >> >> /Length 7 >>\n'
        b'stream\n/Im1 Do\nendstream',
        6: b'<< /Type /Outlines /First 7 0 R /Last 7 0 R /Count 1 >>',
        7: b'<< /Title (The Chapter) /Parent 6 0 R /Dest [%d 0 R /XYZ 0 792 0] >>' % (first_page + 2 * max(0, outline_page - 1) + 1),
    }
    for i, content in enumerate(pages):
        c = content.encode('ascii')
        objs[first_page + 2 * i] = b'<< /Length %d >>\nstream\n%s\nendstream' % (len(c), c)
        objs[first_page + 2 * i + 1] = (
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> /XObject << /Im1 4 0 R /Fm1 5 0 R >> >>'
            b' /Contents %d 0 R >>' % (first_page + 2 * i)
        )
    out = b'%PDF-1.4\n'
    offsets: dict[int, int] = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += b'%d 0 obj\n%s\nendobj\n' % (num, objs[num])
    xref = len(out)
    size = max(objs) + 1
    out += b'xref\n0 %d\n0000000000 65535 f \n' % size
    out += b''.join(b'%010d 00000 n \n' % offsets[n] for n in range(1, size))
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, xref)
    with open(path, 'wb') as f:
        f.write(out)


class TestPageContentStats(unittest.TestCase):
    def stats(self, *pages: str) -> list[tuple[int, int, float] | None]:
        with TemporaryDirectory() as tdir:
            path = os.path.join(tdir, 'test.pdf')
            make_pdf(path, pages)
            return get_page_content_stats(path)

    def test_visible_and_invisible_text(self) -> None:
        visible, invisible, coverage = self.stats('BT /F1 12 Tf (abc) Tj ET BT 3 Tr [(de) -200 (f)] TJ ET')[0] or (0, 0, 0)
        self.assertEqual((visible, invisible, coverage), (3, 3, 0))

    def test_render_mode_lasts_beyond_text_objects_until_restored(self) -> None:
        # The text rendering mode is part of the graphics state, not of the text object
        page = 'q BT 3 Tr /F1 12 Tf (ab) Tj ET BT (cd) Tj ET Q BT /F1 12 Tf (efg) Tj ET'
        self.assertEqual(self.stats(page)[0], (3, 4, 0))

    def test_image_coverage(self) -> None:
        stats = self.stats(FULL_PAGE_IMAGE, 'q 306 0 0 792 0 0 cm /Im1 Do Q', FULL_PAGE_IMAGE * 2, '')
        self.assertEqual([round(s[2], 3) if s else None for s in stats], [1, 0.5, 2, 0])

    def test_image_in_form_is_transformed_by_the_matrix_of_the_form(self) -> None:
        stats = self.stats('q 612 0 0 792 0 0 cm /Fm1 Do Q')
        self.assertEqual(round((stats[0] or (0, 0, 0))[2], 3), 0.5)


@unittest.skipUnless(shutil.which(mod.PDFTOHTML) and shutil.which(mod.PDFTOTEXT), 'pdftohtml or pdftotext is not available')
class TestInvisibleText(unittest.TestCase):
    def convert(self, pages: Sequence[str], as_xml: bool = True, outline_page: int = 0) -> tuple[list[str], list[str], list[list[str]], str]:
        """
        Convert a PDF with pages drawn by the PDF content in pages, returning
        the output for each page, the names of the images extracted, the
        commands run, and the whole output
        """
        commands: list[list[str]] = []
        original_popen = mod.popen

        def spy(cmd: Sequence[str], **kw: Unpack[PopenKwargs]) -> subprocess.Popen[bytes]:
            commands.append([os.path.basename(cmd[0]).partition('.')[0], *cmd[1:]])
            return original_popen(cmd, **kw)

        with TemporaryDirectory() as tdir, patch.object(mod, 'popen', spy), patch.object(mod, 'prints'):
            src = os.path.join(tdir, 'test.pdf')
            make_pdf(src, pages, outline_page)
            out = os.path.join(tdir, 'out')
            os.mkdir(out)
            mod.pdftohtml(out, src, False, as_xml=as_xml)
            index = 'index.' + ('xml' if as_xml else 'html')
            with open(os.path.join(out, index), encoding='utf-8') as f:
                raw = f.read()
            images = sorted(x for x in os.listdir(out) if x != index)
        if as_xml:
            return re.findall(r'<page [^>]*/>|<page .*?</page>', raw, flags=re.S), images, commands, raw
        return re.split(r'<a id="p\d+"></a>', raw)[1:], images, commands, raw

    def page_ranges_run(self, commands: list[list[str]]) -> list[str]:
        # The pages that pdftohtml was run for, other than to read the outline
        ans = []
        for cmd in commands:
            if cmd[0] == 'pdftohtml' and '-stdout' not in cmd:
                ans.append(f'{cmd[cmd.index("-f") + 1]}-{cmd[cmd.index("-l") + 1]}' if '-f' in cmd else 'all')
        return ans

    def test_scanned_pages_of_a_pdf_with_a_visible_cover_get_their_text(self) -> None:
        pages, images, commands, raw = self.convert([COVER, SCANNED, SCANNED, FULL_PAGE_IMAGE + BODY], outline_page=3)
        self.assertEqual(len(pages), 4)
        self.assertIn('Visible Cover Title', pages[0])
        for page in pages[1:3]:
            self.assertEqual(page.count('scanned text'), 30)
        self.assertEqual(pages[3].count('body text'), 30)
        # pdftohtml is run only for the pages that are not scanned, so the
        # images of the scanned pages are not extracted
        self.assertEqual(self.page_ranges_run(commands), ['1-1', '4-4'])
        self.assertTrue(images)
        self.assertFalse([x for x in images if re.search(r'-[23]_\d+\.', x)])
        # The outline is kept once
        self.assertIn('<item page="3">The Chapter</item>', raw)
        self.assertEqual(raw.count('<outline>'), 1)
        # Every font is defined once
        ids = re.findall(r'<fontspec id="(\d+)"', raw)
        self.assertEqual(sorted(ids), sorted(set(ids)))
        for font in re.findall(r'<text [^>]*font="(\d+)"', raw):
            self.assertIn(font, ids)

    def test_visible_watermark_does_not_hide_the_text_of_scanned_pages(self) -> None:
        pages, images, commands, raw = self.convert([SCANNED + WATERMARK] * 3)
        for page in pages:
            self.assertEqual(page.count('scanned text'), 30)
            self.assertEqual(page.count('Downloaded from'), 1)
        self.assertEqual(self.page_ranges_run(commands), [])
        self.assertEqual(images, [])

    def test_invisible_copy_of_visible_text_is_not_duplicated(self) -> None:
        pages, images, commands, raw = self.convert([FULL_PAGE_IMAGE + lines(8, 'visible', False) + lines(8, 'visible', True)] * 2)
        for page in pages:
            self.assertEqual(page.count('visible text'), 8)
        self.assertEqual(self.page_ranges_run(commands), ['all'])

    def test_pdf_with_visible_text_is_converted_as_before(self) -> None:
        pages, images, commands, raw = self.convert([BODY, 'BT /F1 30 Tf 100 600 Td (Chapter One) Tj ET\n', '', BODY])
        self.assertEqual([c[0] for c in commands if '-stdout' not in c], ['pdftohtml'])
        self.assertEqual(self.page_ranges_run(commands), ['all'])
        self.assertEqual(pages[0].count('body text'), 30)

    def test_images_of_page_with_invisible_text_that_is_not_scanned_are_extracted(self) -> None:
        pages, images, commands, raw = self.convert(['q 200 0 0 200 0 0 cm /Im1 Do Q\n' + lines(30, 'scanned', True)])
        self.assertEqual(self.page_ranges_run(commands), ['all'])
        self.assertTrue(images)
        self.assertEqual(pages[0].count('scanned text'), 30)

    def test_html_engine_uses_invisible_text_when_most_pages_are_scanned(self) -> None:
        pages, images, commands, raw = self.convert([COVER, SCANNED, SCANNED], as_xml=False)
        self.assertEqual(sum(page.count('scanned text') for page in pages), 60)
        self.assertIn('Visible Cover Title', pages[0])
        pages, images, commands, raw = self.convert([BODY, BODY, BODY, SCANNED], as_xml=False)
        self.assertEqual(sum(page.count('scanned text') for page in pages), 0)

    def test_failure_of_pdftotext_uses_invisible_text_of_all_pages(self) -> None:
        with patch.object(mod, 'PDFTOTEXT', mod.PDFTOTEXT + '-does-not-exist'):
            pages, images, commands, raw = self.convert([COVER, SCANNED, SCANNED])
        self.assertEqual(self.page_ranges_run(commands), ['all'])
        self.assertIn('Visible Cover Title', pages[0])
        self.assertEqual(sum(page.count('scanned text') for page in pages), 60)

    def test_page_ranges(self) -> None:
        self.assertEqual(mod.page_ranges([5, 1, 2, 3]), [(1, 3), (5, 5)])
        self.assertEqual(mod.page_ranges([1, 11, 22], max_gap=10), [(1, 11), (22, 22)])
        self.assertEqual(mod.page_ranges([]), [])


def find_tests() -> unittest.TestSuite:
    return unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(x) for x in (TestPageContentStats, TestInvisibleText)])


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=4).run(find_tests())
