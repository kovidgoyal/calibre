#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, traceback, math
from collections import namedtuple
from functools import wraps, partial
from future_builtins import map

import sip
from PyQt4.Qt import (QPaintEngine, QPaintDevice, Qt, QTransform, QBrush)

from calibre.constants import plugins
from calibre.ebooks.pdf.render.serialize import (PDFStream, Path)
from calibre.ebooks.pdf.render.common import inch, A4, fmtnum
from calibre.ebooks.pdf.render.graphics import convert_path, Graphics
from calibre.utils.fonts.sfnt.container import Sfnt, UnsupportedFont
from calibre.utils.fonts.sfnt.metrics import FontMetrics

Point = namedtuple('Point', 'x y')
ColorState = namedtuple('ColorState', 'color opacity do')

def repr_transform(t):
    vals = map(fmtnum, (t.m11(), t.m12(), t.m21(), t.m22(), t.dx(), t.dy()))
    return '[%s]'%' '.join(vals)

def store_error(func):

    @wraps(func)
    def errh(self, *args, **kwargs):
        try:
            func(self, *args, **kwargs)
        except:
            self.errors_occurred = True
            self.errors(traceback.format_exc())

    return errh

class Font(FontMetrics):

    def __init__(self, sfnt):
        FontMetrics.__init__(self, sfnt)
        self.glyph_map = {}

