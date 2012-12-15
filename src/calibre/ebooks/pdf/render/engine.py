#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, traceback
from math import sqrt
from collections import namedtuple
from future_builtins import map

from PyQt4.Qt import (QPaintEngine, QPaintDevice, Qt, QApplication, QPainter,
                      QTransform, QPainterPath)

from calibre.constants import DEBUG
from calibre.ebooks.pdf.render.serialize import (Color, inch, A4, PDFStream,
                                                 Path)

XDPI = 1200
YDPI = 1200

Point = namedtuple('Point', 'x y')
ColorState = namedtuple('ColorState', 'color opacity do')

class GraphicsState(object): # {{{

    def __init__(self):
        self.ops = {}
        self.current_state = self.initial_state = {
            'fill': ColorState(Color(0., 0., 0., 1.), 1.0, False),
            'transform': QTransform(),
            'dash': [],
            'line_width': 0,
            'stroke': ColorState(Color(0., 0., 0., 1.), 1.0, True),
            'line_cap': 'flat',
            'line_join': 'miter',
            'clip': (Qt.NoClip, QPainterPath()),
        }

    def reset(self):
        self.current_state = self.initial_state

    def update_color_state(self, which, color=None, opacity=None,
                           brush_style=None, pen_style=None):
        current = self.ops.get(which, self.current_state[which])
        n = ColorState(*current)
        if color is not None:
            n = n._replace(color=Color(*color.getRgbF()))
        if opacity is not None:
            n = n._replace(opacity=opacity)
        if opacity is not None:
            opacity *= n.color.opacity
        if brush_style is not None:
            if which == 'fill':
                do = (False if opacity == 0.0 or brush_style == Qt.NoBrush else
                    True)
            else:
                do = (False if opacity == 0.0 or brush_style == Qt.NoBrush or
                    pen_style == Qt.NoPen else True)
            n = n._replace(do=do)
        self.ops[which] = n

    def read(self, state):
        self.ops = {}
        flags = state.state()

        if flags & QPaintEngine.DirtyTransform:
            self.ops['transform'] = state.transform()

        # TODO: Add support for brush patterns
        if flags & QPaintEngine.DirtyBrush:
            brush = state.brush()
            color = brush.color()
            self.update_color_state('fill', color=color,
                                    brush_style=brush.style())

        if flags & QPaintEngine.DirtyPen:
            pen = state.pen()
            brush = pen.brush()
            color = pen.color()
            self.update_color_state('stroke', color, brush_style=brush.style(),
                                    pen_style=pen.style())
            ps = {Qt.DashLine:[3], Qt.DotLine:[1,2], Qt.DashDotLine:[3,2,1,2],
                  Qt.DashDotDotLine:[3, 2, 1, 2, 1, 2]}.get(pen.style(), [])
            self.ops['dash'] = ps
            self.ops['line_width'] = pen.widthF()
            self.ops['line_cap'] = {Qt.FlatCap:'flat', Qt.RoundCap:'round',
                            Qt.SquareCap:'square'}.get(pen.capStyle(), 'flat')
            self.ops['line_join'] = {Qt.MiterJoin:'miter', Qt.RoundJoin:'round',
                            Qt.BevelJoin:'bevel'}.get(pen.joinStyle(), 'miter')

        if flags & QPaintEngine.DirtyOpacity:
            self.update_color_state('fill', opacity=state.opacity())
            self.update_color_state('stroke', opacity=state.opacity())

        if flags & QPaintEngine.DirtyClipPath:
            self.ops['clip'] = (state.clipOperation(), state.clipPath())
        elif flags & QPaintEngine.DirtyClipRegion:
            path = QPainterPath()
            for rect in state.clipRegion().rects():
                path.addRect(rect)
            self.ops['clip'] = (state.clipOperation(), path)

    def __call__(self, engine):
        pdf = engine.pdf
        ops = self.ops
        current_transform = self.current_state['transform']
        transform_changed = 'transform' in ops and ops['transform'] != current_transform
        reset_stack = transform_changed or 'clip' in ops

        if reset_stack:
            pdf.restore_stack()
            pdf.save_stack()

        # We apply clip before transform as the clip may have to be merged with
        # the previous clip path so it is easiest to work with clips that are
        # pre-transformed
        prev_op, prev_clip_path = self.current_state['clip']
        if 'clip' in ops:
            op, path = ops['clip']
            self.current_state['clip'] = (op, path)
            transform = ops.get('transform', QTransform())
            if not transform.isIdentity() and path is not None:
                # Pre transform the clip path
                path = current_transform.map(path)
                self.current_state['clip'] = (op, path)

            if op == Qt.ReplaceClip:
                pass
            elif op == Qt.IntersectClip:
                if prev_op != Qt.NoClip:
                    self.current_state['clip'] = (op, path.intersected(prev_clip_path))
            elif op == Qt.UniteClip:
                if prev_clip_path is not None:
                    path.addPath(prev_clip_path)
            else:
                self.current_state['clip'] = (Qt.NoClip, QPainterPath())
            op, path = self.current_state['clip']
            if op != Qt.NoClip:
                engine.add_clip(path)
        elif reset_stack and prev_op != Qt.NoClip:
            # Re-apply the previous clip path since no clipping operation was
            # specified
            engine.add_clip(prev_clip_path)

        if reset_stack:
            # Since we have reset the stack we need to re-apply all previous
            # operations, that are different from the default value (clip is
            # handled separately).
            for op in set(self.current_state) - (set(ops)|{'clip'}):
                if self.current_state[op] != self.initial_state[op]:
                    self.apply(op, self.current_state[op], engine, pdf)

        # Now apply the new operations
        for op, val in ops.iteritems():
            self.apply(op, val, engine, pdf)
            self.current_state[op] = val

    def apply(self, op, val, engine, pdf):
        getattr(self, 'apply_'+op)(val, engine, pdf)

    def apply_transform(self, val, engine, pdf):
        engine.qt_system = val
        pdf.transform(val)

    def apply_stroke(self, val, engine, pdf):
        self.apply_color_state('stroke', val, engine, pdf)

    def apply_fill(self, val, engine, pdf):
        self.apply_color_state('fill', val, engine, pdf)

    def apply_color_state(self, which, val, engine, pdf):
        color = val.color._replace(opacity=val.opacity*val.color.opacity)
        getattr(pdf, 'set_%s_color'%which)(color)
        setattr(engine, 'do_%s'%which, val.do)

    def apply_dash(self, val, engine, pdf):
        pdf.set_dash(val)

    def apply_line_width(self, val, engine, pdf):
        pdf.set_line_width(val)

    def apply_line_cap(self, val, engine, pdf):
        pdf.set_line_cap(val)

    def apply_line_join(self, val, engine, pdf):
        pdf.set_line_join(val)

