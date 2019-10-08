#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from PyQt5.Qt import QPainter, QPalette, QPoint, QRect, QTimer, QWidget, Qt, QFontInfo, QLabel

from calibre.gui2.progress_indicator import draw_snake_spinner


class LoadingOverlay(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setVisible(False)
        self.label = QLabel(self)
        self.label.setText('<i>testing')
        self.label.setTextFormat(Qt.RichText)
        self.label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.resize(parent.size())
        self.move(0, 0)
        self.angle = 0
        self.timer = t = QTimer(self)
        t.setInterval(60)
        t.timeout.connect(self.tick)
        f = self.font()
        f.setBold(True)
        fm = QFontInfo(f)
        f.setPixelSize(int(fm.pixelSize() * 1.5))
        self.label.setFont(f)
        self.calculate_rects()

    def tick(self):
        self.angle -= 6
        self.angle %= 360
        self.update()

    def __call__(self, msg=''):
        self.label.setText(msg)
        self.resize(self.parent().size())
        self.move(0, 0)
        self.setVisible(True)
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)
        self.update()

    def hide(self):
        self.parent().web_view.setFocus(Qt.OtherFocusReason)
        return QWidget.hide(self)

    def showEvent(self, ev):
        self.timer.start()

    def hideEvent(self, ev):
        self.timer.stop()

    def calculate_rects(self):
        rect = self.rect()
        self.spinner_rect = r = QRect(0, 0, 96, 96)
        r.moveCenter(rect.center() - QPoint(0, r.height() // 2))
        r = QRect(r)
        r.moveTop(r.center().y() +  20 + r.height() // 2)
        r.setLeft(0), r.setRight(self.width())
        self.label.setGeometry(r)

    def resizeEvent(self, ev):
        self.calculate_rects()
        return QWidget.resizeEvent(self, ev)

    def do_paint(self, painter):
        pal = self.palette()
        color = pal.color(QPalette.Window)
        color.setAlphaF(0.8)
        painter.fillRect(self.rect(), color)
        draw_snake_spinner(painter, self.spinner_rect, self.angle, pal.color(QPalette.Window), pal.color(QPalette.WindowText))

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        try:
            self.do_paint(painter)
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            painter.end()
