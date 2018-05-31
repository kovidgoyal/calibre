#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json, os
from future_builtins import map
from math import floor
from collections import defaultdict

from PyQt5.Qt import (
    QObject, QPainter, Qt, QSize, QTimer, QEventLoop, QPixmap, QRect, pyqtSlot)
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

from calibre import fit_image
from calibre.constants import iswindows
from calibre.ebooks.oeb.display.webview import load_html
from calibre.ebooks.pdf.render.common import (inch, cm, mm, pica, cicero,
                                              didot, PAPER_SIZES, current_log)
from calibre.ebooks.pdf.render.engine import PdfDevice
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.resources import load_hyphenator_dicts


def get_page_size(opts, for_comic=False):  # {{{
    use_profile = opts.use_profile_size and opts.output_profile.short_name != 'default' and opts.output_profile.width <= 9999
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
                    width = float(width.replace(',', '.'))
                    height = float(height.replace(',', '.'))
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
        from calibre.gui2 import secure_web_page
        self.log = log
        QWebPage.__init__(self)
        settings = self.settings()
        settings.setFontSize(QWebSettings.DefaultFontSize,
                opts.pdf_default_font_size)
        settings.setFontSize(QWebSettings.DefaultFixedFontSize,
                opts.pdf_mono_font_size)
        settings.setFontSize(QWebSettings.MinimumLogicalFontSize, 8)
        settings.setFontSize(QWebSettings.MinimumFontSize, 8)
        secure_web_page(settings)

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

    @pyqtSlot(result=unicode)
    def title(self):
        return self.doc_title

    @pyqtSlot(result=unicode)
    def author(self):
        return self.doc_author

    @pyqtSlot(result=unicode)
    def section(self):
        return self.current_section

    @pyqtSlot(result=unicode)
    def tl_section(self):
        return self.current_tl_section

    def __init__(self, opts, log, cover_data=None, toc=None):
        from calibre.gui2 import must_use_qt
        must_use_qt()
        QObject.__init__(self)

        self.logger = self.log = log
        current_log(log)
        self.opts = opts
        self.cover_data = cover_data
        self.paged_js = None
        self.toc = toc

        self.loop = QEventLoop()
        self.view = QWebView()
        self.page = Page(opts, self.log)
        self.view.setPage(self.page)
        self.view.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
        self.view.loadFinished.connect(self.render_html,
                type=Qt.QueuedConnection)
        for x in (Qt.Horizontal, Qt.Vertical):
            self.view.page().mainFrame().setScrollBarPolicy(x,
                    Qt.ScrollBarAlwaysOff)
        self.report_progress = lambda x, y: x
        self.current_section = ''
        self.current_tl_section = ''

    def dump(self, items, out_stream, pdf_metadata):
        opts = self.opts
        page_size = get_page_size(self.opts)
        xdpi, ydpi = self.view.logicalDpiX(), self.view.logicalDpiY()

        def margin(which):
            val = getattr(opts, 'pdf_page_margin_' + which)
            if val == 0.0:
                val = getattr(opts, 'margin_' + which)
            return val
        ml, mr, mt, mb = map(margin, 'left right top bottom'.split())
        # We cannot set the side margins in the webview as there is no right
        # margin for the last page (the margins are implemented with
        # -webkit-column-gap)
        self.doc = PdfDevice(out_stream, page_size=page_size, left_margin=ml,
                             top_margin=0, right_margin=mr, bottom_margin=0,
                             xdpi=xdpi, ydpi=ydpi, errors=self.log.error,
                             debug=self.log.debug, compress=not
                             opts.uncompressed_pdf, opts=opts,
                             mark_links=opts.pdf_mark_links, page_margins=(ml, mr, mt, mb))
        self.footer = opts.pdf_footer_template
        if self.footer:
            self.footer = self.footer.strip()
        if not self.footer and opts.pdf_page_numbers:
            self.footer = '<p style="text-align:center; text-indent: 0">_PAGENUM_</p>'
        self.header = opts.pdf_header_template
        if self.header:
            self.header = self.header.strip()
        min_margin = 1.5 * opts._final_base_font_size
        if self.footer and mb < min_margin:
            self.log.warn('Bottom margin is too small for footer, increasing it to %.1fpts' % min_margin)
            mb = min_margin
        if self.header and mt < min_margin:
            self.log.warn('Top margin is too small for header, increasing it to %.1fpts' % min_margin)
            mt = min_margin

        self.page.setViewportSize(QSize(self.doc.width(), self.doc.height()))
        self.render_queue = items
        self.total_items = len(items)

        mt, mb = map(self.doc.to_px, (mt, mb))
        self.margin_top, self.margin_bottom = map(lambda x:int(floor(x)), (mt, mb))

        self.painter = QPainter(self.doc)
        self.book_language = pdf_metadata.mi.languages[0]
        self.doc.set_metadata(title=pdf_metadata.title,
                              author=pdf_metadata.author,
                              tags=pdf_metadata.tags, mi=pdf_metadata.mi)
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
        if bool(evaljs('''
                    window.mathjax.base = %s;
                    mathjax.check_for_math(); mathjax.math_present
                    '''%(json.dumps(mjpath, ensure_ascii=False)))):
            self.log.debug('Math present, loading MathJax')
            while not bool(evaljs('mathjax.math_loaded')):
                self.loop.processEvents(self.loop.ExcludeUserInputEvents)
            evaljs('document.getElementById("MathJax_Message").style.display="none";')

    def load_header_footer_images(self):
        from calibre.utils.monotonic import monotonic
        evaljs = self.view.page().mainFrame().evaluateJavaScript
        st = monotonic()
        while not evaljs('paged_display.header_footer_images_loaded()'):
            self.loop.processEvents(self.loop.ExcludeUserInputEvents)
            if monotonic() - st > 5:
                self.log.warn('Header and footer images have not loaded in 5 seconds, ignoring')
                break

    def get_sections(self, anchor_map, only_top_level=False):
        sections = defaultdict(list)
        ci = os.path.abspath(os.path.normcase(self.current_item))
        if self.toc is not None:
            tocentries = self.toc.top_level_items() if only_top_level else self.toc.flat()
            for toc in tocentries:
                path = toc.abspath or None
                frag = toc.fragment or None
                if path is None:
                    continue
                path = os.path.abspath(os.path.normcase(path))
                if path == ci:
                    col = 0
                    if frag and frag in anchor_map:
                        col = anchor_map[frag]['column']
                    sections[col].append(toc.text or _('Untitled'))

        return sections

    def hyphenate(self, evaljs):
        evaljs(u'''\
        Hyphenator.config(
            {
            'minwordlength'    : 6,
            // 'hyphenchar'     : '|',
            'displaytogglebox' : false,
            'remoteloading'    : false,
            'doframes'         : true,
            'defaultlanguage'  : 'en',
            'storagetype'      : 'session',
            'onerrorhandler'   : function (e) {
                                    console.log(e);
                                }
            });
        Hyphenator.hyphenate(document.body, "%s");
        ''' % self.hyphenate_lang
        )

    def convert_page_margins(self, doc_margins):
        ans = [0, 0, 0, 0]

        def convert(name, idx, vertical=True):
            m = doc_margins.get(name)
            if m is None:
                ans[idx] = getattr(self.doc.engine, '{}_margin'.format(name))
            else:
                ans[idx] = m

        convert('left', 0, False), convert('top', 1), convert('right', 2, False), convert('bottom', 3)
        return ans

    def do_paged_render(self):
        if self.paged_js is None:
            import uuid
            from calibre.utils.resources import compiled_coffeescript as cc
            self.paged_js =  cc('ebooks.oeb.display.utils')
            self.paged_js += cc('ebooks.oeb.display.indexing')
            self.paged_js += cc('ebooks.oeb.display.paged')
            self.paged_js += cc('ebooks.oeb.display.mathjax')
            if self.opts.pdf_hyphenate:
                self.paged_js += P('viewer/hyphenate/Hyphenator.js', data=True).decode('utf-8')
                hjs, self.hyphenate_lang = load_hyphenator_dicts({}, self.book_language)
                self.paged_js += hjs
            self.hf_uuid = str(uuid.uuid4()).replace('-', '')

        self.view.page().mainFrame().addToJavaScriptWindowObject("py_bridge", self)
        self.view.page().longjs_counter = 0
        evaljs = self.view.page().mainFrame().evaluateJavaScript
        evaljs(self.paged_js)
        self.load_mathjax()
        if self.opts.pdf_hyphenate:
            self.hyphenate(evaljs)

        margin_top, margin_bottom = self.margin_top, self.margin_bottom
        page_margins = None
        if self.opts.pdf_use_document_margins:
            doc_margins = evaljs('document.documentElement.getAttribute("data-calibre-pdf-output-page-margins")')
            try:
                doc_margins = json.loads(doc_margins)
            except Exception:
                doc_margins = None
            if doc_margins and isinstance(doc_margins, dict):
                doc_margins = {k:float(v) for k, v in doc_margins.iteritems() if isinstance(v, (float, int)) and k in {'right', 'top', 'left', 'bottom'}}
                if doc_margins:
                    margin_top = margin_bottom = 0
                    page_margins = self.convert_page_margins(doc_margins)

        amap = json.loads(evaljs('''
        document.body.style.backgroundColor = "white";
        paged_display.set_geometry(1, %d, %d, %d);
        paged_display.layout();
        paged_display.fit_images();
        ret = book_indexing.all_links_and_anchors();
        window.scrollTo(0, 0); // This is needed as getting anchor positions could have caused the viewport to scroll
        JSON.stringify(ret);
        '''%(margin_top, 0, margin_bottom)))

        if not isinstance(amap, dict):
            amap = {'links':[], 'anchors':{}}  # Some javascript error occurred
        for val in amap['anchors'].itervalues():
            if isinstance(val, dict) and 'column' in val:
                val['column'] = int(val['column'])
        for href, val in amap['links']:
            if isinstance(val, dict) and 'column' in val:
                val['column'] = int(val['column'])
        sections = self.get_sections(amap['anchors'])
        tl_sections = self.get_sections(amap['anchors'], True)
        col = 0

        if self.header:
            evaljs('paged_display.header_template = ' + json.dumps(self.header))
        if self.footer:
            evaljs('paged_display.footer_template = ' + json.dumps(self.footer))
        if self.header or self.footer:
            evaljs('paged_display.create_header_footer("%s");'%self.hf_uuid)

        start_page = self.current_page_num

        mf = self.view.page().mainFrame()

        def set_section(col, sections, attr):
            # If this page has no section, use the section from the previous page
            idx = col if col in sections else col - 1 if col - 1 in sections else None
            if idx is not None:
                setattr(self, attr, sections[idx][0])

        while True:
            set_section(col, sections, 'current_section')
            set_section(col, tl_sections, 'current_tl_section')
            self.doc.init_page(page_margins)
            if self.header or self.footer:
                if evaljs('paged_display.update_header_footer(%d)'%self.current_page_num) is True:
                    self.load_header_footer_images()

            self.painter.save()
            mf.render(self.painter)
            self.painter.restore()
            try:
                nsl = int(evaljs('paged_display.next_screen_location()'))
            except (TypeError, ValueError):
                break
            self.doc.end_page(nsl <= 0)
            if nsl <= 0:
                break
            evaljs('window.scrollTo(%d, 0); paged_display.position_header_footer();'%nsl)
            if self.doc.errors_occurred:
                break
            col += 1

        if not self.doc.errors_occurred and self.doc.current_page_num > 1:
            self.doc.add_links(self.current_item, start_page, amap['links'],
                            amap['anchors'])