# }}}

class PdfEngine(QPaintEngine):

    def __init__(self, file_object, page_width, page_height, left_margin,
                 top_margin, right_margin, bottom_margin, width, height):
        QPaintEngine.__init__(self, self.features)
        self.file_object = file_object
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
        self.qt_system = QTransform()
        self.do_stroke = True
        self.do_fill = False
        self.scale = sqrt(sy**2 + sx**2)
        self.yscale = sy
        self.graphics_state = GraphicsState()

    def init_page(self):
        self.pdf.transform(self.pdf_system)
        self.pdf.set_rgb_colorspace()
        width = self.painter.pen().widthF() if self.isActive() else 0
        self.pdf.set_line_width(width)
        self.do_stroke = True
        self.do_fill = False
        self.graphics_state.reset()
        self.pdf.save_stack()

    @property
    def features(self):
        return (QPaintEngine.Antialiasing | QPaintEngine.AlphaBlend |
                QPaintEngine.ConstantOpacity | QPaintEngine.PainterPaths |
                QPaintEngine.PaintOutsidePaintEvent |
                QPaintEngine.PrimitiveTransform)

    def begin(self, device):
        try:
            self.pdf = PDFStream(self.file_object, (self.page_width,
                                                    self.page_height),
                                compress=not DEBUG)
            self.init_page()
        except:
            traceback.print_exc()
            return False
        return True

    def end_page(self, start_new=True):
        self.pdf.restore_stack()
        self.pdf.end_page()
        if start_new:
            self.init_page()

    def end(self):
        try:
            self.end_page(start_new=False)
            self.pdf.end()
        except:
            traceback.print_exc()
            return False
        finally:
            self.pdf = self.file_object = None
        return True

    def type(self):
        return QPaintEngine.Pdf

    def drawPixmap(self, rect, pixmap, source_rect):
        print ('TODO: drawPixmap() currently unimplemented')

    def drawImage(self, rect, image, source_rect, flags=Qt.AutoColor):
        print ('TODO: drawImage() currently unimplemented')

    def updateState(self, state):
        self.graphics_state.read(state)
        self.graphics_state(self)

    def convert_path(self, path):
        p = Path()
        i = 0
        while i < path.elementCount():
            elem = path.elementAt(i)
            em = (elem.x, elem.y)
            i += 1
            if elem.isMoveTo():
                p.move_to(*em)
            elif elem.isLineTo():
                p.line_to(*em)
            elif elem.isCurveTo():
                if path.elementCount() > i+1:
                    c1, c2 = map(lambda j:(
                        path.elementAt(j).x, path.elementAt(j).y), (i, i+1))
                    i += 2
                    p.curve_to(*(c1 + c2 + em))
        return p

    def drawPath(self, path):
        p = self.convert_path(path)
        fill_rule = {Qt.OddEvenFill:'evenodd',
                    Qt.WindingFill:'winding'}[path.fillRule()]
        self.pdf.draw_path(p, stroke=self.do_stroke,
                                fill=self.do_fill, fill_rule=fill_rule)

    def add_clip(self, path):
        p = self.convert_path(path)
        fill_rule = {Qt.OddEvenFill:'evenodd',
                    Qt.WindingFill:'winding'}[path.fillRule()]
        self.pdf.add_clip(p, fill_rule=fill_rule)

    def drawPoints(self, points):
        p = Path()
        for point in points:
            p.move_to(point.x(), point.y())
            p.line_to(point.x(), point.y() + 0.001)
        self.pdf.draw_path(p, stroke=self.do_stroke, fill=False)

    def drawRects(self, rects):
        for rect in rects:
            bl = rect.topLeft()
            self.pdf.draw_rect(bl.x(), bl.y(), rect.width(), rect.height(),
                             stroke=self.do_stroke, fill=self.do_fill)

    def drawTextItem(self, point, text_item):
        # super(PdfEngine, self).drawTextItem(point, text_item)
        f = text_item.font()
        px, pt = f.pixelSize(), f.pointSizeF()
        if px == -1:
            sz = pt/self.yscale
        else:
            sz = px

        q = self.qt_system
        if not q.isIdentity() and q.type() > q.TxShear:
            # We cant map this transform to a PDF text transform operator
            f, s = self.do_fill, self.do_stroke
            self.do_fill, self.do_stroke = True, False
            super(PdfEngine, self).drawTextItem(point, text_item)
            self.do_fill, self.do_stroke = f, s
            return

        to = self.canvas.beginText()
        # set_transform(QTransform(1, 0, 0, -1, point.x(), point.y()), to.setTextTransform)
        fontname = 'Times-Roman'
        to.setFont(fontname, sz) # TODO: Embed font
        stretch = f.stretch()
        if stretch != 100:
            to.setHorizontalScale(stretch)
        ws = f.wordSpacing()
        if ws != 0:
            to.setWordSpacing(self.map_dx(ws))
        spacing = f.letterSpacing()
        st = f.letterSpacingType()
        if st == f.AbsoluteSpacing and spacing != 0:
            to.setCharSpace(spacing)
        # TODO: Handle percentage letter spacing
        text = type(u'')(text_item.text())
        to.textOut(text)
        # TODO: handle colors
        self.canvas.drawText(to)

        def draw_line(kind='underline'):
            tw = self.canvas.stringWidth(text, fontname, sz)
            p = self.canvas.beginPath()
            if kind == 'underline':
                dy = -text_item.descent()
            elif kind == 'overline':
                dy = text_item.ascent()
            elif kind == 'strikeout':
                dy = text_item.ascent()/2
            p.moveTo(point.x, point.y+dy)
            p.lineTo(point.x+tw, point.y+dy)

        if f.underline():
            draw_line()
        if f.overline():
            draw_line('overline')
        if f.strikeOut():
            draw_line('strikeout')

    def drawPolygon(self, points, mode):
        if not points: return
        p = Path()
        p.move_to(points[0].x(), points[0].y())
        for point in points[1:]:
            p.line_to(point.x(), point.y())
        if points[-1] != points[0]:
            p.line_to(points[0].x(), points[0].y())
        fill_rule = {self.OddEvenMode:'evenodd',
                    self.WindingMode:'winding'}.get(mode, 'evenodd')
        self.pdf.draw_path(p, stroke=True, fill_rule=fill_rule,
            fill=(mode in (self.OddEvenMode, self.WindingMode, self.ConvexMode)))

    def __enter__(self):
        self.pdf.save_stack()

    def __exit__(self, *args):
        self.pdf.restore_stack()

