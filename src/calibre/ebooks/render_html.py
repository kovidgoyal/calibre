#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys

from PyQt5.Qt import (
    QApplication, QMarginsF, QPageLayout, QPageSize, Qt, QTimer, QUrl
)
from PyQt5.QtWebEngineWidgets import QWebEnginePage

from calibre.ebooks.metadata.pdf import page_images
from calibre.gui2 import must_use_qt
from calibre.gui2.webengine import secure_webengine
from calibre.utils.monotonic import monotonic

LOAD_TIMEOUT = 20
PRINT_TIMEOUT = 10


class Render(QWebEnginePage):

    def __init__(self):
        QWebEnginePage.__init__(self)
        secure_webengine(self)
        self.printing_started = False
        self.loadFinished.connect(self.load_finished, type=Qt.QueuedConnection)
        self.pdfPrintingFinished.connect(self.print_finished)
        self.hang_timer = t = QTimer(self)
        t.setInterval(500)
        t.timeout.connect(self.hang_check)

    def load_finished(self, ok):
        if ok:
            self.start_print()
        else:
            self.hang_timer.stop()
            QApplication.instance().exit(1)

    def start_load(self, path_to_html):
        self.load(QUrl.fromLocalFile(path_to_html))
        self.start_time = monotonic()
        self.hang_timer.start()

    def hang_check(self):
        if self.printing_started:
            if monotonic() - self.start_time > PRINT_TIMEOUT:
                self.hang_timer.stop()
                QApplication.instance().exit(4)
        else:
            if monotonic() - self.start_time > LOAD_TIMEOUT:
                self.hang_timer.stop()
                QApplication.instance().exit(3)

    def start_print(self):
        margins = QMarginsF(0, 0, 0, 0)
        page_layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, margins)
        self.printToPdf('rendered.pdf', page_layout)
        self.printing_started = True
        self.start_time = monotonic()

    def print_finished(self, path, ok):
        QApplication.instance().exit(0 if ok else 2)
        self.hang_timer.stop()


def main(path_to_html, tdir, image_format='jpeg'):
    if image_format not in ('jpeg', 'png'):
        raise ValueError('Image format must be either jpeg or png')
    must_use_qt()
    path_to_html = os.path.abspath(path_to_html)
    os.chdir(tdir)
    renderer = Render()
    renderer.start_load(path_to_html)
    ret = QApplication.instance().exec_()
    if ret == 0:
        page_images('rendered.pdf', image_format=image_format)
        ext = {'jpeg': 'jpg'}.get(image_format, image_format)
        os.rename('page-images-1.' + ext, 'rendered.' + image_format)
    return ret == 0


if __name__ == '__main__':
    if not main(sys.argv[-1], '.'):
        raise SystemExit('Failed to render HTML')
