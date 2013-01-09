#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from math import sqrt
from collections import namedtuple

from PyQt4.Qt import (
    QBrush, QPen, Qt, QPointF, QTransform, QPaintEngine, QImage)

from calibre.ebooks.pdf.render.common import (
    Name, Array, fmtnum, Stream, Dictionary)
from calibre.ebooks.pdf.render.serialize import Path
from calibre.ebooks.pdf.render.gradients import LinearGradientPattern

def convert_path(path): # {{{
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
            added = False
            if path.elementCount() > i+1:
                c1, c2 = path.elementAt(i), path.elementAt(i+1)
                if (c1.type == path.CurveToDataElement and c2.type ==
                    path.CurveToDataElement):
                    i += 2
                    p.curve_to(em[0], em[1], c1.x, c1.y, c2.x, c2.y)
                    added = True
            if not added:
                raise ValueError('Invalid curve to operation')
    return p
# }}}

Brush = namedtuple('Brush', 'origin brush color')

class TilingPattern(Stream):

    def __init__(self, cache_key, matrix, w=8, h=8, paint_type=2, compress=False):
        Stream.__init__(self, compress=compress)
        self.paint_type = paint_type
        self.w, self.h = w, h
        self.matrix = (matrix.m11(), matrix.m12(), matrix.m21(), matrix.m22(),
                       matrix.dx(), matrix.dy())
        self.resources = Dictionary()
        self.cache_key = (self.__class__.__name__, cache_key, self.matrix)

    def add_extra_keys(self, d):
        d['Type'] = Name('Pattern')
        d['PatternType'] = 1
        d['PaintType'] = self.paint_type
        d['TilingType'] = 1
        d['BBox'] = Array([0, 0, self.w, self.h])
        d['XStep'] = self.w
        d['YStep'] = self.h
        d['Matrix'] = Array(self.matrix)
        d['Resources'] = self.resources

class QtPattern(TilingPattern):

    qt_patterns = ( # {{{
        "0 J\n"
        "6 w\n"
        "[] 0 d\n"
        "4 0 m\n"
        "4 8 l\n"
        "0 4 m\n"
        "8 4 l\n"
        "S\n", # Dense1Pattern

        "0 J\n"
        "2 w\n"
        "[6 2] 1 d\n"
        "0 0 m\n"
        "0 8 l\n"
        "8 0 m\n"
        "8 8 l\n"
        "S\n"
        "[] 0 d\n"
        "2 0 m\n"
        "2 8 l\n"
        "6 0 m\n"
        "6 8 l\n"
        "S\n"
        "[6 2] -3 d\n"
        "4 0 m\n"
        "4 8 l\n"
        "S\n", # Dense2Pattern

        "0 J\n"
        "2 w\n"
        "[6 2] 1 d\n"
        "0 0 m\n"
        "0 8 l\n"
        "8 0 m\n"
        "8 8 l\n"
        "S\n"
        "[2 2] -1 d\n"
        "2 0 m\n"
        "2 8 l\n"
        "6 0 m\n"
        "6 8 l\n"
        "S\n"
        "[6 2] -3 d\n"
        "4 0 m\n"
        "4 8 l\n"
        "S\n", # Dense3Pattern

        "0 J\n"
        "2 w\n"
        "[2 2] 1 d\n"
        "0 0 m\n"
        "0 8 l\n"
        "8 0 m\n"
        "8 8 l\n"
        "S\n"
        "[2 2] -1 d\n"
        "2 0 m\n"
        "2 8 l\n"
        "6 0 m\n"
        "6 8 l\n"
        "S\n"
        "[2 2] 1 d\n"
        "4 0 m\n"
        "4 8 l\n"
        "S\n", # Dense4Pattern

        "0 J\n"
        "2 w\n"
        "[2 6] -1 d\n"
        "0 0 m\n"
        "0 8 l\n"
        "8 0 m\n"
        "8 8 l\n"
        "S\n"
        "[2 2] 1 d\n"
        "2 0 m\n"
        "2 8 l\n"
        "6 0 m\n"
        "6 8 l\n"
        "S\n"
        "[2 6] 3 d\n"
        "4 0 m\n"
        "4 8 l\n"
        "S\n", # Dense5Pattern

        "0 J\n"
        "2 w\n"
        "[2 6] -1 d\n"
        "0 0 m\n"
        "0 8 l\n"
        "8 0 m\n"
        "8 8 l\n"
        "S\n"
        "[2 6] 3 d\n"
        "4 0 m\n"
        "4 8 l\n"
        "S\n", # Dense6Pattern

        "0 J\n"
        "2 w\n"
        "[2 6] -1 d\n"
        "0 0 m\n"
        "0 8 l\n"
        "8 0 m\n"
        "8 8 l\n"
        "S\n", # Dense7Pattern

        "1 w\n"
        "0 4 m\n"
        "8 4 l\n"
        "S\n", # HorPattern

        "1 w\n"
        "4 0 m\n"
        "4 8 l\n"
        "S\n", # VerPattern

        "1 w\n"
        "4 0 m\n"
        "4 8 l\n"
        "0 4 m\n"
        "8 4 l\n"
        "S\n", # CrossPattern

        "1 w\n"
        "-1 5 m\n"
        "5 -1 l\n"
        "3 9 m\n"
        "9 3 l\n"
        "S\n", # BDiagPattern

        "1 w\n"
        "-1 3 m\n"
        "5 9 l\n"
        "3 -1 m\n"
        "9 5 l\n"
        "S\n", # FDiagPattern

        "1 w\n"
        "-1 3 m\n"
        "5 9 l\n"
        "3 -1 m\n"
        "9 5 l\n"
        "-1 5 m\n"
        "5 -1 l\n"
        "3 9 m\n"
        "9 3 l\n"
        "S\n", # DiagCrossPattern
    ) # }}}

    def __init__(self, pattern_num, matrix):
        super(QtPattern, self).__init__(pattern_num, matrix)
        self.write(self.qt_patterns[pattern_num-2])