class PdfDevice(QPaintDevice): # {{{


    def __init__(self, file_object, page_size=A4, left_margin=inch,
                 top_margin=inch, right_margin=inch, bottom_margin=inch):
        QPaintDevice.__init__(self)
        self.page_width, self.page_height = page_size
        self.body_width = self.page_width - left_margin - right_margin
        self.body_height = self.page_height - top_margin - bottom_margin
        self.engine = PdfEngine(file_object, self.page_width, self.page_height,
                                left_margin, top_margin, right_margin,
                                bottom_margin, self.width(), self.height())

    def paintEngine(self):
        return self.engine

    def metric(self, m):
        if m in (self.PdmDpiX, self.PdmPhysicalDpiX):
            return XDPI
        if m in (self.PdmDpiY, self.PdmPhysicalDpiY):
            return YDPI
        if m == self.PdmDepth:
            return 32
        if m == self.PdmNumColors:
            return sys.maxint
        if m == self.PdmWidthMM:
            return int(round(self.body_width * 0.35277777777778))
        if m == self.PdmHeightMM:
            return int(round(self.body_height * 0.35277777777778))
        if m == self.PdmWidth:
            return int(round(self.body_width * XDPI / 72.0))
        if m == self.PdmHeight:
            return int(round(self.body_height * YDPI / 72.0))
        return 0
