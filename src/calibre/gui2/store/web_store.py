#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import os
from base64 import standard_b64decode, standard_b64encode

from PyQt5.Qt import (
    QHBoxLayout, QProgressBar, QPushButton, QVBoxLayout, QWidget, pyqtSignal
)
from PyQt5.QtWebEngineWidgets import QWebEngineView

from calibre import url_slash_cleaner
from calibre.constants import STORE_DIALOG_APP_UID, islinux, iswindows
from calibre.gui2 import Application, set_app_uid
from calibre.gui2.main_window import MainWindow
from calibre.ptempfile import reset_base_dir


class View(QWebEngineView):
    pass


class Central(QWidget):

    home = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.view = v = View(self)
        v.loadStarted.connect(self.load_started)
        v.loadProgress.connect(self.load_progress)
        v.loadFinished.connect(self.load_finished)
        l.addWidget(v)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.home_button = b = QPushButton(_('Home'))
        b.clicked.connect(self.home)
        h.addWidget(b)
        self.back_button = b = QPushButton(_('Back'))
        b.clicked.connect(v.back)
        h.addWidget(b)
        self.forward_button = b = QPushButton(_('Forward'))
        b.clicked.connect(v.forward)
        h.addWidget(b)

        self.progress_bar = b = QProgressBar(self)
        h.addWidget(b)

    def load_started(self):
        self.progress_bar.setValue(0)

    def load_progress(self, amt):
        self.progress_bar.setValue(amt)

    def load_finished(self, ok):
        self.progress_bar.setValue(100)


class Main(MainWindow):

    def __init__(self, data):
        MainWindow.__init__(self, None)
        self.data = data
        self.central = c = Central(self)
        c.home.connect(self.go_home)
        self.setCentralWidget(c)

    @property
    def view(self):
        return self.central.view

    def go_home(self):
        self.go_to()

    def go_to(self, url=None):
        url = url or self.data['base_url']
        url = url_slash_cleaner(url)
        self.view.load(url)


def main(args):
    # Ensure we can continue to function if GUI is closed
    os.environ.pop('CALIBRE_WORKER_TEMP_DIR', None)
    reset_base_dir()
    if iswindows:
        # Ensure that all instances are grouped together in the task bar. This
        # prevents them from being grouped with viewer/editor process when
        # launched from within calibre, as both use calibre-parallel.exe
        set_app_uid(STORE_DIALOG_APP_UID)

    data = args[-1]
    data = json.loads(standard_b64decode(data))
    override = 'calibre-ebook-viewer' if islinux else None
    app = Application(args, override_program_name=override)
    app.exec_()


if __name__ == '__main__':
    sample_data = standard_b64encode(
        json.dumps({
            u'window_title': u'MobileRead',
            u'base_url': u'https://www.mobileread.com/',
            u'detail_url': u'http://www.mobileread.com/forums/showthread.php?t=54477',
            u'tags': u''
        })
    )
    main([sample_data])
