#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json, os
from future_builtins import map
from math import floor

from PyQt4.Qt import (QObject, QPainter, Qt, QSize, QString, QTimer,
                      pyqtProperty, QEventLoop, QPixmap, QRect, pyqtSlot)
from PyQt4.QtWebKit import QWebView, QWebPage, QWebSettings

from calibre import fit_image
from calibre.constants import iswindows
from calibre.ebooks.oeb.display.webview import load_html
from calibre.ebooks.pdf.render.common import (inch, cm, mm, pica, cicero,
                                              didot, PAPER_SIZES)
from calibre.ebooks.pdf.render.engine import PdfDevice
from calibre.ptempfile import PersistentTemporaryFile

def get_page_size(opts, for_comic=False):  # {{{
    use_profile = not (opts.override_profile_size or
                       opts.output_profile.short_name == 'default' or
                       opts.output_profile.width > 9999)
    if use_profile:
        w = (opts.output_profile.comic_screen_size[0] if for_comic else
                opts.output_profile.width)
        h = (opts.output_profile.comic_screen_size[1] if for_comic else
                opts.output_profile.height)
        dpi = opts.output_profile.dpi
        factor = 72.0 / dpi
        page_size = (factor * w, factor * h)
    else:
        page_size = None
        if opts.custom_size is not None:
            width, sep, height = opts.custom_size.partition('x')
            if height:
                try:
                    width = float(width)
                    height = float(height)
                except:
                    pass
                else:
                    if opts.unit == 'devicepixel':
                        factor = 72.0 / opts.output_profile.dpi
                    else:
                        factor = {'point':1.0, 'inch':inch, 'cicero':cicero,
                         'didot':didot, 'pica':pica, 'millimeter':mm,
                         'centimeter':cm}[opts.unit]
                    page_size = (factor*width, factor*height)
        if page_size is None:
            page_size = PAPER_SIZES[opts.paper_size]
    return page_size
# }}}

class Page(QWebPage):  # {{{

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
        self.longjs_counter = 0

    def javaScriptConsoleMessage(self, msg, lineno, msgid):
        self.log.debug(u'JS:', unicode(msg))

    def javaScriptAlert(self, frame, msg):
        self.log(unicode(msg))

    @pyqtSlot(result=bool)
    def shouldInterruptJavaScript(self):
        if self.longjs_counter < 10:
            self.log('Long running javascript, letting it proceed')
            self.longjs_counter += 1
            return False
        self.log.warn('Long running javascript, aborting it')
        return True

# }}}

def draw_image_page(page_rect, painter, p, preserve_aspect_ratio=True):
    if preserve_aspect_ratio:
        aspect_ratio = float(p.width())/p.height()
        nw, nh = page_rect.width(), page_rect.height()
        if aspect_ratio > 1:
            nh = int(page_rect.width()/aspect_ratio)
        else:  # Width is smaller than height
            nw = page_rect.height()*aspect_ratio
        __, nnw, nnh = fit_image(nw, nh, page_rect.width(),
                page_rect.height())
        dx = int((page_rect.width() - nnw)/2.)
        dy = int((page_rect.height() - nnh)/2.)
        page_rect.translate(dx, dy)
        page_rect.setHeight(nnh)
        page_rect.setWidth(nnw)
    painter.drawPixmap(page_rect, p, p.rect())

