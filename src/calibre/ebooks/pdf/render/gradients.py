#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
from math import floor, ceil
from future_builtins import map

import sip
from PyQt4.Qt import (QPointF, QGradient, QLinearGradient)

from calibre.ebooks.pdf.render.common import Stream, Name, Array, Dictionary

def write_triple(data, val):
    data.write(bytes(bytearray((
        (val >> 16) & 0xff, (val >> 8) & 0xff, val & 0xff))))

def write_byte(data, val):
    data.write(bytes(bytearray([val&0xff])))

def write_triangle_line(data, xpos, ypos, xoff, yoff, rgb, flag, alpha):
    for xo, yo in ( (0, 0), (xoff, yoff) ):
        write_byte(data, flag)
        write_triple(data, xpos+xo)
        write_triple(data, ypos+yo)
        if alpha:
            write_byte(data, rgb[-1])
        else:
            for x in rgb[:3]:
                write_byte(data, x)

class LinearShader(Stream):

    def __init__(self, is_transparent, xmin, xmax, ymin, ymax):
        Stream.__init__(self, compress=False)
        self.is_transparent = is_transparent
        self.xmin, self.xmax, self.ymin, self.ymax = (xmin, xmax, ymin, ymax)
        self.cache_key = None

    def add_extra_keys(self, d):
        d['ShadingType'] = 4
        d['ColorSpace'] = Name('DeviceGray' if self.is_transparent else 'DeviceRGB')
        d['AntiAlias'] = True
        d['BitsPerCoordinate'] = 24
        d['BitsPerComponent'] = 8
        d['BitsPerFlag'] = 8
        a = ([0, 1] if self.is_transparent else [0, 1, 0, 1, 0, 1])
        d['Decode'] = Array([self.xmin, self.xmax, self.ymin, self.ymax]+a)
        d['AntiAlias'] = True