# }}}

if __name__ == '__main__':
    from PyQt4.Qt import (QBrush, QColor, QPoint)
    QBrush, QColor, QPoint
    app = QApplication([])
    p = QPainter()
    with open('/tmp/painter.pdf', 'wb') as f:
        dev = PdfDevice(f)
        p.begin(dev)
        xmax, ymax = p.viewport().width(), p.viewport().height()
        try:
            p.drawRect(0, 0, xmax, ymax)
            p.drawPolyline(QPoint(0, 0), QPoint(xmax, 0), QPoint(xmax, ymax),
                           QPoint(0, ymax), QPoint(0, 0))
            pp = QPainterPath()
            pp.addRect(0, 0, xmax, ymax)
            p.drawPath(pp)
            p.save()
            for i in xrange(3):
                col = [0, 0, 0, 200]
                col[i] = 255
                p.setOpacity(0.3)
                p.setBrush(QBrush(QColor(*col)))
                p.drawRect(0, 0, xmax/10, xmax/10)
                p.translate(xmax/10, xmax/10)
                p.scale(1, 1.5)
            p.restore()

            p.save()
            p.drawLine(0, 0, 5000, 0)
            p.rotate(45)
            p.drawLine(0, 0, 5000, 0)
            p.restore()

            # f = p.font()
            # f.setPointSize(24)
            # f.setFamily('Times New Roman')
            # p.setFont(f)
            # # p.scale(2, 2)
            # p.rotate(45)
            # p.drawText(QPoint(100, 300), 'Some text')
        finally:
            p.end()