class PDFWriter(QObject):

    def _pass_json_value_getter(self):
        val = json.dumps(self.bridge_value)
        return QString(val)

    def _pass_json_value_setter(self, value):
        self.bridge_value = json.loads(unicode(value))

    _pass_json_value = pyqtProperty(QString, fget=_pass_json_value_getter,
            fset=_pass_json_value_setter)

    @pyqtSlot(result=unicode)
    def title(self):
        return self.doc_title

    @pyqtSlot(result=unicode)
    def author(self):
        return self.doc_author

    @pyqtSlot(result=unicode)
    def section(self):
        return self.current_section

    def __init__(self, opts, log, cover_data=None, toc=None):
        from calibre.gui2 import is_ok_to_use_qt
        if not is_ok_to_use_qt():
            raise Exception('Not OK to use Qt')
        QObject.__init__(self)

        self.logger = self.log = log
        self.opts = opts
        self.cover_data = cover_data
        self.paged_js = None
        self.toc = toc

        self.loop = QEventLoop()
        self.view = QWebView()
        self.page = Page(opts, self.log)
        self.view.setPage(self.page)
        self.view.setRenderHints(QPainter.Antialiasing|
                    QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
        self.view.loadFinished.connect(self.render_html,
                type=Qt.QueuedConnection)
        for x in (Qt.Horizontal, Qt.Vertical):
            self.view.page().mainFrame().setScrollBarPolicy(x,
                    Qt.ScrollBarAlwaysOff)
        self.report_progress = lambda x, y: x
        self.current_section = ''

    def dump(self, items, out_stream, pdf_metadata):
        opts = self.opts
        page_size = get_page_size(self.opts)
        xdpi, ydpi = self.view.logicalDpiX(), self.view.logicalDpiY()
        # We cannot set the side margins in the webview as there is no right
        # margin for the last page (the margins are implemented with
        # -webkit-column-gap)
        ml, mr = opts.margin_left, opts.margin_right
        self.doc = PdfDevice(out_stream, page_size=page_size, left_margin=ml,
                             top_margin=0, right_margin=mr, bottom_margin=0,
                             xdpi=xdpi, ydpi=ydpi, errors=self.log.error,
                             debug=self.log.debug, compress=not
                             opts.uncompressed_pdf,
                             mark_links=opts.pdf_mark_links)
        self.footer = opts.pdf_footer_template
        if self.footer:
            self.footer = self.footer.strip()
        if not self.footer and opts.pdf_page_numbers:
            self.footer = '<p style="text-align:center; text-indent: 0">_PAGENUM_</p>'
        self.header = opts.pdf_header_template
        if self.header:
            self.header = self.header.strip()
        min_margin = 36
        if self.footer and opts.margin_bottom < min_margin:
            self.log.warn('Bottom margin is too small for footer, increasing it.')
            opts.margin_bottom = min_margin
        if self.header and opts.margin_top < min_margin:
            self.log.warn('Top margin is too small for header, increasing it.')
            opts.margin_top = min_margin

        self.page.setViewportSize(QSize(self.doc.width(), self.doc.height()))
        self.render_queue = items
        self.total_items = len(items)

        mt, mb = map(self.doc.to_px, (opts.margin_top, opts.margin_bottom))
        self.margin_top, self.margin_bottom = map(lambda x:int(floor(x)), (mt, mb))

        self.painter = QPainter(self.doc)
        self.doc.set_metadata(title=pdf_metadata.title,
                              author=pdf_metadata.author,
                              tags=pdf_metadata.tags)
        self.doc_title = pdf_metadata.title
        self.doc_author = pdf_metadata.author
        self.painter.save()
        try:
            if self.cover_data is not None:
                p = QPixmap()
                try:
                    p.loadFromData(self.cover_data)
                except TypeError:
                    self.log.warn('This ebook does not have a raster cover, cannot generate cover for PDF'
                                  '. Cover type: %s' % type(self.cover_data))
                if not p.isNull():
                    self.doc.init_page()
                    draw_image_page(QRect(*self.doc.full_page_rect),
                            self.painter, p,
                            preserve_aspect_ratio=self.opts.preserve_cover_aspect_ratio)
                    self.doc.end_page()
        finally:
            self.painter.restore()

        QTimer.singleShot(0, self.render_book)
        if self.loop.exec_() == 1:
            raise Exception('PDF Output failed, see log for details')

        if self.toc is not None and len(self.toc) > 0:
            self.doc.add_outline(self.toc)

        self.painter.end()

        if self.doc.errors_occurred:
            raise Exception('PDF Output failed, see log for details')

    def render_inline_toc(self):
        self.rendered_inline_toc = True
        from calibre.ebooks.pdf.render.toc import toc_as_html
        raw = toc_as_html(self.toc, self.doc, self.opts)
        pt = PersistentTemporaryFile('_pdf_itoc.htm')
        pt.write(raw)
        pt.close()
        self.render_queue.append(pt.name)
        self.render_next()

    def render_book(self):
        if self.doc.errors_occurred:
            return self.loop.exit(1)
        try:
            if not self.render_queue:
                if self.opts.pdf_add_toc and self.toc is not None and len(self.toc) > 0 and not hasattr(self, 'rendered_inline_toc'):
                    return self.render_inline_toc()
                self.loop.exit()
            else:
                self.render_next()
        except:
            self.logger.exception('Rendering failed')
            self.loop.exit(1)

    def render_next(self):
        item = unicode(self.render_queue.pop(0))

        self.logger.debug('Processing %s...' % item)
        self.current_item = item
        load_html(item, self.view)

    def render_html(self, ok):
        if ok:
            try:
                self.do_paged_render()
            except:
                self.log.exception('Rendering failed')
                self.loop.exit(1)
                return
        else:
            # The document is so corrupt that we can't render the page.
            self.logger.error('Document cannot be rendered.')
            self.loop.exit(1)
            return
        done = self.total_items - len(self.render_queue)
        self.report_progress(done/self.total_items,
                        _('Rendered %s'%os.path.basename(self.current_item)))
        self.render_book()

    @property
    def current_page_num(self):
        return self.doc.current_page_num

    def load_mathjax(self):
        evaljs = self.view.page().mainFrame().evaluateJavaScript
        mjpath = P(u'viewer/mathjax').replace(os.sep, '/')
        if iswindows:
            mjpath = u'/' + mjpath
        if evaljs('''
                    window.mathjax.base = %s;
                    mathjax.check_for_math(); mathjax.math_present
                    '''%(json.dumps(mjpath, ensure_ascii=False))).toBool():
            self.log.debug('Math present, loading MathJax')
            while not evaljs('mathjax.math_loaded').toBool():
                self.loop.processEvents(self.loop.ExcludeUserInputEvents)
            evaljs('document.getElementById("MathJax_Message").style.display="none";')

    def get_sections(self, anchor_map):
        sections = {}
        ci = os.path.abspath(os.path.normcase(self.current_item))
        if self.toc is not None:
            for toc in self.toc.flat():
                path = toc.abspath or None
                frag = toc.fragment or None
                if path is None:
                    continue
                path = os.path.abspath(os.path.normcase(path))
                if path == ci:
                    col = 0
                    if frag and frag in anchor_map:
                        col = anchor_map[frag]['column']
                    if col not in sections:
                        sections[col] = toc.text or _('Untitled')

        return sections

    def do_paged_render(self):
        if self.paged_js is None:
            import uuid
            from calibre.utils.resources import compiled_coffeescript as cc
            self.paged_js =  cc('ebooks.oeb.display.utils')
            self.paged_js += cc('ebooks.oeb.display.indexing')
            self.paged_js += cc('ebooks.oeb.display.paged')
            self.paged_js += cc('ebooks.oeb.display.mathjax')
            self.hf_uuid = str(uuid.uuid4()).replace('-', '')

        self.view.page().mainFrame().addToJavaScriptWindowObject("py_bridge", self)
        self.view.page().longjs_counter = 0
        evaljs = self.view.page().mainFrame().evaluateJavaScript
        evaljs(self.paged_js)
        self.load_mathjax()

        evaljs('''
        py_bridge.__defineGetter__('value', function() {
            return JSON.parse(this._pass_json_value);
        });
        py_bridge.__defineSetter__('value', function(val) {
            this._pass_json_value = JSON.stringify(val);
        });

        document.body.style.backgroundColor = "white";
        paged_display.set_geometry(1, %d, %d, %d);
        paged_display.layout();
        paged_display.fit_images();
        py_bridge.value = book_indexing.all_links_and_anchors();
        window.scrollTo(0, 0); // This is needed as getting anchor positions could have caused the viewport to scroll
        '''%(self.margin_top, 0, self.margin_bottom))

        amap = self.bridge_value
        if not isinstance(amap, dict):
            amap = {'links':[], 'anchors':{}}  # Some javascript error occurred
        sections = self.get_sections(amap['anchors'])
        col = 0

        if self.header:
            self.bridge_value = self.header
            evaljs('paged_display.header_template = py_bridge.value')
        if self.footer:
            self.bridge_value = self.footer
            evaljs('paged_display.footer_template = py_bridge.value')
        if self.header or self.footer:
            evaljs('paged_display.create_header_footer("%s");'%self.hf_uuid)

        start_page = self.current_page_num

        mf = self.view.page().mainFrame()
        while True:
            if col in sections:
                self.current_section = sections[col]
            self.doc.init_page()
            if self.header or self.footer:
                evaljs('paged_display.update_header_footer(%d)'%self.current_page_num)
            self.painter.save()
            mf.render(self.painter)
            self.painter.restore()
            nsl = evaljs('paged_display.next_screen_location()').toInt()
            self.doc.end_page()
            if not nsl[1] or nsl[0] <= 0:
                break
            evaljs('window.scrollTo(%d, 0); paged_display.position_header_footer();'%nsl[0])
            if self.doc.errors_occurred:
                break
            col += 1

        if not self.doc.errors_occurred:
            self.doc.add_links(self.current_item, start_page, amap['links'],
                            amap['anchors'])