class TexturePattern(TilingPattern):

    def __init__(self, pixmap, matrix, pdf, clone=None):
        if clone is None:
            image = pixmap.toImage()
            cache_key = pixmap.cacheKey()
            imgref = pdf.add_image(image, cache_key)
            paint_type = (2 if image.format() in {QImage.Format_MonoLSB,
                                                QImage.Format_Mono} else 1)
            super(TexturePattern, self).__init__(
                cache_key, matrix, w=image.width(), h=image.height(),
                paint_type=paint_type)
            m = (self.w, 0, 0, -self.h, 0, self.h)
            self.resources['XObject'] = Dictionary({'Texture':imgref})
            self.write_line('%s cm /Texture Do'%(' '.join(map(fmtnum, m))))
        else:
            super(TexturePattern, self).__init__(
                clone.cache_key[1], matrix, w=clone.w, h=clone.h,
                paint_type=clone.paint_type)
            self.resources['XObject'] = Dictionary(clone.resources['XObject'])
            self.write(clone.getvalue())

class GraphicsState(object):

    FIELDS = ('fill', 'stroke', 'opacity', 'transform', 'brush_origin',
                  'clip_updated', 'do_fill', 'do_stroke')

    def __init__(self):
        self.fill = QBrush()
        self.stroke = QPen()
        self.opacity = 1.0
        self.transform = QTransform()
        self.brush_origin = QPointF()
        self.clip_updated = False
        self.do_fill = False
        self.do_stroke = True
        self.qt_pattern_cache = {}

    def __eq__(self, other):
        for x in self.FIELDS:
            if getattr(other, x) != getattr(self, x):
                return False
        return True

    def copy(self):
        ans = GraphicsState()
        ans.fill = QBrush(self.fill)
        ans.stroke = QPen(self.stroke)
        ans.opacity = self.opacity
        ans.transform = self.transform * QTransform()
        ans.brush_origin = QPointF(self.brush_origin)
        ans.clip_updated = self.clip_updated
        ans.do_fill, ans.do_stroke = self.do_fill, self.do_stroke
        return ans

