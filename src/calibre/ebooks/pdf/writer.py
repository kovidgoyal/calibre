# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Write content to PDF.
'''

import os, shutil, sys

from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks.pdf.pageoptions import PageOptions
from calibre.ebooks.metadata.opf2 import OPF

from PyQt4 import QtCore
from PyQt4.Qt import QUrl, QEventLoop, SIGNAL, QObject, QApplication, QPrinter, \
    QMetaObject, Qt
from PyQt4.QtWebKit import QWebView

from pyPdf import PdfFileWriter, PdfFileReader
        
class PDFWriter(QObject):
    def __init__(self, log, popts=PageOptions()):
        if QApplication.instance() is None:
            QApplication([])
        QObject.__init__(self)
        
        self.logger = log
        
        self.loop = QEventLoop()
        self.view = QWebView()
        self.connect(self.view, SIGNAL('loadFinished(bool)'), self._render_html)
        self.render_queue = []
        self.combine_queue = []
        self.tmp_path = PersistentTemporaryDirectory('_any2pdf_parts')
        self.popts = popts

    def dump(self, opfpath, out_stream):
        self._delete_tmpdir()
        
        opf = OPF(opfpath, os.path.dirname(opfpath))
        self.render_queue = [i.path for i in opf.spine]
        self.combine_queue = []
        self.out_stream = out_stream
        
        QMetaObject.invokeMethod(self, "_render_book", Qt.QueuedConnection)
        self.loop.exec_()
        
    @QtCore.pyqtSignature('_render_book()')
    def _render_book(self):
        if len(self.render_queue) == 0:
            self._write()
        else:
            self._render_next()
            
    def _render_next(self):
        item = str(self.render_queue.pop(0))
        self.combine_queue.append(os.path.join(self.tmp_path, '%i.pdf' % (len(self.combine_queue) + 1)))
        
        self.logger.info('Processing %s...' % item)
    
        self.view.load(QUrl(item))

    def _render_html(self, ok):
        if ok:
            item_path = os.path.join(self.tmp_path, '%i.pdf' % len(self.combine_queue))
            
            self.logger.debug('\tRendering item %s as %i' % (os.path.basename(str(self.view.url().toLocalFile())), len(self.combine_queue)))
        
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageMargins(self.popts.margin_left, self.popts.margin_top, self.popts.margin_right, self.popts.margin_bottom, self.popts.unit)
            printer.setPaperSize(self.popts.paper_size)
            printer.setOrientation(self.popts.orientation)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(item_path)
            self.view.print_(printer)
        self._render_book()

    def _delete_tmpdir(self):
        if os.path.exists(self.tmp_path):
            shutil.rmtree(self.tmp_path, True)
            self.tmp_path = PersistentTemporaryDirectory('_pdf_out_parts')

    def _write(self):
        self.logger.info('Combining individual PDF parts...')
    
        try:
            outPDF = PdfFileWriter()
            for item in self.combine_queue:
                inputPDF = PdfFileReader(file(item, 'rb'))
                for page in inputPDF.pages:
                    outPDF.addPage(page)
            outPDF.write(self.out_stream)
        finally:
            self._delete_tmpdir()
            self.loop.exit(0)
