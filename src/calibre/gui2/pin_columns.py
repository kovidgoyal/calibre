#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from PyQt5.Qt import QSplitter, QTableView


class PinTableView(QTableView):

    def __init__(self, books_view, parent=None):
        QTableView.__init__(self, parent)
        self.books_view = books_view
        self.verticalHeader().close()


class PinContainer(QSplitter):

    def __init__(self, books_view, parent=None):
        QSplitter.__init__(self, parent)
        self.setChildrenCollapsible(False)
        self.books_view = books_view
        self.addWidget(books_view)
        self.addWidget(books_view.pin_view)