class Graphics(object):

    def __init__(self, page_width_px, page_height_px):
        self.base_state = GraphicsState()
        self.current_state = GraphicsState()
        self.pending_state = None
        self.page_width_px, self.page_height_px = (page_width_px, page_height_px)

    def begin(self, pdf):
        self.pdf = pdf

    def update_state(self, state, painter):
        flags = state.state()
        if self.pending_state is None:
            self.pending_state = self.current_state.copy()

        s = self.pending_state

        if flags & QPaintEngine.DirtyTransform:
            s.transform = state.transform()

        if flags & QPaintEngine.DirtyBrushOrigin:
            s.brush_origin = state.brushOrigin()

        if flags & QPaintEngine.DirtyBrush:
            s.fill = state.brush()

        if flags & QPaintEngine.DirtyPen:
            s.stroke = state.pen()

        if flags & QPaintEngine.DirtyOpacity:
            s.opacity = state.opacity()

        if flags & QPaintEngine.DirtyClipPath or flags & QPaintEngine.DirtyClipRegion:
            s.clip_updated = True

    def reset(self):
        self.current_state = GraphicsState()
        self.pending_state = None

    def __call__(self, pdf_system, painter):
        # Apply the currently pending state to the PDF
        if self.pending_state is None:
            return

        pdf_state = self.current_state
        ps = self.pending_state
        pdf = self.pdf

        if ps.transform != pdf_state.transform or ps.clip_updated:
            pdf.restore_stack()
            pdf.save_stack()
            pdf_state = self.base_state

        if (pdf_state.transform != ps.transform):
            pdf.transform(ps.transform)

        if (pdf_state.opacity != ps.opacity or pdf_state.stroke != ps.stroke):
            self.apply_stroke(ps, pdf_system, painter)

        if (pdf_state.opacity != ps.opacity or pdf_state.fill != ps.fill or
            pdf_state.brush_origin != ps.brush_origin):
            self.apply_fill(ps, pdf_system, painter)

        if ps.clip_updated:
            ps.clip_updated = False
            path = painter.clipPath()
            if not path.isEmpty():
                p = convert_path(path)
                fill_rule = {Qt.OddEvenFill:'evenodd',
                            Qt.WindingFill:'winding'}[path.fillRule()]
                pdf.add_clip(p, fill_rule=fill_rule)

        self.current_state = self.pending_state
        self.pending_state = None

    def convert_brush(self, brush, brush_origin, global_opacity,
                      pdf_system, qt_system):
        # Convert a QBrush to PDF operators
        style = brush.style()
        pdf = self.pdf

        pattern = color = pat = None
        opacity = global_opacity
        do_fill = True

        matrix = (QTransform.fromTranslate(brush_origin.x(), brush_origin.y())
                  * pdf_system * qt_system.inverted()[0])
        vals = list(brush.color().getRgbF())
        self.brushobj = None

        if style <= Qt.DiagCrossPattern:
            opacity *= vals[-1]
            color = vals[:3]

            if style > Qt.SolidPattern:
                pat = QtPattern(style, matrix)

        elif style == Qt.TexturePattern:
            pat = TexturePattern(brush.texture(), matrix, pdf)
            if pat.paint_type == 2:
                opacity *= vals[-1]
                color = vals[:3]

        elif False and style == Qt.LinearGradientPattern:
            pat = LinearGradientPattern(brush, matrix, pdf, self.page_width_px,
                                        self.page_height_px)
            opacity *= pat.const_opacity
        # TODO: Add support for radial/conical gradient fills

        if opacity < 1e-4 or style == Qt.NoBrush:
            do_fill = False
        self.brushobj = Brush(brush_origin, pat, color)

        if pat is not None:
            pattern = pdf.add_pattern(pat)
        return color, opacity, pattern, do_fill

    def apply_stroke(self, state, pdf_system, painter):
        # TODO: Support miter limit by using QPainterPathStroker
        pen = state.stroke
        self.pending_state.do_stroke = True
        pdf = self.pdf

        # Width
        w = pen.widthF()
        if pen.isCosmetic():
            t = painter.transform()
            w /= sqrt(t.m11()**2 + t.m22()**2)
        pdf.serialize(w)
        pdf.current_page.write(' w ')

        # Line cap
        cap = {Qt.FlatCap:0, Qt.RoundCap:1, Qt.SquareCap:
               2}.get(pen.capStyle(), 0)
        pdf.current_page.write('%d J '%cap)

        # Line join
        join = {Qt.MiterJoin:0, Qt.RoundJoin:1,
                Qt.BevelJoin:2}.get(pen.joinStyle(), 0)
        pdf.current_page.write('%d j '%join)

        # Dash pattern
        ps = {Qt.DashLine:[3], Qt.DotLine:[1,2], Qt.DashDotLine:[3,2,1,2],
              Qt.DashDotDotLine:[3, 2, 1, 2, 1, 2]}.get(pen.style(), [])
        if ps:
            pdf.serialize(Array(ps))
            pdf.current_page.write(' 0 d ')

        # Stroke fill
        color, opacity, pattern, self.pending_state.do_stroke = self.convert_brush(
            pen.brush(), state.brush_origin, state.opacity, pdf_system,
            painter.transform())
        self.pdf.apply_stroke(color, pattern, opacity)
        if pen.style() == Qt.NoPen:
            self.pending_state.do_stroke = False

    def apply_fill(self, state, pdf_system, painter):
        self.pending_state.do_fill = True
        color, opacity, pattern, self.pending_state.do_fill = self.convert_brush(
            state.fill, state.brush_origin, state.opacity, pdf_system,
            painter.transform())
        self.pdf.apply_fill(color, pattern, opacity)
        self.last_fill = self.brushobj

    def __enter__(self):
        self.pdf.save_stack()

    def __exit__(self, *args):
        self.pdf.restore_stack()

    def resolve_fill(self, rect, pdf_system, qt_system):
        '''
        Qt's paint system does not update brushOrigin when using
        TexturePatterns and it also uses TexturePatterns to emulate gradients,
        leading to brokenness. So this method allows the paint engine to update
        the brush origin before painting an object. While not perfect, this is
        better than nothing.
        '''
        if not hasattr(self, 'last_fill') or not self.current_state.do_fill:
            return

        if isinstance(self.last_fill.brush, TexturePattern):
            tl = rect.topLeft()
            if tl == self.last_fill.origin:
                return

            matrix = (QTransform.fromTranslate(tl.x(), tl.y())
                * pdf_system * qt_system.inverted()[0])

            pat = TexturePattern(None, matrix, self.pdf, clone=self.last_fill.brush)
            pattern = self.pdf.add_pattern(pat)
            self.pdf.apply_fill(self.last_fill.color, pattern)