def generate_linear_gradient_shader(gradient, page_rect, is_transparent=False):
    start = gradient.start()
    stop = gradient.finalStop()
    stops = list(map(list, gradient.stops()))
    offset = stop - start
    spread = gradient.spread()

    if gradient.spread() == QGradient.ReflectSpread:
        offset *= 2
        for i in xrange(len(stops) - 2, -1, -1):
            s = stops[i]
            s[0] = 2. - s[0]
            stops.append(s)
        for i in xrange(len(stops)):
            stops[i][0] /= 2.

    orthogonal = QPointF(offset.y(), -offset.x())
    length = offset.x()*offset.x() + offset.y()*offset.y()

    # find the max and min values in offset and orth direction that are needed to cover
    # the whole page
    off_min = sys.maxint
    off_max = -sys.maxint - 1
    ort_min = sys.maxint
    ort_max = -sys.maxint - 1
    for i in xrange(4):
        off = ((page_rect[i].x() - start.x()) * offset.x() + (page_rect[i].y() - start.y()) * offset.y())/length
        ort = ((page_rect[i].x() - start.x()) * orthogonal.x() + (page_rect[i].y() - start.y()) * orthogonal.y())/length
        off_min = min(off_min, int(floor(off)))
        off_max = max(off_max, int(ceil(off)))
        ort_min = min(ort_min, ort)
        ort_max = max(ort_max, ort)
    ort_min -= 1
    ort_max += 1

    start += off_min * offset + ort_min * orthogonal
    orthogonal *= (ort_max - ort_min)
    num = off_max - off_min

    gradient_rect = [ start, start + orthogonal, start + num*offset, start +
                     num*offset + orthogonal]

    xmin = gradient_rect[0].x()
    xmax = gradient_rect[0].x()
    ymin = gradient_rect[0].y()
    ymax = gradient_rect[0].y()
    for i in xrange(1, 4):
        xmin = min(xmin, gradient_rect[i].x())
        xmax = max(xmax, gradient_rect[i].x())
        ymin = min(ymin, gradient_rect[i].y())
        ymax = max(ymax, gradient_rect[i].y())
    xmin -= 1000
    xmax += 1000
    ymin -= 1000
    ymax += 1000
    start -= QPointF(xmin, ymin)
    factor_x = float(1<<24)/(xmax - xmin)
    factor_y = float(1<<24)/(ymax - ymin)
    xoff = int(orthogonal.x()*factor_x)
    yoff = int(orthogonal.y()*factor_y)

    triangles = LinearShader(is_transparent, xmin, xmax, ymin, ymax)
    if spread == QGradient.PadSpread:
        if (off_min > 0 or off_max < 1):
            # linear gradient outside of page
            current_stop = stops[len(stops)-1] if off_min > 0 else stops[0]
            rgb = current_stop[1].getRgb()
            xpos = int(start.x()*factor_x)
            ypos = int(start.y()*factor_y)
            write_triangle_line(triangles, xpos, ypos, xoff, yoff, rgb, 0,
                              is_transparent)
            start += num*offset
            xpos = int(start.x()*factor_x)
            ypos = int(start.y()*factor_y)
            write_triangle_line(triangles, xpos, ypos, xoff, yoff, rgb, 1,
                              is_transparent)
        else:
            flag = 0
            if off_min < 0:
                rgb = stops[0][1].getRgb()
                xpos = int(start.x()*factor_x)
                ypos = int(start.y()*factor_y)
                write_triangle_line(triangles, xpos, ypos, xoff, yoff, rgb, flag,
                                  is_transparent)
                start -= off_min*offset
                flag = 1
            for s, current_stop in enumerate(stops):
                rgb = current_stop[1].getRgb()
                xpos = int(start.x()*factor_x)
                ypos = int(start.y()*factor_y)
                write_triangle_line(triangles, xpos, ypos, xoff, yoff, rgb, flag,
                                  is_transparent)
                if s < len(stops)-1:
                    start += offset*(stops[s+1][0] - stops[s][0])
                flag = 1

            if off_max > 1:
                start += (off_max - 1)*offset
                rgb = stops[len(stops)-1][1].getRgb()
                xpos = int(start.x()*factor_x)
                ypos = int(start.y()*factor_y)
                write_triangle_line(triangles, xpos, ypos, xoff, yoff, rgb, flag,
                                  is_transparent);

    else:
        for i in xrange(num):
            flag = 0
            for s in xrange(len(stops)):
                rgb = stops[s][1].getRgb()
                xpos = int(start.x()*factor_x)
                ypos = int(start.y()*factor_y)
                write_triangle_line(triangles, xpos, ypos, xoff, yoff, rgb, flag,
                                  is_transparent)
                if s < len(stops)-1:
                    start += offset*(stops[s+1][0] - stops[s][0])
                flag = 1

    t = triangles
    t.cache_key = (t.xmin, t.xmax, t.ymin, t.ymax, t.is_transparent, hash(t.getvalue()))
    return triangles

class LinearGradientPattern(Dictionary):

    def __init__(self, brush, matrix, pdf, pixel_page_width, pixel_page_height):
        self.matrix = (matrix.m11(), matrix.m12(), matrix.m21(), matrix.m22(),
                       matrix.dx(), matrix.dy())
        gradient = sip.cast(brush.gradient(), QLinearGradient)
        inv = matrix.inverted()[0]

        page_rect = tuple(map(inv.map, (
            QPointF(0, 0), QPointF(pixel_page_width, 0), QPointF(0, pixel_page_height),
            QPointF(pixel_page_width, pixel_page_height))))

        shader = generate_linear_gradient_shader(gradient, page_rect)
        self.const_opacity = 1.0
        if not brush.isOpaque():
            # TODO: Handle colors with different opacities in the gradient
            self.const_opacity = gradient.stops()[0][1].alphaF()

        self.shaderref = pdf.add_shader(shader)

        d = {}
        d['Type'] = Name('Pattern')
        d['PatternType'] = 2
        d['Shading'] = self.shaderref
        d['Matrix'] = Array(self.matrix)
        Dictionary.__init__(self, d)

        self.cache_key = (self.__class__.__name__, self.matrix,
                          repr(self.shaderref))

