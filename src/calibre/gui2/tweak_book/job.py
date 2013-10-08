#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import time
from threading import Thread
from functools import partial

from PyQt4.Qt import (QWidget, QVBoxLayout, QLabel, Qt, QPainter, QBrush, QColor)

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
        l.addWidget(self.pi, alignment=Qt.AlignHCenter)
        self.msg = QLabel('')
        l.addSpacing(10)
        l.addWidget(self.msg, alignment=Qt.AlignHCenter)
        l.addStretch(10)
        self.setVisible(False)

    def start(self):
        self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        self.setVisible(True)
        self.raise_()
        self.pi.startAnimation()

    def stop(self):
        self.pi.stopAnimation()
        self.setVisible(False)

    def job_done(self, callback, job):
        del job.callback
        self.stop()
        callback(job)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(ev.region().boundingRect(), QBrush(QColor(200, 200, 200, 160), Qt.SolidPattern))
        p.end()
        QWidget.paintEvent(self, ev)

    def __call__(self, name, user_text, callback, function, *args, **kwargs):
        self.msg.setText('<h2>%s</h2>' % user_text)
        job = LongJob(name, user_text, Dispatcher(partial(self.job_done, callback)), function, *args, **kwargs)
        job.start()
        self.start()
