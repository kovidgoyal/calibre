#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time

class Gestures(object):

    def __init__(self):
        self.in_progress = {}

    def get_boundary_point(self, event):
        t = time.time()
        id_ = None
        if hasattr(event, 'touchPoints'):
            tps = list(event.touchPoints())
            tp = None
            for t in tps:
                if t.isPrimary():
                    tp = t
                    break
            if tp is None:
                tp = tps[0]
            gp, p = tp.screenPos(), tp.pos()
            id_ = tp.id()
        else:
            gp, p = event.globalPos(), event.pos()
        return (t, gp, p, id_)

    def start_gesture(self, typ, event):
        self.in_progress[typ] = self.get_boundary_point(event)

    def is_in_progress(self, typ):
        return typ in self.in_progress

    def end_gesture(self, typ, event, widget_rect):
        if not self.is_in_progress(typ):
            return
        start = self.in_progress[typ]
        end = self.get_boundary_point(event)
        if start[3] != end[3]:
            return
        timespan = end[0] - start[0]
        start_pos, end_pos = start[1], end[1]
        xspan = end_pos.x() - start_pos.x()
        yspan = end_pos.y() - start_pos.y()

        width = widget_rect.width()

        if timespan < 1.1 and abs(xspan) >= width/5. and \
                abs(yspan) < abs(xspan)/5.:
            # Quick horizontal gesture
            return 'line'+('left' if xspan < 0 else 'right')

        return None



