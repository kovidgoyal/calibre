#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QDialog, QLabel, QSizePolicy, QStackedLayout, QStackedWidget, Qt, QVBoxLayout, QWidget

from calibre_extensions.progress_indicator import QProgressIndicator as ProgressIndicator
from calibre_extensions.progress_indicator import SpinAnimator, draw_snake_spinner

draw_snake_spinner

class WaitPanel(QWidget):

    def __init__(self, msg, parent=None, size=256, interval=10):
        QWidget.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.l = l = QVBoxLayout(self)
        self.spinner = ProgressIndicator(self, size, interval)
        self.start, self.stop = self.spinner.start, self.spinner.stop
        l.addStretch(), l.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignCenter)
        self.la = QLabel(msg)
        f = self.la.font()
        f.setPointSize(28)
        self.la.setFont(f)
        l.addWidget(self.la, 0, Qt.AlignmentFlag.AlignCenter), l.addStretch()

    @property
    def msg(self):
        return self.la.text()

    @msg.setter
    def msg(self, val):
        self.la.setText(val)


class WaitStack(QStackedWidget):

    def __init__(self, msg, after=None, parent=None, size=256, interval=10):
        QStackedWidget.__init__(self, parent)
        self.wp = WaitPanel(msg, self, size, interval)
        if after is None:
            after = QWidget(self)
        self.after = after
        self.addWidget(self.wp)
        self.addWidget(after)

    def start(self):
        self.setCurrentWidget(self.wp)
        self.wp.start()

    def stop(self):
        self.wp.stop()
        self.setCurrentWidget(self.after)

    @property
    def msg(self):
        return self.wp.msg

    @msg.setter
    def msg(self, val):
        self.wp.msg = val


class WaitLayout(QStackedLayout):

    def __init__(self, msg, after=None, parent=None, size=256, interval=10):
        QStackedLayout.__init__(self, parent)
        self.wp = WaitPanel(msg, parent, size, interval)
        if after is None:
            after = QWidget(parent)
        self.after = after
        self.addWidget(self.wp)
        self.addWidget(after)

    def start(self):
        self.setCurrentWidget(self.wp)
        self.wp.start()

    def stop(self):
        self.wp.stop()
        self.setCurrentWidget(self.after)

    @property
    def msg(self):
        return self.wp.msg

    @msg.setter
    def msg(self, val):
        self.wp.msg = val


def develop():
    from qt.core import QPainter, QPalette

    from calibre.gui2 import Application

    class Widget(QWidget):

        def __init__(self):
            QWidget.__init__(self)
            self.a = SpinAnimator(self)
            self.a.updated.connect(self.update)

        def paintEvent(self, ev):
            p = QPainter(self)
            pal = self.palette()
            self.a.draw(p, self.rect(), pal.color(QPalette.ColorRole.WindowText))
            p.end()

    app = Application([])
    d = QDialog()
    d.resize(64, 64)
    l = QVBoxLayout(d)
    w = Widget()
    l.addWidget(w)
    w.a.start()
    d.exec()
    del d
    del app


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = QDialog()
    d.resize(64, 64)
    w = ProgressIndicator(d)
    l = QVBoxLayout(d)
    l.addWidget(w)
    w.start()
    d.exec()
    del d
    del app