class PdfEngine(QPaintEngine):

    FEATURES = QPaintEngine.AllFeatures & ~(
        QPaintEngine.PorterDuff | QPaintEngine.PerspectiveTransform
        | QPaintEngine.ObjectBoundingModeGradients
        | QPaintEngine.RadialGradientFill
        | QPaintEngine.ConicalGradientFill
    )

    def __init__(self, file_object, page_width, page_height, left_margin,
                 top_margin, right_margin, bottom_margin, width, height,
                 errors=print, debug=print, compress=True,
                 mark_links=False):
        QPaintEngine.__init__(self, self.FEATURES)
        self.file_object = file_object
        self.compress, self.mark_links = compress, mark_links
        self.page_height, self.page_width = page_height, page_width
        self.left_margin, self.top_margin = left_margin, top_margin
        self.right_margin, self.bottom_margin = right_margin, bottom_margin
        self.pixel_width, self.pixel_height = width, height
        # Setup a co-ordinate transform that allows us to use co-ords
        # from Qt's pixel based co-ordinate system with its origin at the top
        # left corner. PDF's co-ordinate system is based on pts and has its
        # origin in the bottom left corner. We also have to implement the page
        # margins. Therefore, we need to translate, scale and reflect about the
        # x-axis.
        dy = self.page_height - self.top_margin
        dx = self.left_margin
        sx =  (self.page_width - self.left_margin -
                            self.right_margin) / self.pixel_width
        sy =  (self.page_height - self.top_margin -
                            self.bottom_margin) / self.pixel_height

        self.pdf_system = QTransform(sx, 0, 0, -sy, dx, dy)
        self.graphics = Graphics(self.pixel_width, self.pixel_height)
        self.errors_occurred = False
        self.errors, self.debug = errors, debug
        self.fonts = {}
        self.current_page_num = 1
        self.current_page_inited = False
        self.qt_hack, err = plugins['qt_hack']
        if err:
            raise RuntimeError('Failed to load qt_hack with err: %s'%err)

    def apply_graphics_state(self):
        self.graphics(self.pdf_system, self.painter())

    def resolve_fill(self, rect):
        self.graphics.resolve_fill(rect, self.pdf_system,
                                   self.painter().transform())

    @property
    def do_fill(self):
        return self.graphics.current_state.do_fill

    @property
    def do_stroke(self):
        return self.graphics.current_state.do_stroke

    def init_page(self):
        self.pdf.transform(self.pdf_system)
        self.pdf.apply_fill(color=(1, 1, 1)) # QPainter has a default background brush of white
        self.graphics.reset()
        self.pdf.save_stack()
        self.current_page_inited = True

    def begin(self, device):
        if not hasattr(self, 'pdf'):
            try:
                self.pdf = PDFStream(self.file_object, (self.page_width,
                        self.page_height), compress=self.compress,
                                     mark_links=self.mark_links,
                                     debug=self.debug)
                self.graphics.begin(self.pdf)
            except:
                self.errors(traceback.format_exc())
                self.errors_occurred = True
                return False
        return True

    def end_page(self):
        if self.current_page_inited:
            self.pdf.restore_stack()
            self.pdf.end_page()
            self.current_page_inited = False
            self.current_page_num += 1

    def end(self):
        try:
            self.end_page()
            self.pdf.end()
        except:
            self.errors(traceback.format_exc())
            self.errors_occurred = True
            return False
        finally:
            self.pdf = self.file_object = None
        return True

    def type(self):
        return QPaintEngine.Pdf

    def add_image(self, img, cache_key):
        if img.isNull(): return
        return self.pdf.add_image(img, cache_key)

    @store_error
    def drawTiledPixmap(self, rect, pixmap, point):
        self.apply_graphics_state()
        brush = QBrush(pixmap)
        bl = rect.topLeft()
        color, opacity, pattern, do_fill = self.graphics.convert_brush(
            brush, bl-point, 1.0, self.pdf_system,
            self.painter().transform())
        self.pdf.save_stack()
        self.pdf.apply_fill(color, pattern)
        self.pdf.draw_rect(bl.x(), bl.y(), rect.width(), rect.height(),
                            stroke=False, fill=True)
        self.pdf.restore_stack()

    @store_error
    def drawPixmap(self, rect, pixmap, source_rect):
        self.apply_graphics_state()
        source_rect = source_rect.toRect()
        pixmap = (pixmap if source_rect == pixmap.rect() else
                  pixmap.copy(source_rect))
        image = pixmap.toImage()
        ref = self.add_image(image, pixmap.cacheKey())
        if ref is not None:
            self.pdf.draw_image(rect.x(), rect.y(), rect.width(),
                                rect.height(), ref)

    @store_error
    def drawImage(self, rect, image, source_rect, flags=Qt.AutoColor):
        self.apply_graphics_state()
        source_rect = source_rect.toRect()
        image = (image if source_rect == image.rect() else
                 image.copy(source_rect))
        ref = self.add_image(image, image.cacheKey())
        if ref is not None:
            self.pdf.draw_image(rect.x(), rect.y(), rect.width(),
                                rect.height(), ref)

    @store_error
    def updateState(self, state):
        self.graphics.update_state(state, self.painter())

    @store_error
    def drawPath(self, path):
        self.apply_graphics_state()
        p = convert_path(path)
        fill_rule = {Qt.OddEvenFill:'evenodd',
                    Qt.WindingFill:'winding'}[path.fillRule()]
        self.pdf.draw_path(p, stroke=self.do_stroke,
                                fill=self.do_fill, fill_rule=fill_rule)

    @store_error
    def drawPoints(self, points):
        self.apply_graphics_state()
        p = Path()
        for point in points:
            p.move_to(point.x(), point.y())
            p.line_to(point.x(), point.y() + 0.001)
        self.pdf.draw_path(p, stroke=self.do_stroke, fill=False)

    @store_error
    def drawRects(self, rects):
        self.apply_graphics_state()
        with self.graphics:
            for rect in rects:
                self.resolve_fill(rect)
                bl = rect.topLeft()
                self.pdf.draw_rect(bl.x(), bl.y(), rect.width(), rect.height(),
                                stroke=self.do_stroke, fill=self.do_fill)

    def create_sfnt(self, text_item):
        get_table = partial(self.qt_hack.get_sfnt_table, text_item)
        try:
            ans = Font(Sfnt(get_table))
        except UnsupportedFont as e:
            raise UnsupportedFont('The font %s is not a valid sfnt. Error: %s'%(
                text_item.font().family(), e))
        glyph_map = self.qt_hack.get_glyph_map(text_item)
        gm = {}
        for uc, glyph_id in enumerate(glyph_map):
            if glyph_id not in gm:
                gm[glyph_id] = unichr(uc)
        ans.full_glyph_map = gm
        return ans

    @store_error
    def drawTextItem(self, point, text_item):
        # return super(PdfEngine, self).drawTextItem(point, text_item)
        self.apply_graphics_state()
        gi = self.qt_hack.get_glyphs(point, text_item)
        if not gi.indices:
            sip.delete(gi)
            return
        name = hash(bytes(gi.name))
        if name not in self.fonts:
            try:
                self.fonts[name] = self.create_sfnt(text_item)
            except UnsupportedFont:
                return super(PdfEngine, self).drawTextItem(point, text_item)
        metrics = self.fonts[name]
        for glyph_id in gi.indices:
            try:
                metrics.glyph_map[glyph_id] = metrics.full_glyph_map[glyph_id]
            except (KeyError, ValueError):
                pass
        glyphs = []
        last_x = last_y = 0
        for i, pos in enumerate(gi.positions):
            x, y = pos.x(), pos.y()
            glyphs.append((x-last_x, last_y - y, gi.indices[i]))
            last_x, last_y = x, y

        self.pdf.draw_glyph_run([gi.stretch, 0, 0, -1, 0, 0], gi.size, metrics,
                                glyphs)
        sip.delete(gi)

    @store_error
    def drawPolygon(self, points, mode):
        self.apply_graphics_state()
        if not points: return
        p = Path()
        p.move_to(points[0].x(), points[0].y())
        for point in points[1:]:
            p.line_to(point.x(), point.y())
        p.close()
        fill_rule = {self.OddEvenMode:'evenodd',
                    self.WindingMode:'winding'}.get(mode, 'evenodd')
        self.pdf.draw_path(p, stroke=True, fill_rule=fill_rule,
            fill=(mode in (self.OddEvenMode, self.WindingMode, self.ConvexMode)))

    def set_metadata(self, *args, **kwargs):
        self.pdf.set_metadata(*args, **kwargs)

    def add_outline(self, toc):
        self.pdf.links.add_outline(toc)

    def add_links(self, current_item, start_page, links, anchors):
        for pos in anchors.itervalues():
            pos['left'], pos['top'] = self.pdf_system.map(pos['left'], pos['top'])
        for link in links:
            pos = link[1]
            llx = pos['left']
            lly = pos['top'] + pos['height']
            urx = pos['left'] + pos['width']
            ury = pos['top']
            llx, lly = self.pdf_system.map(llx, lly)
            urx, ury = self.pdf_system.map(urx, ury)
            link[1] = pos['column'] + start_page
            link.append((llx, lly, urx, ury))
        self.pdf.links.add(current_item, start_page, links, anchors)

