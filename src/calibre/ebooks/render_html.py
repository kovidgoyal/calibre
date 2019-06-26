#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys

from PyQt5.Qt import QApplication, QMarginsF, QPageLayout, QPageSize, Qt, QUrl
from PyQt5.QtWebEngineWidgets import QWebEnginePage

from calibre.ebooks.metadata.pdf import page_images
from calibre.gui2 import must_use_qt
from calibre.gui2.webengine import secure_webengine


class Render(QWebEnginePage):

    def __init__(self):
        QWebEnginePage.__init__(self)
        secure_webengine(self)
        self.loadFinished.connect(self.load_finished, type=Qt.QueuedConnection)
        self.pdfPrintingFinished.connect(self.print_finished)

    def load_finished(self, ok):
        if ok:
            self.start_print()
        else:
            QApplication.instance().exit(1)

    def start_print(self):
        margins = QMarginsF(0, 0, 0, 0)
        page_layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, margins)
        self.printToPdf('rendered.pdf', page_layout)

    def print_finished(self, path, ok):
        QApplication.instance().exit(0 if ok else 2)


def main(path_to_html, tdir, image_format='jpeg'):
    if image_format not in ('jpeg', 'png'):
        raise ValueError('Image format must be either jpeg or png')
    must_use_qt()
    path_to_html = os.path.abspath(path_to_html)
    os.chdir(tdir)
    renderer = Render()
    renderer.load(QUrl.fromLocalFile(path_to_html))
    ret = QApplication.instance().exec_()
    if ret == 0:
        page_images('rendered.pdf', image_format=image_format)
        ext = {'jpeg': 'jpg'}.get(image_format, image_format)
        os.rename('page-images-1.' + ext, 'rendered.' + image_format)
    return ret == 0


if __name__ == '__main__':
    main(sys.argv[-1], '.')
