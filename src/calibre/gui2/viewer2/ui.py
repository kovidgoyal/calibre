#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os

from PyQt5.Qt import pyqtSignal

from calibre.gui2.main_window import MainWindow


class EbookViewer(MainWindow):

    msg_from_anotherinstance = pyqtSignal(object)

    def __init__(self):
        MainWindow.__init__(self)

    def handle_commandline_arg(self, arg):
        if arg and os.path.isfile(arg) and os.access(arg, os.R_OK):
            self.load_ebook(arg)

    def another_instance_wants_to_talk(self, msg):
        try:
            path, open_at = msg
        except Exception:
            return
        self.load_ebook(path, open_at=open_at)
        self.raise_()
