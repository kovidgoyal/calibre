#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json

from PyQt5.Qt import (
    QAction, QGridLayout, QIcon, QItemSelectionModel, QLabel, QListWidget,
    QListWidgetItem, QPushButton, Qt, QWidget, pyqtSignal
)

from calibre.gui2 import choose_files, choose_save_file
from calibre.gui2.viewer.annotations import serialize_annotation
from calibre.srv.render_book import parse_annotation
from calibre.utils.date import EPOCH
from calibre.utils.icu import sort_key
from polyglot.builtins import range, unicode_type


class BookmarksList(QListWidget):

    changed = pyqtSignal()
    bookmark_activated = pyqtSignal(object)

    def __init__(self, parent=None):
        QListWidget.__init__(self, parent)
        self.setDragEnabled(True)
        self.setDragDropMode(self.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAlternatingRowColors(True)
        self.setStyleSheet('QListView::item { padding: 0.5ex }')
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.ac_edit = ac = QAction(QIcon(I('edit_input.png')), _('Edit this bookmark'), self)
        self.addAction(ac)
        self.ac_delete = ac = QAction(QIcon(I('trash.png')), _('Remove this bookmark'), self)
        self.addAction(ac)
        self.ac_sort = ac = QAction(_('Sort by name'), self)
        self.addAction(ac)
        self.ac_sort_pos = ac = QAction(_('Sort by position in book'), self)
        self.addAction(ac)

    def dropEvent(self, ev):
        QListWidget.dropEvent(self, ev)
        if ev.isAccepted():
            self.changed.emit()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Enter, Qt.Key_Return):
            i = self.currentItem()
            if i is not None:
                self.bookmark_activated.emit(i)
                ev.accept()
                return
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            i = self.currentItem()
            if i is not None:
                self.ac_delete.trigger()
                ev.accept()
                return
        return QListWidget.keyPressEvent(self, ev)


