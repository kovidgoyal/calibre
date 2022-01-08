#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from qt.core import (
    QToolButton, QSize, QPropertyAnimation, Qt, QMetaObject, pyqtProperty, QSizePolicy,
    QWidget, QIcon, QPainter, QStyleOptionToolButton, QStyle, QAbstractAnimation)

from calibre.gui2 import config


class ThrobbingButton(QToolButton):

    @pyqtProperty(int)
    def icon_size(self):
        return self._icon_size

    @icon_size.setter
    def icon_size(self, value):
        self._icon_size = value

    def __init__(self, *args):
        QToolButton.__init__(self, *args)
        # vertically size policy must be expanding for it to align inside a
        # toolbar
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._icon_size = -1
        QToolButton.setIcon(self, QIcon.ic('donate.png'))
        self.setText('\xa0')
        self.animation = QPropertyAnimation(self, b'icon_size', self)
        self.animation.setDuration(int(60/72.*1000))
        self.animation.setLoopCount(4)
        self.animation.valueChanged.connect(self.value_changed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.animation.finished.connect(self.animation_finished)

    def animation_finished(self):
        self.icon_size = self.iconSize().width()

    def enterEvent(self, ev):
        self.start_animation()

    def leaveEvent(self, ev):
        self.stop_animation()

    def value_changed(self, val):
        self.update()

    def start_animation(self):
        if config['disable_animations']:
            return
        if self.animation.state() != QAbstractAnimation.State.Stopped or not self.isVisible():
            return
        size = self.iconSize().width()
        smaller = int(0.7 * size)
        self.animation.setStartValue(smaller)
        self.animation.setEndValue(size)
        QMetaObject.invokeMethod(self.animation, 'start', Qt.ConnectionType.QueuedConnection)

    def stop_animation(self):
        self.animation.stop()
        self.animation_finished()

    def paintEvent(self, ev):
        size = self._icon_size if self._icon_size > 10 else self.iconSize().width()
        p = QPainter(self)
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        s = self.style()
        opt.iconSize = QSize(size, size)
        s.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, opt, p, self)


if __name__ == '__main__':
    from qt.core import QApplication, QHBoxLayout
    app = QApplication([])
    w = QWidget()
    w.setLayout(QHBoxLayout())
    b = ThrobbingButton()
    b.setIcon(QIcon.ic('donate.png'))
    w.layout().addWidget(b)
    w.show()
    b.set_normal_icon_size(64, 64)
    b.start_animation()

    app.exec()
