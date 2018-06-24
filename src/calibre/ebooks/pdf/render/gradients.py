#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, copy
from future_builtins import map
from collections import namedtuple

from PyQt5.Qt import QLinearGradient, QPointF
try:
    from PyQt5 import sip
except ImportError:
    import sip

from calibre.ebooks.pdf.render.common import Name, Array, Dictionary

Stop = namedtuple('Stop', 't color')


class LinearGradientPattern(Dictionary):

    def __init__(self, brush, matrix, pdf, pixel_page_width, pixel_page_height):
        self.matrix = (matrix.m11(), matrix.m12(), matrix.m21(), matrix.m22(),
                       matrix.dx(), matrix.dy())
        gradient = sip.cast(brush.gradient(), QLinearGradient)

        start, stop, stops = self.spread_gradient(gradient, pixel_page_width,
                                                  pixel_page_height, matrix)

        # TODO: Handle colors with different opacities
        self.const_opacity = stops[0].color[-1]

        funcs = Array()
        bounds = Array()
        encode = Array()

        for i, current_stop in enumerate(stops):
            if i < len(stops) - 1:
                next_stop = stops[i+1]
                func = Dictionary({
                    'FunctionType': 2,
                    'Domain': Array([0, 1]),
                    'C0': Array(current_stop.color[:3]),
                    'C1': Array(next_stop.color[:3]),
                    'N': 1,
                })
                funcs.append(func)
                encode.extend((0, 1))
                if i+1 < len(stops) - 1:
                    bounds.append(next_stop.t)

        func = Dictionary({
            'FunctionType': 3,
            'Domain': Array([stops[0].t, stops[-1].t]),
            'Functions': funcs,
            'Bounds': bounds,
            'Encode': encode,
        })

        shader = Dictionary({
            'ShadingType': 2,
            'ColorSpace': Name('DeviceRGB'),
            'AntiAlias': True,
            'Coords': Array([start.x(), start.y(), stop.x(), stop.y()]),
            'Function': func,
            'Extend': Array([True, True]),
        })

        Dictionary.__init__(self, {
            'Type': Name('Pattern'),
            'PatternType': 2,
            'Shading': shader,
            'Matrix': Array(self.matrix),
        })

        self.cache_key = (self.__class__.__name__, self.matrix,
                          tuple(shader['Coords']), stops)

    def spread_gradient(self, gradient, pixel_page_width, pixel_page_height,
                        matrix):
        start = gradient.start()
        stop = gradient.finalStop()
        stops = list(map(lambda x: [x[0], x[1].getRgbF()], gradient.stops()))
        spread = gradient.spread()
        if spread != gradient.PadSpread:
            inv = matrix.inverted()[0]
            page_rect = tuple(map(inv.map, (
                QPointF(0, 0), QPointF(pixel_page_width, 0), QPointF(0, pixel_page_height),
                QPointF(pixel_page_width, pixel_page_height))))
            maxx = maxy = -sys.maxint-1
            minx = miny = sys.maxint

            for p in page_rect:
                minx, maxx = min(minx, p.x()), max(maxx, p.x())
                miny, maxy = min(miny, p.y()), max(maxy, p.y())

            def in_page(point):
                return (minx <= point.x() <= maxx and miny <= point.y() <= maxy)

            offset = stop - start
            llimit, rlimit = start, stop

            reflect = False
            base_stops = copy.deepcopy(stops)
            reversed_stops = list(reversed(stops))
            do_reflect = spread == gradient.ReflectSpread
            totl = abs(stops[-1][0] - stops[0][0])
            intervals = [abs(stops[i+1][0] - stops[i][0])/totl
                         for i in xrange(len(stops)-1)]

            while in_page(llimit):
                reflect ^= True
                llimit -= offset
                estops = reversed_stops if (reflect and do_reflect) else base_stops
                stops = copy.deepcopy(estops) + stops

            first_is_reflected = reflect
            reflect = False

            while in_page(rlimit):
                reflect ^= True
                rlimit += offset
                estops = reversed_stops if (reflect and do_reflect) else base_stops
                stops = stops + copy.deepcopy(estops)

            start, stop = llimit, rlimit

            num = len(stops) // len(base_stops)
            if num > 1:
                # Adjust the stop parameter values
                t = base_stops[0][0]
                rlen = totl/num
                reflect = first_is_reflected ^ True
                intervals = [i*rlen for i in intervals]
                rintervals = list(reversed(intervals))

                for i in xrange(num):
                    reflect ^= True
                    pos = i * len(base_stops)
                    tvals = [t]
                    for ival in (rintervals if reflect and do_reflect else
                                 intervals):
                        tvals.append(tvals[-1] + ival)
                    for j in xrange(len(base_stops)):
                        stops[pos+j][0] = tvals[j]
                    t = tvals[-1]

                # In case there were rounding errors
                stops[-1][0] = base_stops[-1][0]

        return start, stop, tuple(Stop(s[0], s[1]) for s in stops)