class ImagePDFWriter(object):

    def __init__(self, opts, log, cover_data=None, toc=None):
        from calibre.gui2 import must_use_qt
        must_use_qt()

        self.logger = self.log = log
        self.opts = opts
        self.cover_data = cover_data
        self.toc = toc

    def dump(self, items, out_stream, pdf_metadata):
        opts = self.opts
        page_size = get_page_size(self.opts)
        ml, mr = opts.margin_left, opts.margin_right
        self.doc = PdfDevice(
            out_stream, page_size=page_size, left_margin=ml,
            top_margin=opts.margin_top, right_margin=mr,
            bottom_margin=opts.margin_bottom,
            errors=self.log.error, debug=self.log.debug, compress=not
            opts.uncompressed_pdf, opts=opts, mark_links=opts.pdf_mark_links)
        self.painter = QPainter(self.doc)
        self.doc.set_metadata(title=pdf_metadata.title,
                              author=pdf_metadata.author,
                              tags=pdf_metadata.tags, mi=pdf_metadata.mi)
        self.doc_title = pdf_metadata.title
        self.doc_author = pdf_metadata.author

        for imgpath in items:
            self.log.debug('Processing %s...' % imgpath)
            self.doc.init_page()
            p = QPixmap()
            with lopen(imgpath, 'rb') as f:
                if not p.loadFromData(f.read()):
                    raise ValueError('Could not read image from: {}'.format(imgpath))
            draw_image_page(QRect(*self.doc.full_page_rect),
                    self.painter, p,
                    preserve_aspect_ratio=True)
            self.doc.end_page()
        if self.toc is not None and len(self.toc) > 0:
            self.doc.add_outline(self.toc)

        self.painter.end()

        if self.doc.errors_occurred:
            raise Exception('PDF Output failed, see log for details')
