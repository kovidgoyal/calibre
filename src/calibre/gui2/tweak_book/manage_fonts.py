#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys

from PyQt4.Qt import (
    QSplitter, QVBoxLayout, QTableView, QWidget, QLabel, QAbstractTableModel,
    Qt, QApplication, QTimer, QPushButton)

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.fonts import font_family_data
from calibre.gui2.tweak_book import current_container, set_current_container
from calibre.gui2.tweak_book.widgets import Dialog, BusyCursor
from calibre.utils.icu import primary_sort_key as sort_key

class AllFonts(QAbstractTableModel):

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.items = []
        self.font_data = {}
        self.sorted_on = ('name', True)

    def rowCount(self, parent=None):
        return len(self.items)

    def columnCount(self, parent=None):
        return 2

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _('Font family') if section == 1 else _('Embedded')
        return QAbstractTableModel.headerData(self, section, orientation, role)

    def build(self):
        with BusyCursor():
            self.beginResetModel()
            self.font_data = font_family_data(current_container())
            self.do_sort()
            self.endResetModel()

    def do_sort(self):
        reverse = not self.sorted_on[1]
        self.items = sorted(self.font_data.iterkeys(), key=sort_key, reverse=reverse)
        if self.sorted_on[0] != 'name':
            self.items.sort(key=self.font_data.get, reverse=reverse)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            row, col = index.row(), index.column()
            try:
                name = self.items[row]
                embedded = '✓ ' if self.font_data[name] else ''
            except (IndexError, KeyError):
                return
            return name if col == 1 else embedded

    def sort(self, col, order=Qt.AscendingOrder):
        sorted_on = (('name' if col == 1 else 'embedded'), order == Qt.AscendingOrder)
        if sorted_on != self.sorted_on:
            self.sorted_on = sorted_on
            self.beginResetModel()
            self.do_sort()
            self.endResetModel()

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
        self.model = m = AllFonts(fv)
        fv.horizontalHeader().setStretchLastSection(True)
        fv.setModel(m)
        fv.setSortingEnabled(True)
        fv.setShowGrid(False)
        fv.setAlternatingRowColors(True)
        fv.setSelectionMode(fv.ExtendedSelection)
        fv.setSelectionBehavior(fv.SelectRows)
        fv.horizontalHeader().setSortIndicator(1, Qt.AscendingOrder)
        self.container = c = QWidget()
        l = c.l = QVBoxLayout(c)
        c.setLayout(l)
        s.addWidget(fv), s.addWidget(c)

        self.cb = b = QPushButton(_('&Change selected fonts'))
        b.clicked.connect(self.change_fonts)
        l.addWidget(b)
        self.rb = b = QPushButton(_('&Remove selected fonts'))
        b.clicked.connect(self.remove_fonts)
        l.addWidget(b)
        self.eb = b = QPushButton(_('&Embed all fonts'))
        b.clicked.connect(self.embed_fonts)
        l.addWidget(b)

        self.la = la = QLabel('<p>' + _(
        ''' All the fonts declared in this book are shown to the left, along with whether they are embedded or not.
            You can remove or replace any selected font and also embed any declared fonts that are not already embedded.'''))
        la.setWordWrap(True)
        l.addWidget(la)

        l.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        QTimer.singleShot(0, m.build)

    def change_fonts(self):
        pass

    def remove_fonts(self):
        pass

    def embed_fonts(self):
        pass

if __name__ == '__main__':
    app = QApplication([])
    c = get_container(sys.argv[-1], tweak_mode=True)
    set_current_container(c)
    d = ManageFonts()
    d.exec_()
    del app
