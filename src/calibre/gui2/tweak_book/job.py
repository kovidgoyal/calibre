#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import time
from functools import partial
from threading import Thread
from typing import TYPE_CHECKING

from qt.core import QApplication, QBrush, QCursor, QLabel, QPainter, QRect, Qt, QVBoxLayout, QWidget

from calibre.gui2 import Dispatcher
from calibre.gui2.progress_indicator import ProgressIndicator

if TYPE_CHECKING:
    from collections.abc import Callable

    from qt.core import QPaintEvent


class LongJob[T](Thread):
    daemon = True
    result: T | None
    traceback: str | None
    time_taken: float | None

    def __init__(
        self, name: str, user_text: str, callback: Callable[[LongJob[T]], object], function: Callable[..., T], *args: object, **kwargs: object
    ) -> None:
        Thread.__init__(self, name=name)
        self.user_text = user_text
        self.function = function
        self.args, self.kwargs = args, kwargs
        self.result = self.traceback = None
        self.time_taken = None
        self.callback = callback

    def run(self) -> None:
        st = time.time()
        try:
            self.result = self.function(*self.args, **self.kwargs)
        except Exception:
            import traceback

            self.traceback = traceback.format_exc()
        self.time_taken = time.time() - st
        try:
            self.callback(self)
        finally:
            pass


class BlockingJob(QWidget):
    def __init__(self, parent: QWidget | None) -> None:
        QWidget.__init__(self, parent)
        l = QVBoxLayout()
        self.setLayout(l)
        l.addStretch(10)
        self.pi = ProgressIndicator(self, 128)
        l.addWidget(self.pi, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.dummy = QLabel('<h2>\xa0')
        l.addSpacing(10)
        l.addWidget(self.dummy, alignment=Qt.AlignmentFlag.AlignHCenter)
        l.addStretch(10)
        self.setVisible(False)
        self.text = ''
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def start(self) -> None:
        p = self.parent()
        assert isinstance(p, QWidget)
        self.setGeometry(0, 0, p.width(), p.height())
        self.setVisible(True)
        # Prevent any actions from being triggered by key presses
        p.setEnabled(False)
        self.raise_and_focus()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.pi.startAnimation()
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))

    def stop(self) -> None:
        QApplication.restoreOverrideCursor()
        self.pi.stopAnimation()
        self.setVisible(False)
        p = self.parent()
        assert isinstance(p, QWidget)
        p.setEnabled(True)
        # The following line is needed on OS X, because of this bug:
        # https://bugreports.qt-project.org/browse/QTBUG-34371 it causes
        # keyboard events to no longer work
        p.setFocus(Qt.FocusReason.OtherFocusReason)

    def job_done[T](self, callback: Callable[[LongJob[T]], object], job: LongJob[T]) -> None:
        del job.callback
        self.stop()
        callback(job)

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        assert a0 is not None
        br = a0.region().boundingRect()
        p = QPainter(self)
        p.setOpacity(0.2)
        p.fillRect(br, QBrush(self.palette().text()))
        p.end()
        QWidget.paintEvent(self, a0)
        p = QPainter(self)
        p.setClipRect(br)
        f = p.font()
        f.setBold(True)
        f.setPointSize(20)
        p.setFont(f)
        p.setPen(Qt.PenStyle.SolidLine)
        r = QRect(0, self.dummy.geometry().top() + 10, self.geometry().width(), 150)
        p.drawText(r, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextSingleLine, self.text)
        p.end()

    def set_msg(self, text: str) -> None:
        self.text = text

    def __call__[T](
        self, name: str, user_text: str, callback: Callable[[LongJob[T]], object], function: Callable[..., T], *args: object, **kwargs: object
    ) -> None:
        "Run a job that blocks the GUI providing some feedback to the user"
        self.set_msg(user_text)
        job = LongJob(name, user_text, Dispatcher(partial(self.job_done, callback)), function, *args, **kwargs)
        job.start()
        self.start()
