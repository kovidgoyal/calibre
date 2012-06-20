# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Write content to PDF.
'''

import os
import shutil

from calibre import isosx
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks.pdf.pageoptions import unit, paper_size, \
    orientation
from calibre.ebooks.metadata import authors_to_string
from calibre.ptempfile import PersistentTemporaryFile
from calibre import __appname__, __version__, fit_image
from calibre.ebooks.oeb.display.webview import load_html

from PyQt4 import QtCore
from PyQt4.Qt import (QEventLoop, QObject,
    QPrinter, QMetaObject, QSizeF, Qt, QPainter, QPixmap)
from PyQt4.QtWebKit import QWebView

from pyPdf import PdfFileWriter, PdfFileReader

def get_custom_size(opts):
    custom_size = None
    if opts.custom_size != None:
        width, sep, height = opts.custom_size.partition('x')
        if height != '':
            try:
                width = int(width)
                height = int(height)
                custom_size = (width, height)
            except:
                custom_size = None
    return custom_size

def get_pdf_printer(opts, for_comic=False, output_file_name=None):
    from calibre.gui2 import is_ok_to_use_qt
    if not is_ok_to_use_qt():
        raise Exception('Not OK to use Qt')

    printer = QPrinter(QPrinter.HighResolution)
    custom_size = get_custom_size(opts)
    if isosx and not for_comic:
        # On OSX, the native engine can only produce a single page size
        # (usually A4). The Qt engine on the other hand produces image based
        # PDFs. If we set a custom page size using QSizeF the native engine
        # produces unreadable output, so we just ignore the custom size
        # settings.
        printer.setPaperSize(paper_size(opts.paper_size))
    else:
        if opts.output_profile.short_name == 'default' or \
                opts.output_profile.width > 9999:
            if custom_size is None:
                printer.setPaperSize(paper_size(opts.paper_size))
            else:
                printer.setPaperSize(QSizeF(custom_size[0], custom_size[1]), unit(opts.unit))
        else:
            w = opts.output_profile.comic_screen_size[0] if for_comic else \
                    opts.output_profile.width
            h = opts.output_profile.comic_screen_size[1] if for_comic else \
                    opts.output_profile.height
            dpi = opts.output_profile.dpi
            printer.setPaperSize(QSizeF(float(w) / dpi, float(h) / dpi), QPrinter.Inch)

    if for_comic:
        # Comic pages typically have their own margins, or their background
        # color is not white, in which case the margin looks bad
        printer.setPageMargins(0, 0, 0, 0, QPrinter.Point)
    else:
        printer.setPageMargins(opts.margin_left, opts.margin_top,
                opts.margin_right, opts.margin_bottom, QPrinter.Point)
    printer.setOrientation(orientation(opts.orientation))
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setFullPage(for_comic)
    if output_file_name:
        printer.setOutputFileName(output_file_name)
    if isosx and not for_comic:
        # Ensure we are not generating enormous image based PDFs
        printer.setOutputFormat(QPrinter.NativeFormat)

    return printer

def draw_image_page(printer, painter, p, preserve_aspect_ratio=True):
    page_rect = printer.pageRect()
    if preserve_aspect_ratio:
        aspect_ratio = float(p.width())/p.height()
        nw, nh = page_rect.width(), page_rect.height()
        if aspect_ratio > 1:
            nh = int(page_rect.width()/aspect_ratio)
        else: # Width is smaller than height
            nw = page_rect.height()*aspect_ratio
        __, nnw, nnh = fit_image(nw, nh, page_rect.width(),
                page_rect.height())
        dx = int((page_rect.width() - nnw)/2.)
        dy = int((page_rect.height() - nnh)/2.)
        page_rect.moveTo(dx, dy)
        page_rect.setHeight(nnh)
        page_rect.setWidth(nnw)
    painter.drawPixmap(page_rect, p, p.rect())


class PDFMetadata(object):
    def __init__(self, oeb_metadata=None):
        self.title = _('Unknown')
        self.author = _('Unknown')

        if oeb_metadata != None:
            if len(oeb_metadata.title) >= 1:
                self.title = oeb_metadata.title[0].value
            if len(oeb_metadata.creator) >= 1:
                self.author = authors_to_string([x.value for x in oeb_metadata.creator])


class PDFWriter(QObject): # {{{

    def __init__(self, opts, log, cover_data=None):
        from calibre.gui2 import is_ok_to_use_qt
        if not is_ok_to_use_qt():
            raise Exception('Not OK to use Qt')
        QObject.__init__(self)

        self.logger = log

        self.loop = QEventLoop()
        self.view = QWebView()
        self.view.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
        self.view.loadFinished.connect(self._render_html,
                type=Qt.QueuedConnection)
        for x in (Qt.Horizontal, Qt.Vertical):
            self.view.page().mainFrame().setScrollBarPolicy(x,
                    Qt.ScrollBarAlwaysOff)
        self.render_queue = []
        self.combine_queue = []
        self.tmp_path = PersistentTemporaryDirectory(u'_pdf_output_parts')

        self.opts = opts
        self.cover_data = cover_data
        self.paged_js = None

    def dump(self, items, out_stream, pdf_metadata):
        self.metadata = pdf_metadata
        self._delete_tmpdir()

        self.render_queue = items
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
        item = unicode(self.render_queue.pop(0))
        self.combine_queue.append(os.path.join(self.tmp_path, '%i.pdf' % (len(self.combine_queue) + 1)))

        self.logger.debug('Processing %s...' % item)
        load_html(item, self.view)

    def _render_html(self, ok):
        if ok:
            item_path = os.path.join(self.tmp_path, '%i.pdf' % len(self.combine_queue))
            self.logger.debug('\tRendering item %s as %i.pdf' % (os.path.basename(str(self.view.url().toLocalFile())), len(self.combine_queue)))
            if True:
                self.do_paged_render(item_path)
            else:
                printer = get_pdf_printer(self.opts, output_file_name=item_path)
                self.view.page().mainFrame().evaluateJavaScript('''
                    document.body.style.backgroundColor = "white";

                    ''')
                self.view.print_(printer)
                printer.abort()
        else:
            # The document is so corrupt that we can't render the page.
            self.loop.exit(0)
            raise Exception('Document cannot be rendered.')
        self._render_book()

    def do_paged_render(self, outpath):
        from PyQt4.Qt import QSize, QPainter
        if self.paged_js is None:
            from calibre.utils.resources import compiled_coffeescript
            self.paged_js = compiled_coffeescript('ebooks.oeb.display.paged',
                    dynamic=False)
        printer = get_pdf_printer(self.opts, output_file_name=outpath)
        painter = QPainter(printer)
        zoomx = printer.logicalDpiX()/self.view.logicalDpiX()
        zoomy = printer.logicalDpiY()/self.view.logicalDpiY()
        painter.scale(zoomx, zoomy)

        pr = printer.pageRect()
        evaljs = self.view.page().mainFrame().evaluateJavaScript
        evaljs(self.paged_js)
        self.view.page().setViewportSize(QSize(pr.width()/zoomx,
            pr.height()/zoomy))
        evaljs('''
        document.body.style.backgroundColor = "white";
        paged_display.set_geometry(1, 0, 0, 0);
        paged_display.layout();
        ''')
        mf = self.view.page().mainFrame()
        while True:
            mf.render(painter)
            nsl = evaljs('paged_display.next_screen_location()').toInt()
            if not nsl[1] or nsl[0] <= 0: break
            evaljs('window.scrollTo(%d, 0)'%nsl[0])
            printer.newPage()

        painter.end()
        printer.abort()

    def _delete_tmpdir(self):
        if os.path.exists(self.tmp_path):
            shutil.rmtree(self.tmp_path, True)
            self.tmp_path = PersistentTemporaryDirectory('_pdf_output_parts')

    def insert_cover(self):
        if self.cover_data is None:
            return
        item_path = os.path.join(self.tmp_path, 'cover.pdf')
        printer = get_pdf_printer(self.opts, output_file_name=item_path)
        self.combine_queue.insert(0, item_path)
        p = QPixmap()
        p.loadFromData(self.cover_data)
        if not p.isNull():
            painter = QPainter(printer)
            draw_image_page(printer, painter, p,
                    preserve_aspect_ratio=self.opts.preserve_cover_aspect_ratio)
            painter.end()
        printer.abort()


    def _write(self):
        self.logger.debug('Combining individual PDF parts...')

        self.insert_cover()

        try:
            outPDF = PdfFileWriter(title=self.metadata.title, author=self.metadata.author)
            for item in self.combine_queue:
                # The input PDF stream must remain open until the final PDF
                # is written to disk. PyPDF references pages added to the
                # final PDF from the input PDF on disk. It does not store
                # the pages in memory so we can't close the input PDF.
                inputPDF = PdfFileReader(open(item, 'rb'))
                for page in inputPDF.pages:
                    outPDF.addPage(page)
            outPDF.write(self.out_stream)
        finally:
            self._delete_tmpdir()
            self.loop.exit(0)

# }}}

class ImagePDFWriter(object):

    def __init__(self, opts, log, cover_data=None):
        self.opts = opts
        self.log = log

    def dump(self, items, out_stream, pdf_metadata):
        f = PersistentTemporaryFile('_comic2pdf.pdf')
        f.close()
        try:
            self.render_images(f.name, pdf_metadata, items)
            with open(f.name, 'rb') as x:
                shutil.copyfileobj(x, out_stream)
        finally:
            os.remove(f.name)

    def render_images(self, outpath, mi, items):
        printer = get_pdf_printer(self.opts, for_comic=True,
                output_file_name=outpath)
        printer.setDocName(mi.title)
        printer.setCreator(u'%s [%s]'%(__appname__, __version__))
        # Seems to be no way to set author

        painter = QPainter(printer)
        painter.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform)

        for i, imgpath in enumerate(items):
            self.log('Rendering image:', i)
            p = QPixmap()
            p.load(imgpath)
            if not p.isNull():
                if i > 0:
                    printer.newPage()
                draw_image_page(printer, painter, p)
            else:
                self.log.warn('Failed to load image', i)
        painter.end()