class PdfDevice(QPaintDevice): # {{{


    def __init__(self, file_object, page_size=A4, left_margin=inch,
                 top_margin=inch, right_margin=inch, bottom_margin=inch,
                 xdpi=1200, ydpi=1200, errors=print, debug=print,
                 compress=True, mark_links=False):
        QPaintDevice.__init__(self)
        self.xdpi, self.ydpi = xdpi, ydpi
        self.page_width, self.page_height = page_size
        self.body_width = self.page_width - left_margin - right_margin
        self.body_height = self.page_height - top_margin - bottom_margin
        self.left_margin, self.right_margin = left_margin, right_margin
        self.top_margin, self.bottom_margin = top_margin, bottom_margin
        self.engine = PdfEngine(file_object, self.page_width, self.page_height,
                                left_margin, top_margin, right_margin,
                                bottom_margin, self.width(), self.height(),
                                errors=errors, debug=debug, compress=compress,
                                mark_links=mark_links)
        self.add_outline = self.engine.add_outline
        self.add_links = self.engine.add_links

    def paintEngine(self):
        return self.engine

    def metric(self, m):
        if m in (self.PdmDpiX, self.PdmPhysicalDpiX):
            return self.xdpi
        if m in (self.PdmDpiY, self.PdmPhysicalDpiY):
            return self.ydpi
        if m == self.PdmDepth:
            return 32
        if m == self.PdmNumColors:
            return sys.maxint
        if m == self.PdmWidthMM:
            return int(round(self.body_width * 0.35277777777778))
        if m == self.PdmHeightMM:
            return int(round(self.body_height * 0.35277777777778))
        if m == self.PdmWidth:
            return int(round(self.body_width * self.xdpi / 72.0))
        if m == self.PdmHeight:
            return int(round(self.body_height * self.ydpi / 72.0))
        return 0

    def end_page(self, *args, **kwargs):
        self.engine.end_page(*args, **kwargs)

    def init_page(self):
        self.engine.init_page()

    @property
    def full_page_rect(self):
        page_width = self.page_width * self.xdpi / 72.0
        lm = int(math.ceil(self.left_margin * self.xdpi / 72.0))
        page_height = self.page_height * self.ydpi / 72.0
        tm = int(math.ceil(self.top_margin * self.ydpi / 72.0))
        return (-lm, -tm, page_width, page_height)

    @property
    def current_page_num(self):
        return self.engine.current_page_num

    @property
    def errors_occurred(self):
        return self.engine.errors_occurred

    def to_px(self, pt, vertical=True):
        return pt * (self.height()/self.page_height if vertical else
                     self.width()/self.page_width)

    def set_metadata(self, *args, **kwargs):
        self.engine.set_metadata(*args, **kwargs)

# }}}


