# License: GPLv3
import os
import tempfile
import unittest

from calibre.ebooks.djvu.convert import djvu_tool, get_tools, parse_text, run


class ConversionTest(unittest.TestCase):
    def test_text_parser(self):
        tree = parse_text('(page 0 0 100 100 (word 1 2 30 40 "Радио \\"тест\\""))')
        self.assertEqual(tree[0][5][5], 'Радио "тест"')
        with self.assertRaises(ValueError):
            parse_text('(page')

    def test_pdf_djvu_roundtrip(self):
        try:
            djvu_tool('ddjvu')
        except FileNotFoundError:
            self.skipTest('DjVuLibre is not installed')

        from qt.core import QFont, QImage, QMarginsF, QPageLayout, QPageSize, QPainter, QPdfWriter

        from calibre.ebooks.conversion.plumber import Plumber
        from calibre.gui2 import must_use_qt
        from calibre.utils.logging import default_log

        must_use_qt()
        with tempfile.TemporaryDirectory() as work:
            source = os.path.join(work, 'original.pdf')
            djvu = os.path.join(work, 'converted.djvu')
            pdf = os.path.join(work, 'roundtrip.pdf')
            writer = QPdfWriter(source)
            writer.setResolution(150)
            writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A5), QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)))
            painter = QPainter(writer)
            painter.setFont(QFont('Arial', 18))
            painter.drawText(70, 100, 'Radio 1980 — Проверка текста')
            writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A5), QPageLayout.Orientation.Landscape, QMarginsF(0, 0, 0, 0)))
            writer.newPage()
            painter.drawText(70, 100, 'Second page — Вторая страница')
            writer.newPage()
            painter.drawRect(70, 70, 150, 150)  # A page without a text layer.
            painter.end()
            del writer
            Plumber(source, djvu, default_log).run()
            self.assertEqual(run(djvu_tool('djvused'), ['-e', 'n', 'converted.djvu'], work).strip(), b'3')
            text = run(djvu_tool('djvutxt'), ['converted.djvu'], work).decode('utf-8')
            self.assertIn('Проверка', text)
            self.assertIn('Вторая', text)
            Plumber(djvu, pdf, default_log).run()
            text_tool = os.path.join(os.path.dirname(get_tools()[0]), 'pdftotext.exe' if os.name == 'nt' else 'pdftotext')
            text = run(text_tool, ['-enc', 'UTF-8', 'roundtrip.pdf', '-'], work).decode('utf-8')
            self.assertIn('Проверка', text)
            self.assertIn('Вторая', text)
            info = run(get_tools()[0], ['-enc', 'UTF-8', 'roundtrip.pdf'], work).decode('utf-8', 'replace')
            self.assertRegex(info, r'Pages:\s+3')
            empty = run(text_tool, ['-f', '3', '-l', '3', 'roundtrip.pdf', '-'], work)
            self.assertFalse(empty.strip())
            render = get_tools()[1]
            for number in (1, 2, 3):
                for filename, prefix in (('original.pdf', 'before'), ('roundtrip.pdf', 'after')):
                    run(render, ['-f', str(number), '-l', str(number), '-r', '150', '-singlefile', filename, prefix], work)
                before, after = QImage(os.path.join(work, 'before.ppm')), QImage(os.path.join(work, 'after.ppm'))
                self.assertLessEqual(abs(before.width() - after.width()), 2)
                self.assertLessEqual(abs(before.height() - after.height()), 2)
