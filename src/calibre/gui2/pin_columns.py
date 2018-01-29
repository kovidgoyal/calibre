#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from PyQt5.Qt import QWidget, QHBoxLayout, QTableView


class PinTableView(QTableView):

    def __init__(self, books_view, parent=None):
        QTableView.__init__(self, parent)
        self.books_view = books_view
        self.verticalHeader().close()


class PinContainer(QWidget):

    def __init__(self, books_view, parent=None):
        QWidget.__init__(self, parent)
        self.books_view = books_view
        self.l = l = QHBoxLayout(self)
        l.addWidget(books_view)
        l.addWidget(books_view.pin_view)
        l.setContentsMargins(0, 0, 0, 0)
