#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import time
from threading import Thread
from functools import partial

from qt.core import (QWidget, QVBoxLayout, QLabel, Qt, QPainter, QBrush, QRect, QApplication, QCursor)

from calibre.gui2 import Dispatcher
from calibre.gui2.progress_indicator import ProgressIndicator


class LongJob(Thread):

    daemon = True

    def __init__(self, name, user_text, callback, function, *args, **kwargs):
        Thread.__init__(self, name=name)
        self.user_text = user_text
        self.function = function
        self.args, self.kwargs = args, kwargs
        self.result = self.traceback = None
        self.time_taken = None
        self.callback = callback

    def run(self):
        st = time.time()
        try:
            self.result = self.function(*self.args, **self.kwargs)
        except:
            import traceback
            self.traceback = traceback.format_exc()
        self.time_taken = time.time() - st
        try:
            self.callback(self)
        finally:
            pass


class BlockingJob(QWidget):

    def __init__(self, parent):
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

    def start(self):
        self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        self.setVisible(True)
        # Prevent any actions from being triggered by key presses
        self.parent().setEnabled(False)
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.pi.startAnimation()
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))

    def stop(self):
        QApplication.restoreOverrideCursor()
        self.pi.stopAnimation()
        self.setVisible(False)
        self.parent().setEnabled(True)
        # The following line is needed on OS X, because of this bug:
        # https://bugreports.qt-project.org/browse/QTBUG-34371 it causes
        # keyboard events to no longer work
        self.parent().setFocus(Qt.FocusReason.OtherFocusReason)

    def job_done(self, callback, job):
        del job.callback
        self.stop()
        callback(job)

    def paintEvent(self, ev):
        br = ev.region().boundingRect()
        p = QPainter(self)
        p.setOpacity(0.2)
        p.fillRect(br, QBrush(self.palette().text()))
        p.end()
        QWidget.paintEvent(self, ev)
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

    def set_msg(self, text):
        self.text = text

    def __call__(self, name, user_text, callback, function, *args, **kwargs):
        ' Run a job that blocks the GUI providing some feedback to the user '
        self.set_msg(user_text)
        job = LongJob(name, user_text, Dispatcher(partial(self.job_done, callback)), function, *args, **kwargs)
        job.start()
        self.start()
