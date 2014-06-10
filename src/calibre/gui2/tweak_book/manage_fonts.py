#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import (
    QSplitter, QVBoxLayout, QTableView, QWidget, QSize, QTableModel)

from calibre.gui2.tweak_book.widgets import Dialog

class AllFonts(QTableModel):

    def __init__(self, parent=None):
        QTableModel.__init__(self, parent)
        self.items = []
        self.font_data = {}

    def build(self):
        self.beginResetModel()

class ManageFonts(Dialog):

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Manage Fonts'), 'manage-fonts', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.bb.clear()
        self.bb.addButton(self.bb.Close)
        self.splitter = s = QSplitter(self)
        l.addWidget(s), l.addWidget(self.bb)

        self.fonts_view = fv = QTableView(self)
        self.container = c = QWidget()
        l = c.l = QVBoxLayout(c)
        c.setLayout(l)
        s.addWidget(fv), s.addWidget(l)

    def sizeHint(self):
        return QSize(900, 600)