class BookmarkManager(QWidget):

    edited = pyqtSignal(object)
    activated = pyqtSignal(object)
    create_requested = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = l = QGridLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.setLayout(l)

        self.bookmarks_list = bl = BookmarksList(self)
        bl.itemChanged.connect(self.item_changed)
        l.addWidget(bl, 0, 0, 1, -1)
        bl.itemClicked.connect(self.item_activated)
        bl.bookmark_activated.connect(self.item_activated)
        bl.changed.connect(lambda : self.edited.emit(self.get_bookmarks()))
        bl.ac_edit.triggered.connect(self.edit_bookmark)
        bl.ac_sort.triggered.connect(self.sort_by_name)
        bl.ac_sort_pos.triggered.connect(self.sort_by_pos)
        bl.ac_delete.triggered.connect(self.delete_bookmark)

        self.la = la = QLabel(_(
            'Double click to edit and drag-and-drop to re-order the bookmarks'))
        la.setWordWrap(True)
        l.addWidget(la, l.rowCount(), 0, 1, -1)

        self.button_new = b = QPushButton(QIcon(I('bookmarks.png')), _('&New'), self)
        b.clicked.connect(self.create_requested)
        b.setToolTip(_('Create a new bookmark at the current location'))
        l.addWidget(b)

        self.button_delete = b = QPushButton(QIcon(I('trash.png')), _('&Remove'), self)
        b.setToolTip(_('Remove the currently selected bookmark'))
        b.clicked.connect(self.delete_bookmark)
        l.addWidget(b, l.rowCount() - 1, 1)

        self.button_delete = b = QPushButton(_('Sort by &name'), self)
        b.setToolTip(_('Sort bookmarks by name'))
        b.clicked.connect(self.sort_by_name)
        l.addWidget(b)

        self.button_delete = b = QPushButton(_('Sort by &position'), self)
        b.setToolTip(_('Sort bookmarks by position in book'))
        b.clicked.connect(self.sort_by_pos)
        l.addWidget(b, l.rowCount() - 1, 1)

        self.button_export = b = QPushButton(QIcon(I('back.png')), _('E&xport'), self)
        b.clicked.connect(self.export_bookmarks)
        l.addWidget(b)

        self.button_import = b = QPushButton(QIcon(I('forward.png')), _('&Import'), self)
        b.clicked.connect(self.import_bookmarks)
        l.addWidget(b, l.rowCount() - 1, 1)

    def item_activated(self, item):
        bm = self.item_to_bm(item)
        self.activated.emit(bm)

    def set_bookmarks(self, bookmarks=()):
        self.bookmarks_list.clear()
        for bm in bookmarks:
            i = QListWidgetItem(bm['title'])
            i.setData(Qt.UserRole, self.bm_to_item(bm))
            i.setFlags(i.flags() | Qt.ItemIsEditable)
            self.bookmarks_list.addItem(i)
        if self.bookmarks_list.count() > 0:
            self.bookmarks_list.setCurrentItem(self.bookmarks_list.item(0), QItemSelectionModel.ClearAndSelect)

    def set_current_bookmark(self, bm):
        for i, q in enumerate(self):
            if bm == q:
                l = self.bookmarks_list
                item = l.item(i)
                l.setCurrentItem(item, QItemSelectionModel.ClearAndSelect)
                l.scrollToItem(item)

    def __iter__(self):
        for i in range(self.bookmarks_list.count()):
            yield self.item_to_bm(self.bookmarks_list.item(i))

    def item_changed(self, item):
        self.bookmarks_list.blockSignals(True)
        title = unicode_type(item.data(Qt.DisplayRole))
        if not title:
            title = _('Unknown')
            item.setData(Qt.DisplayRole, title)
        bm = self.item_to_bm(item)
        bm['title'] = title
        item.setData(Qt.UserRole, self.bm_to_item(bm))
        self.bookmarks_list.blockSignals(False)
        self.edited.emit(self.get_bookmarks())

    def delete_bookmark(self):
        row = self.bookmarks_list.currentRow()
        if row > -1:
            self.bookmarks_list.takeItem(row)
            self.edited.emit(self.get_bookmarks())

    def edit_bookmark(self):
        item = self.bookmarks_list.currentItem()
        if item is not None:
            self.bookmarks_list.editItem(item)

    def sort_by_name(self):
        bm = self.get_bookmarks()
        bm.sort(key=lambda x:sort_key(x['title']))
        self.set_bookmarks(bm)
        self.edited.emit(bm)

    def sort_by_pos(self):
        from calibre.ebooks.epub.cfi.parse import cfi_sort_key

        def pos_key(b):
            if b.get('pos_type') == 'epubcfi':
                return cfi_sort_key(b['pos'], only_path=False)
            return cfi_sort_key('/99999999')
        bm = self.get_bookmarks()
        bm.sort(key=pos_key)
        self.set_bookmarks(bm)
        self.edited.emit(bm)

    def bm_to_item(self, bm):
        return bm.copy()

    def item_to_bm(self, item):
        return item.data(Qt.UserRole).copy()

    def get_bookmarks(self):
        return list(self)

    def export_bookmarks(self):
        filename = choose_save_file(
            self, 'export-viewer-bookmarks', _('Export bookmarks'),
            filters=[(_('Saved bookmarks'), ['calibre-bookmarks'])], all_files=False, initial_filename='bookmarks.calibre-bookmarks')
        if filename:
            entries = [serialize_annotation(a) for a in self.get_bookmarks()]
            data = json.dumps({'type': 'bookmarks', 'entries': entries}, indent=True)
            if not isinstance(data, bytes):
                data = data.encode('utf-8')
            with lopen(filename, 'wb') as fileobj:
                fileobj.write(data)

    def import_bookmarks(self):
        files = choose_files(self, 'export-viewer-bookmarks', _('Import bookmarks'),
            filters=[(_('Saved bookmarks'), ['calibre-bookmarks'])], all_files=False, select_only_single_file=True)
        if not files:
            return
        filename = files[0]

        imported = None
        with lopen(filename, 'rb') as fileobj:
            imported = json.load(fileobj)

        def import_old_bookmarks(imported):
            try:
                for bm in imported:
                    if 'title' not in bm:
                        return
            except Exception:
                return

            bookmarks = self.get_bookmarks()
            for bm in imported:
                if bm['title'] == 'calibre_current_page_bookmark':
                    continue
                epubcfi = 'epubcfi(/{}/{})'.format(bm['spine'], bm['pos'].lstrip('/'))
                q = {'pos_type': 'epubcfi', 'pos': epubcfi, 'timestamp': EPOCH, 'title': bm['title']}
                if q not in bookmarks:
                    bookmarks.append(q)
            self.set_bookmarks(bookmarks)
            self.edited.emit(self.get_bookmarks())

        def import_current_bookmarks(imported):
            if imported.get('type') != 'bookmarks':
                return
            bookmarks = self.get_bookmarks()
            for bm in imported['entries']:
                q = parse_annotation(bm)
                if q not in bookmarks:
                    bookmarks.append(q)
            self.set_bookmarks(bookmarks)
            self.edited.emit(self.get_bookmarks())

        if imported is not None:
            if isinstance(imported, list):
                import_old_bookmarks(imported)
            else:
                import_current_bookmarks(imported)
