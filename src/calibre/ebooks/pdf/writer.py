# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Write content to PDF.
'''

import os
import shutil

from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks.pdf.pageoptions import unit, paper_size, \
    orientation
from calibre.ebooks.metadata import authors_to_string

from PyQt4 import QtCore
from PyQt4.Qt import QUrl, QEventLoop, SIGNAL, QObject, \
    QApplication, QPrinter, QMetaObject, QSizeF, Qt
from PyQt4.QtWebKit import QWebView

from pyPdf import PdfFileWriter, PdfFileReader

class PDFMetadata(object):
    def __init__(self, oeb_metadata=None):
        self.title = _('Unknown')
        self.author = _('Unknown')

        if oeb_metadata != None:
            if len(oeb_metadata.title) >= 1:
                self.title = oeb_metadata.title[0].value
            if len(oeb_metadata.creator) >= 1:
                self.author = authors_to_string([x.value for x in oeb_metadata.creator])


class PDFWriter(QObject):
    def __init__(self, opts, log):
        if QApplication.instance() is None:
            QApplication([])
        QObject.__init__(self)

        self.logger = log

        self.loop = QEventLoop()
        self.view = QWebView()
        self.connect(self.view, SIGNAL('loadFinished(bool)'), self._render_html)
        self.render_queue = []
        self.combine_queue = []
        self.tmp_path = PersistentTemporaryDirectory('_pdf_output_parts')

        self.custom_size = None
        if opts.custom_size != None:
            width, sep, height = opts.custom_size.partition('x')
            if height != '':
                try:
                    width = int(width)
                    height = int(height)
                    self.custom_size = (width, height)
                except:
                    self.custom_size = None

        self.opts = opts

        self.size = self._size()

    def dump(self, items, out_stream, pdf_metadata):
        self.metadata = pdf_metadata
        self._delete_tmpdir()

        self.render_queue = items
        self.combine_queue = []
        self.out_stream = out_stream

        QMetaObject.invokeMethod(self, "_render_book", Qt.QueuedConnection)
        self.loop.exec_()

    def _size(self):
        '''
        The size of a pdf page in cm.
        '''
        printer = QPrinter(QPrinter.HighResolution)

        if self.opts.output_profile.short_name == 'default':
            if self.custom_size == None:
                printer.setPaperSize(paper_size(self.opts.paper_size))
            else:
                printer.setPaperSize(QSizeF(self.custom_size[0], self.custom_size[1]), unit(self.opts.unit))
        else:
            printer.setPaperSize(QSizeF(self.opts.output_profile.width / self.opts.output_profile.dpi, self.opts.output_profile.height / self.opts.output_profile.dpi), QPrinter.Inch)

        printer.setPageMargins(0, 0, 0, 0, QPrinter.Point)
        printer.setOrientation(orientation(self.opts.orientation))
        printer.setOutputFormat(QPrinter.PdfFormat)

        size = printer.paperSize(QPrinter.Millimeter)

        return size.width() / 10, size.height() / 10

    @QtCore.pyqtSignature('_render_book()')
    def _render_book(self):
        if len(self.render_queue) == 0:
            self._write()
        else:
            self._render_next()

    def _render_next(self):
        item = str(self.render_queue.pop(0))
        self.combine_queue.append(os.path.join(self.tmp_path, '%i.pdf' % (len(self.combine_queue) + 1)))

        self.logger.debug('Processing %s...' % item)

        self.view.load(QUrl.fromLocalFile(item))

    def _render_html(self, ok):
        if ok:
            item_path = os.path.join(self.tmp_path, '%i.pdf' % len(self.combine_queue))

            self.logger.debug('\tRendering item %s as %i' % (os.path.basename(str(self.view.url().toLocalFile())), len(self.combine_queue)))

            printer = QPrinter(QPrinter.HighResolution)
            printer.setPaperSize(QSizeF(self.size[0] * 10, self.size[1] * 10), QPrinter.Millimeter)
            printer.setPageMargins(0, 0, 0, 0, QPrinter.Point)
            printer.setOrientation(orientation(self.opts.orientation))
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(item_path)
            self.view.print_(printer)
        self._render_book()

    def _delete_tmpdir(self):
        if os.path.exists(self.tmp_path):
            shutil.rmtree(self.tmp_path, True)
            self.tmp_path = PersistentTemporaryDirectory('_pdf_output_parts')

    def _write(self):
        self.logger.debug('Combining individual PDF parts...')

        try:
            outPDF = PdfFileWriter(title=self.metadata.title, author=self.metadata.author)
            for item in self.combine_queue:
                inputPDF = PdfFileReader(open(item, 'rb'))
                for page in inputPDF.pages:
                    outPDF.addPage(page)
            outPDF.write(self.out_stream)
        finally:
            self._delete_tmpdir()
            self.loop.exit(0)


class ImagePDFWriter(PDFWriter):

    def _render_next(self):
        item = str(self.render_queue.pop(0))
        self.combine_queue.append(os.path.join(self.tmp_path, '%i.pdf' % (len(self.combine_queue) + 1)))

        self.logger.debug('Processing %s...' % item)

        height = 'height: %fcm;' % (self.size[1] * 1.3)

        html = '<html><body style="margin: 0;"><img src="%s" style="%s display: block; margin-left: auto; margin-right: auto; padding: 0px;" /></body></html>' % (item, height)

        self.view.setHtml(html)

    def _size(self):
            printer = QPrinter(QPrinter.HighResolution)

            if self.opts.output_profile.short_name == 'default':
                if self.custom_size == None:
                    printer.setPaperSize(paper_size(self.opts.paper_size))
                else:
                    printer.setPaperSize(QSizeF(self.custom_size[0], self.custom_size[1]), unit(self.opts.unit))
            else:
                printer.setPaperSize(QSizeF(self.opts.output_profile.comic_screen_size[0] / self.opts.output_profile.dpi, self.opts.output_profile.comic_screen_size[1] / self.opts.output_profile.dpi), QPrinter.Inch)

            printer.setPageMargins(0, 0, 0, 0, QPrinter.Point)
            printer.setOrientation(orientation(self.opts.orientation))
            printer.setOutputFormat(QPrinter.PdfFormat)

            size = printer.paperSize(QPrinter.Millimeter)

            return size.width() / 10, size.height() / 10

