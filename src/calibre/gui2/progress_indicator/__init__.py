#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

import math
from PyQt5.Qt import (
    Qt, QWidget, QSizePolicy, QSize, QRect, QConicalGradient, QPen, QBrush,
    QPainter, QTimer
)

def draw_snake_spinner(painter, rect, angle, light, dark):
    painter.setRenderHint(QPainter.Antialiasing)

    if rect.width() > rect.height():
        delta = (rect.width() - rect.height()) // 2
        rect = rect.adjusted(delta, 0, -delta, 0)
    elif rect.height() > rect.width():
        delta = (rect.height() - rect.width()) // 2
        rect = rect.adjusted(0, delta, 0, -delta)
    disc_width = max(4, rect.width() // 10)

    drawing_rect = QRect(rect.x() + disc_width, rect.y() + disc_width, rect.width() - 2 * disc_width, rect.height() - 2 *disc_width)
    try:
        angle_for_width = math.degrees(math.atan2(1.3 * disc_width, drawing_rect.width()))
    except ZeroDivisionError:
        angle_for_width = 5

    gradient = QConicalGradient(drawing_rect.center(), angle - angle_for_width)
    gradient.setColorAt(1, light)
    gradient.setColorAt(0, dark)

    painter.setPen(QPen(light, disc_width))
    painter.drawArc(drawing_rect, 0, 360 * 16)
    pen = QPen(QBrush(gradient), disc_width)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.drawArc(drawing_rect, angle * 16, (360 - 2 * angle_for_width) * 16)

class ProgressSpinner(QWidget):

    def __init__(self, parent=None, size=64, interval=10):
        QWidget.__init__(self, parent)
        self.setSizePolicy(QSizePolicy(
            QSizePolicy.GrowFlag | QSizePolicy.ShrinkFlag, QSizePolicy.GrowFlag | QSizePolicy.ShrinkFlag))
        self._size_hint = QSize(size, size)
        self.timer = t = QTimer(self)
        t.setInterval(interval)
        self.timer.timeout.connect(self.tick)
        self.loading_angle = 0
        pal = self.palette()
        self.dark = pal.color(pal.Text)
        self.light = pal.color(pal.Window)
        self.errored_out = False

    @property
    def animation_interval(self):
        return self.timer.interval()

    @animation_interval.setter
    def animation_interval(self, val):
        self.timer.setInterval(val)

    def heightForWidth(self, w):
        return w

    def set_colors(self, dark, light):
        self.dark, self.light = dark, light
        self.update()

    def start(self):
        self.loading_angle = 0
        self.timer.start()
        self.update()
    startAnimation = start

    def stop(self):
        self.timer.stop()
        self.loading_angle = 0
        self.update()
    stopAnimation = stop

    @property
    def is_animated(self):
        return self.timer.isActive()

    @is_animated.setter
    def is_animated(self, val):
        (self.start if val else self.stop)()

    def isAnimated(self):
        return self.is_animated

    def sizeHint(self):
        return self._size_hint

    def setSizeHint(self, val):
        self._size_hint = val
        self.update()
    setDisplaySize = setSizeHint

    def tick(self):
        self.loading_angle -= 2
        self.loading_angle %= 360
        self.update()

    def paintEvent(self, ev):
        if not self.errored_out:
            try:
                draw_snake_spinner(QPainter(self), self.rect(), self.loading_angle, self.light, self.dark)
            except Exception:
                import traceback
                traceback.print_exc()
                self.errored_out = True

ProgressIndicator = ProgressSpinner
if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    w = ProgressSpinner()
    w.show()
    w.start()
    app.exec_()
    del app
