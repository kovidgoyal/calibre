# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Write content to PDF.
'''

import os, shutil, json
from future_builtins import map

from PyQt4.Qt import (QEventLoop, QObject, QPrinter, QSizeF, Qt, QPainter,
        QPixmap, QTimer, pyqtProperty, QString, QSize)
from PyQt4.QtWebKit import QWebView, QWebPage, QWebSettings

from calibre.constants import filesystem_encoding
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks.pdf.pageoptions import (unit, paper_size, orientation)
from calibre.ebooks.pdf.outline_writer import Outline
from calibre.ebooks.metadata import authors_to_string
from calibre.ptempfile import PersistentTemporaryFile, TemporaryFile
from calibre import (__appname__, __version__, fit_image, isosx, force_unicode)
from calibre.ebooks.oeb.display.webview import load_html

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

def get_pdf_printer(opts, for_comic=False, output_file_name=None): # {{{
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
# }}}

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


class PDFMetadata(object): # {{{
    def __init__(self, oeb_metadata=None):
        self.title = _(u'Unknown')
        self.author = _(u'Unknown')
        self.tags = u''

        if oeb_metadata != None:
            if len(oeb_metadata.title) >= 1:
                self.title = oeb_metadata.title[0].value
            if len(oeb_metadata.creator) >= 1:
                self.author = authors_to_string([x.value for x in oeb_metadata.creator])
            if oeb_metadata.subject:
                self.tags = u', '.join(map(unicode, oeb_metadata.subject))

        self.title = force_unicode(self.title)
        self.author = force_unicode(self.author)
# }}}

class Page(QWebPage):

    def __init__(self, opts, log):
        self.log = log
        QWebPage.__init__(self)
        settings = self.settings()
        settings.setFontSize(QWebSettings.DefaultFontSize,
                opts.pdf_default_font_size)
        settings.setFontSize(QWebSettings.DefaultFixedFontSize,
                opts.pdf_mono_font_size)
        settings.setFontSize(QWebSettings.MinimumLogicalFontSize, 8)
        settings.setFontSize(QWebSettings.MinimumFontSize, 8)

        std = {'serif':opts.pdf_serif_family, 'sans':opts.pdf_sans_family,
                'mono':opts.pdf_mono_family}.get(opts.pdf_standard_font,
                        opts.pdf_serif_family)
        if std:
            settings.setFontFamily(QWebSettings.StandardFont, std)
        if opts.pdf_serif_family:
            settings.setFontFamily(QWebSettings.SerifFont, opts.pdf_serif_family)
        if opts.pdf_sans_family:
            settings.setFontFamily(QWebSettings.SansSerifFont,
                    opts.pdf_sans_family)
        if opts.pdf_mono_family:
            settings.setFontFamily(QWebSettings.FixedFont, opts.pdf_mono_family)

    def javaScriptConsoleMessage(self, msg, lineno, msgid):
        self.log.debug(u'JS:', unicode(msg))

    def javaScriptAlert(self, frame, msg):
        self.log(unicode(msg))

class PDFWriter(QObject): # {{{

    def __init__(self, opts, log, cover_data=None, toc=None):
        from calibre.gui2 import is_ok_to_use_qt
        from calibre.utils.podofo import get_podofo
        if not is_ok_to_use_qt():
            raise Exception('Not OK to use Qt')
        QObject.__init__(self)

        self.logger = self.log = log
        self.podofo = get_podofo()
        self.doc = self.podofo.PDFDoc()

        self.loop = QEventLoop()
        self.view = QWebView()
        self.page = Page(opts, self.log)
        self.view.setPage(self.page)
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
        self.toc = toc

    def dump(self, items, out_stream, pdf_metadata):
        self.metadata = pdf_metadata
        self._delete_tmpdir()
        self.outline = Outline(self.toc, items)

        self.render_queue = items
        self.combine_queue = []
        self.out_stream = out_stream
        self.insert_cover()

        self.render_succeeded = False
        self.current_page_num = self.doc.page_count()
        self.combine_queue.append(os.path.join(self.tmp_path,
            'qprinter_out.pdf'))
        self.first_page = True
        self.setup_printer(self.combine_queue[-1])
        QTimer.singleShot(0, self._render_book)
        self.loop.exec_()
        if self.painter is not None:
            self.painter.end()
        if self.printer is not None:
            self.printer.abort()

        if not self.render_succeeded:
            raise Exception('Rendering HTML to PDF failed')

    def _render_book(self):
        try:
            if len(self.render_queue) == 0:
                self._write()
            else:
                self._render_next()
        except:
            self.logger.exception('Rendering failed')
            self.loop.exit(1)

    def _render_next(self):
        item = unicode(self.render_queue.pop(0))

        self.logger.debug('Processing %s...' % item)
        self.current_item = item
        load_html(item, self.view)

    def _render_html(self, ok):
        if ok:
            self.do_paged_render()
        else:
            # The document is so corrupt that we can't render the page.
            self.logger.error('Document cannot be rendered.')
            self.loop.exit(0)
            return
        self._render_book()

    def _pass_json_value_getter(self):
        val = json.dumps(self.bridge_value)
        return QString(val)

    def _pass_json_value_setter(self, value):
        self.bridge_value = json.loads(unicode(value))

    _pass_json_value = pyqtProperty(QString, fget=_pass_json_value_getter,
            fset=_pass_json_value_setter)

    def setup_printer(self, outpath):
        self.printer = self.painter = None
        printer = get_pdf_printer(self.opts, output_file_name=outpath)
        painter = QPainter(printer)
        zoomx = printer.logicalDpiX()/self.view.logicalDpiX()
        zoomy = printer.logicalDpiY()/self.view.logicalDpiY()
        painter.scale(zoomx, zoomy)
        pr = printer.pageRect()
        self.printer, self.painter = printer, painter
        self.viewport_size = QSize(pr.width()/zoomx, pr.height()/zoomy)
        self.page.setViewportSize(self.viewport_size)

    def do_paged_render(self):
        if self.paged_js is None:
            from calibre.utils.resources import compiled_coffeescript
            self.paged_js = compiled_coffeescript('ebooks.oeb.display.utils')
            self.paged_js += compiled_coffeescript('ebooks.oeb.display.indexing')
            self.paged_js += compiled_coffeescript('ebooks.oeb.display.paged')

        self.view.page().mainFrame().addToJavaScriptWindowObject("py_bridge", self)
        evaljs = self.view.page().mainFrame().evaluateJavaScript
        evaljs(self.paged_js)
        evaljs('''
        py_bridge.__defineGetter__('value', function() {
            return JSON.parse(this._pass_json_value);
        });
        py_bridge.__defineSetter__('value', function(val) {
            this._pass_json_value = JSON.stringify(val);
        });

        document.body.style.backgroundColor = "white";
        paged_display.set_geometry(1, 0, 0, 0);
        paged_display.layout();
        paged_display.fit_images();
        ''')
        mf = self.view.page().mainFrame()
        start_page = self.current_page_num
        if not self.first_page:
            start_page += 1
        while True:
            if not self.first_page:
                if self.printer.newPage():
                    self.current_page_num += 1
            self.first_page = False
            mf.render(self.painter)
            nsl = evaljs('paged_display.next_screen_location()').toInt()
            if not nsl[1] or nsl[0] <= 0: break
            evaljs('window.scrollTo(%d, 0)'%nsl[0])

        self.bridge_value = tuple(self.outline.anchor_map[self.current_item])
        evaljs('py_bridge.value = book_indexing.anchor_positions(py_bridge.value)')
        amap = self.bridge_value
        if not isinstance(amap, dict):
            amap = {} # Some javascript error occurred
        self.outline.set_pos(self.current_item, None, start_page, 0)
        for anchor, x in amap.iteritems():
            pagenum, ypos = x
            self.outline.set_pos(self.current_item, anchor, start_page + pagenum, ypos)

    def append_doc(self, outpath):
        doc = self.podofo.PDFDoc()
        with open(outpath, 'rb') as f:
            raw = f.read()
        doc.load(raw)
        self.doc.append(doc)

    def _delete_tmpdir(self):
        if os.path.exists(self.tmp_path):
            shutil.rmtree(self.tmp_path, True)
            self.tmp_path = PersistentTemporaryDirectory('_pdf_output_parts')

    def insert_cover(self):
        if not isinstance(self.cover_data, bytes):
            return
        item_path = os.path.join(self.tmp_path, 'cover.pdf')
        printer = get_pdf_printer(self.opts, output_file_name=item_path,
                for_comic=True)
        self.combine_queue.insert(0, item_path)
        p = QPixmap()
        p.loadFromData(self.cover_data)
        if not p.isNull():
            painter = QPainter(printer)
            draw_image_page(printer, painter, p,
                    preserve_aspect_ratio=self.opts.preserve_cover_aspect_ratio)
            painter.end()
            self.append_doc(item_path)
        printer.abort()

    def _write(self):
        self.painter.end()
        self.printer.abort()
        self.painter = self.printer = None
        self.append_doc(self.combine_queue[-1])

        try:
            self.doc.creator = u'%s %s [http://calibre-ebook.com]'%(
                    __appname__, __version__)
            self.doc.title = self.metadata.title
            self.doc.author = self.metadata.author
            if self.metadata.tags:
                self.doc.keywords = self.metadata.tags
            self.outline(self.doc)
            with TemporaryFile(u'pdf_out.pdf') as tf:
                if isinstance(tf, unicode):
                    tf = tf.encode(filesystem_encoding)
                self.doc.save(tf)
                with open(tf, 'rb') as src:
                    shutil.copyfileobj(src, self.out_stream)
            self.render_succeeded = True
        finally:
            self._delete_tmpdir()
            self.loop.exit(0)

# }}}

class ImagePDFWriter(object): # {{{

    def __init__(self, opts, log, cover_data=None, toc=None):
        self.opts = opts
        self.log = log

    def dump(self, items, out_stream, pdf_metadata):
        from calibre.utils.podofo import get_podofo
        f = PersistentTemporaryFile('_comic2pdf.pdf')
        f.close()
        self.metadata = pdf_metadata
        try:
            self.render_images(f.name, pdf_metadata, items)
            with open(f.name, 'rb') as x:
                raw = x.read()
            doc = get_podofo().PDFDoc()
            doc.load(raw)
            doc.creator = u'%s %s [http://calibre-ebook.com]'%(
                    __appname__, __version__)
            doc.title = self.metadata.title
            doc.author = self.metadata.author
            if self.metadata.tags:
                doc.keywords = self.metadata.tags
            raw = doc.write()
            out_stream.write(raw)
        finally:
            try:
                os.remove(f.name)
            except:
                pass

    def render_images(self, outpath, mi, items):
        printer = get_pdf_printer(self.opts, for_comic=True,
                output_file_name=outpath)
        printer.setDocName(mi.title)

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

# }}}


