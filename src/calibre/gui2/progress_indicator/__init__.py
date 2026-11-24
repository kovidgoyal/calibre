#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from qt.core import QDialog, QIcon, QLabel, QSizePolicy, QStackedLayout, QStackedWidget, Qt, QToolButton, QVBoxLayout, QWidget, pyqtSignal

from calibre_extensions.progress_indicator import QProgressIndicator as ProgressIndicator
from calibre_extensions.progress_indicator import SpinAnimator, draw_snake_spinner  # ruff: ignore[unused-import]

if TYPE_CHECKING:
    from qt.core import QPaintEvent, QResizeEvent


class WaitPanel(QWidget):
    # A discreet button can be shown in the bottom right corner, via
    # enable_corner_button(), for acting on whatever is being waited for,
    # typically to abandon, stop or retry it.
    corner_button_clicked = pyqtSignal()

    def __init__(self, msg: str, parent: QWidget | None = None, size: int = 256, interval: int = 10) -> None:
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
        # Overlaid rather than put in the layout, so that enabling it does not
        # move the spinner and its message off center.
        self.corner_button = cb = QToolButton(self)
        cb.setAutoRaise(True)
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.clicked.connect(self.corner_button_clicked)
        cb.hide()

    def enable_corner_button(self, icon_name: str = 'view-refresh.png', tooltip: str = '') -> None:
        self.corner_button.setIcon(QIcon.ic(icon_name))
        self.corner_button.setToolTip(tooltip)
        self.corner_button.show()
        self.position_corner_button()

    def position_corner_button(self) -> None:
        if self.corner_button.isHidden():
            return
        margin = 4
        s = self.corner_button.sizeHint()
        # it is not in a layout, so it has to be given its size as well
        self.corner_button.setGeometry(self.width() - s.width() - margin, self.height() - s.height() - margin, s.width(), s.height())
        self.corner_button.raise_()

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        self.position_corner_button()  # it is positioned relative to the panel corner

    @property
    def msg(self) -> str:
        return self.la.text()

    @msg.setter
    def msg(self, val: str) -> None:
        self.la.setText(val)


class WaitStack(QStackedWidget):
    corner_button_clicked = pyqtSignal()

    def __init__(self, msg: str, after: QWidget | None = None, parent: QWidget | None = None, size: int = 256, interval: int = 10) -> None:
        QStackedWidget.__init__(self, parent)
        self.wp = WaitPanel(msg, self, size, interval)
        self.wp.corner_button_clicked.connect(self.corner_button_clicked)
        if after is None:
            after = QWidget(self)
        self.after = after
        self.addWidget(self.wp)
        self.addWidget(after)

    def enable_corner_button(self, icon_name: str = 'view-refresh.png', tooltip: str = '') -> None:
        # A discreet button in the bottom right corner of the wait panel, for
        # acting on what is being waited for, see WaitPanel.
        self.wp.enable_corner_button(icon_name, tooltip)

    def start(self) -> None:
        self.setCurrentWidget(self.wp)
        self.wp.start()

    def stop(self) -> None:
        self.wp.stop()
        self.setCurrentWidget(self.after)

    @property
    def msg(self) -> str:
        return self.wp.msg

    @msg.setter
    def msg(self, val: str) -> None:
        self.wp.msg = val


class WaitLayout(QStackedLayout):
    def __init__(self, msg: str, after: QWidget | None = None, parent: QWidget | None = None, size: int = 256, interval: int = 10) -> None:
        QStackedLayout.__init__(self, parent)
        self.wp = WaitPanel(msg, parent, size, interval)
        if after is None:
            after = QWidget(parent)
        self.after = after
        self.addWidget(self.wp)
        self.addWidget(after)

    def start(self) -> None:
        self.setCurrentWidget(self.wp)
        self.wp.start()

    def stop(self) -> None:
        self.wp.stop()
        self.setCurrentWidget(self.after)

    @property
    def msg(self) -> str:
        return self.wp.msg

    @msg.setter
    def msg(self, val: str) -> None:
        self.wp.msg = val


def develop() -> None:
    from qt.core import QPainter, QPalette

    from calibre.gui2 import Application

    class Widget(QWidget):
        def __init__(self) -> None:
            QWidget.__init__(self)
            self.a = SpinAnimator(self)
            self.a.updated.connect(self.update)

        def paintEvent(self, a0: QPaintEvent | None) -> None:
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
