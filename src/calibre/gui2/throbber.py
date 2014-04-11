#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import QToolButton, QSize, QPropertyAnimation, Qt, \
        QMetaObject, QLabel, QVBoxLayout, QWidget

from calibre.constants import isosx
from calibre.gui2 import config

class ThrobbingButton(QToolButton):

    def __init__(self, *args):
        QToolButton.__init__(self, *args)
        self.animation = QPropertyAnimation(self, 'iconSize', self)
        self.animation.setDuration(60/72.*1000)
        self.animation.setLoopCount(4)
        self.normal_icon_size = QSize(64, 64)
        self.animation.valueChanged.connect(self.value_changed)
        self.setCursor(Qt.PointingHandCursor)
        self.animation.finished.connect(self.animation_finished)

    def set_normal_icon_size(self, w, h):
        self.normal_icon_size = QSize(w, h)
        self.setIconSize(self.normal_icon_size)
        try:
            self.setMinimumSize(self.sizeHint())
        except:
            self.setMinimumSize(QSize(w+5, h+5))

    def animation_finished(self):
        self.setIconSize(self.normal_icon_size)

    def enterEvent(self, ev):
        self.start_animation()

    def leaveEvent(self, ev):
        self.stop_animation()

    def value_changed(self, val):
        self.update()

    def start_animation(self):
        if config['disable_animations']:
            return
        if self.animation.state() != self.animation.Stopped or not self.isVisible():
            return
        size = self.normal_icon_size.width()
        smaller = int(0.7 * size)
        self.animation.setStartValue(QSize(smaller, smaller))
        self.animation.setEndValue(self.normal_icon_size)
        QMetaObject.invokeMethod(self.animation, 'start', Qt.QueuedConnection)

    def stop_animation(self):
        self.animation.stop()
        self.animation_finished()

def create_donate_widget(button):
    w = QWidget()
    w.setLayout(QVBoxLayout())
    w.layout().addWidget(button)
    if isosx:
        w.setStyleSheet('QWidget, QToolButton {background-color: none; border: none; }')
        w.layout().setContentsMargins(0,0,0,0)
        w.setContentsMargins(0,0,0,0)
        w.filler = QLabel(u'\u00a0')
        w.layout().addWidget(w.filler)
    return w

if __name__ == '__main__':
    from PyQt5.Qt import QApplication, QHBoxLayout, QIcon
    app = QApplication([])
    w = QWidget()
    w.setLayout(QHBoxLayout())
    b = ThrobbingButton()
    b.setIcon(QIcon(I('donate.png')))
    w.layout().addWidget(b)
    w.show()
    b.set_normal_icon_size(64, 64)
    b.start_animation()

    app.exec_()
