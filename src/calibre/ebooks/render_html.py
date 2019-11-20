#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import os
import sys

from PyQt5.Qt import (
    QApplication, QMarginsF, QPageLayout, QPageSize, Qt, QTimer, QUrl
)
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineScript

from calibre.ebooks.metadata.pdf import page_images
from calibre.gui2 import must_use_qt
from calibre.gui2.webengine import secure_webengine
from calibre.utils.filenames import atomic_rename
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
            self.runJavaScript('''
            var ans = {};
            var meta = document.querySelector('meta[name=calibre-html-render-data]');
            if (meta) {
                try {
                    ans = JSON.parse(meta.content);
                    console.log(ans);
                } catch {}
            }
            ans;
            ''', QWebEngineScript.ApplicationWorld, self.start_print)
        else:
            self.hang_timer.stop()
            QApplication.instance().exit(1)

    def javaScriptConsoleMessage(self, level, msg, linenumber, source_id):
        pass

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

    def start_print(self, data):
        margins = QMarginsF(0, 0, 0, 0)
        page_size = QPageSize(QPageSize.A4)
        if isinstance(data, dict):
            try:
                if 'margins' in data:
                    margins = QMarginsF(*data['margins'])
                if 'size' in data:
                    sz = data['size']
                    if type(getattr(QPageSize, sz, None)) is type(QPageSize.A4):  # noqa
                        page_size = QPageSize(getattr(QPageSize, sz))
                    else:
                        from calibre.ebooks.pdf.image_writer import parse_pdf_page_size
                        ps = parse_pdf_page_size(sz, data.get('unit', 'inch'))
                        if ps is not None:
                            page_size = ps
            except Exception:
                pass
        page_layout = QPageLayout(page_size, QPageLayout.Portrait, margins)
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
        atomic_rename('page-images-1.' + ext, 'rendered.' + image_format)
    return ret == 0


if __name__ == '__main__':
    if not main(sys.argv[-1], '.'):
        raise SystemExit('Failed to render HTML')
