# License: GPLv3
import os
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch

from calibre.ebooks.metadata.djvu import find_ddjvu, get_metadata, page_images


class DjvuCoverTest(unittest.TestCase):
    def test_pdf_cover_preferred_when_importing_pair(self):
        from calibre.ebooks.metadata import MetaInformation
        from calibre.ebooks.metadata.meta import metadata_from_formats

        with tempfile.TemporaryDirectory() as work:
            for djvu_ext in ('djvu', 'djv'):
                paths = [os.path.join(work, 'Journal.' + ext) for ext in ('pdf', djvu_ext)]
                for path in paths:
                    with open(path, 'wb'):
                        pass
                for reverse in (False, True):
                    for pdf_cover in (b'pdf', None):
                        def read_metadata(stream, stream_type, **kwargs):
                            mi = MetaInformation('Journal', ['Author'])
                            mi.cover_data = ('jpeg', pdf_cover if stream_type == 'pdf' else b'larger djvu cover')
                            return mi

                        with patch('calibre.ebooks.metadata.meta.get_metadata', side_effect=read_metadata):
                            mi = metadata_from_formats(list(reversed(paths)) if reverse else list(paths))
                        self.assertEqual(mi.cover_data[1], pdf_cover or b'larger djvu cover')

    def test_quick_read_does_not_render(self):
        with patch('calibre.ebooks.metadata.djvu.page_images') as render:
            self.assertIsNone(get_metadata(BytesIO(b''), cover=False).cover_data[1])
            render.assert_not_called()

    def test_invalid_tool_override(self):
        with patch.dict(os.environ, {'CALIBRE_DDJVU': '/missing/ddjvu'}):
            with self.assertRaises(FileNotFoundError):
                find_ddjvu()

    def test_invalid_page_range(self):
        with self.assertRaises(ValueError):
            page_images('unused', 'unused', first=0)

    @unittest.skipUnless(os.environ.get('CALIBRE_TEST_DJVU'), 'Set CALIBRE_TEST_DJVU to a sample journal')
    def test_real_journal(self):
        from qt.core import QImage

        from calibre.ebooks.metadata.meta import get_metadata as read_metadata

        path = os.environ['CALIBRE_TEST_DJVU']
        with open(path, 'rb') as stream:
            mi = read_metadata(stream, 'djvu')
        self.assertEqual(mi.cover_data[0], 'jpeg')
        self.assertFalse(QImage.fromData(mi.cover_data[1]).isNull())
        with tempfile.TemporaryDirectory() as out:
            pages = page_images(path, out, first=1, last=10)
            self.assertEqual(len(pages), 10)
            with open(pages[0], 'rb') as stream:
                self.assertEqual(stream.read(), mi.cover_data[1])
            more = page_images(path, out, first=11, last=20)
            self.assertEqual(len(more), 10)
            self.assertTrue(set(pages).isdisjoint(more))
            self.assertEqual(page_images(path, out, first=10000, last=10009), [])
        with tempfile.TemporaryDirectory() as out:
            bad = os.path.join(out, 'invalid.djvu')
            with open(bad, 'wb') as stream:
                stream.write(b'not a DjVu')
            with self.assertRaises(ValueError):
                page_images(bad, out)
