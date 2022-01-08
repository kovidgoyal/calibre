#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import (
    QAbstractAnimation, QBrush, QColor, QEasingCurve, QPainter, QPainterPath,
    QPalette, QPoint, QPointF, QPropertyAnimation, QRect, Qt, QWidget
)

from calibre.gui2 import config


class Pointer(QWidget):

    def __init__(self, gui):
        QWidget.__init__(self, gui)
        self.setObjectName('jobs_pointer')
        self.setVisible(False)
        self.resize(100, 80)
        self.animation = QPropertyAnimation(self, b"geometry", self)
        self.animation.setDuration(750)
        self.animation.setLoopCount(2)
        self.animation.setEasingCurve(QEasingCurve.Type.Linear)
        self.animation.finished.connect(self.hide)

        taily, heady = 0, 55
        self.arrow_path = QPainterPath(QPointF(40, taily))
        self.arrow_path.lineTo(40, heady)
        self.arrow_path.lineTo(20, heady)
        self.arrow_path.lineTo(50, self.height())
        self.arrow_path.lineTo(80, heady)
        self.arrow_path.lineTo(60, heady)
        self.arrow_path.lineTo(60, taily)
        self.arrow_path.closeSubpath()

        c = self.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)
        self.color = QColor(c)
        self.color.setAlpha(100)
        self.brush = QBrush(self.color, Qt.BrushStyle.SolidPattern)

        # from qt.core import QTimer
        # QTimer.singleShot(1000, self.start)

    @property
    def gui(self):
        return self.parent()

    def point_at(self, frac):
        return (self.path.pointAtPercent(frac).toPoint() -
                QPoint(self.rect().center().x(), self.height()))

    def rect_at(self, frac):
        return QRect(self.point_at(frac), self.size())

    def abspos(self, widget):
        pos = widget.pos()
        parent = widget.parent()
        while parent is not self.gui:
            pos += parent.pos()
            parent = parent.parent()
        return pos

    def start(self):
        if config['disable_animations']:
            return
        self.setVisible(True)
        self.raise_()
        end = self.abspos(self.gui.jobs_button)
        end = QPointF(end.x() + self.gui.jobs_button.width()/3.0, end.y()+20)
        start = QPointF(end.x(), end.y() - 0.5*self.height())
        self.path = QPainterPath(QPointF(start))
        self.path.lineTo(end)
        self.path.closeSubpath()
        self.animation.setStartValue(self.rect_at(0.0))
        self.animation.setEndValue(self.rect_at(1.0))
        self.animation.setDirection(QAbstractAnimation.Direction.Backward)
        num_keys = 100
        for i in range(1, num_keys):
            i /= num_keys
            self.animation.setKeyValueAt(i, self.rect_at(i))
        self.animation.start()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing)
        p.setBrush(self.brush)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(self.arrow_path)
        p.end()
