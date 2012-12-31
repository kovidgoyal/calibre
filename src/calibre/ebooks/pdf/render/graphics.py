#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from math import sqrt

from PyQt4.Qt import (QBrush, QPen, Qt, QPointF, QTransform, QPainterPath,
                      QPaintEngine)

from calibre.ebooks.pdf.render.common import Array
from calibre.ebooks.pdf.render.serialize import Path, Color

def convert_path(path):
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


class GraphicsState(object):

    FIELDS = ('fill', 'stroke', 'opacity', 'transform', 'brush_origin',
                  'clip', 'do_fill', 'do_stroke')

    def __init__(self):
        self.fill = QBrush()
        self.stroke = QPen()
        self.opacity = 1.0
        self.transform = QTransform()
        self.brush_origin = QPointF()
        self.clip = QPainterPath()
        self.do_fill = False
        self.do_stroke = True

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
        ans.clip = self.clip
        ans.do_fill, ans.do_stroke = self.do_fill, self.do_stroke
        return ans

class Graphics(object):

    def __init__(self):
        self.base_state = GraphicsState()
        self.current_state = GraphicsState()
        self.pending_state = None

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
            s.clip = painter.clipPath()

    def reset(self):
        self.current_state = GraphicsState()
        self.pending_state = None

    def __call__(self, pdf, pdf_system, painter):
        # Apply the currently pending state to the PDF
        if self.pending_state is None:
            return

        pdf_state = self.current_state
        ps = self.pending_state

        if (ps.transform != pdf_state.transform or ps.clip != pdf_state.clip):
            pdf.restore_stack()
            pdf.save_stack()
            pdf_state = self.base_state

        if (pdf_state.transform != ps.transform):
            pdf.transform(ps.transform)

        if (pdf_state.opacity != ps.opacity or pdf_state.stroke != ps.stroke):
            self.apply_stroke(ps, pdf, pdf_system, painter)

        if (pdf_state.opacity != ps.opacity or pdf_state.fill != ps.fill or
            pdf_state.brush_origin != ps.brush_origin):
            self.apply_fill(ps, pdf, pdf_system, painter)

        if (pdf_state.clip != ps.clip):
            p = convert_path(ps.clip)
            fill_rule = {Qt.OddEvenFill:'evenodd',
                        Qt.WindingFill:'winding'}[ps.clip.fillRule()]
            pdf.add_clip(p, fill_rule=fill_rule)

        self.current_state = self.pending_state
        self.pending_state = None

    def apply_stroke(self, state, pdf, pdf_system, painter):
        # TODO: Handle pens with non solid brushes by setting the colorspace
        # for stroking to a pattern
        # TODO: Support miter limit by using QPainterPathStroker
        pen = state.stroke
        self.pending_state.do_stroke = True
        if pen.style() == Qt.NoPen:
            self.pending_state.do_stroke = False

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
            pdf.current_page.write(' d ')

        # Stroke fill
        b = pen.brush()
        vals = list(b.color().getRgbF())
        vals[-1] *= state.opacity
        color = Color(*vals)
        pdf.set_stroke_color(color)

        if vals[-1] < 1e-5 or b.style() == Qt.NoBrush:
            self.pending_state.do_stroke = False

    def apply_fill(self, state, pdf, pdf_system, painter):
        self.pending_state.do_fill = True
        b = state.fill
        if b.style() == Qt.NoBrush:
            self.pending_state.do_fill = False
        vals = list(b.color().getRgbF())
        vals[-1] *= state.opacity
        color = Color(*vals)
        pdf.set_fill_color(color)

