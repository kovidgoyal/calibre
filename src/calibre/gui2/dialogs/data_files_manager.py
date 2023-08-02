#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import os
from contextlib import contextmanager
from datetime import datetime
from qt.core import (
    QAbstractItemView, QAbstractListModel, QDialogButtonBox, QIcon, QItemSelectionModel,
    QLabel, QListView, QPushButton, Qt, QVBoxLayout, QSize
)

from calibre import human_readable
from calibre.db.constants import DATA_DIR_NAME, DATA_FILE_PATTERN
from calibre.gui2 import choose_files, error_dialog, file_icon_provider, question_dialog
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import primary_sort_key


class Files(QAbstractListModel):

    def __init__(self, db, book_id, parent=None):
        self.db = db
        self.book_id = book_id
        super().__init__(parent=parent)
        self.fi = file_icon_provider()
        self.files = sorted(db.list_extra_files(self.book_id, pattern=DATA_FILE_PATTERN), key=self.file_sort_key)

    def refresh(self):
        self.modelAboutToBeReset.emit()
        self.files = sorted(self.db.list_extra_files(self.book_id, pattern=DATA_FILE_PATTERN), key=self.file_sort_key)
        self.modelReset.emit()

    def file_sort_key(self, ef):
        return primary_sort_key(ef.relpath)

    def rowCount(self, parent=None):
        return len(self.files)

    def file_display_name(self, rownum):
        ef = self.files[rownum]
        name = ef.relpath.split('/', 1)[1]
        return name.replace('/', os.sep)

    def item_at(self, rownum):
        return self.files[rownum]

    def data(self, index, role):
        row = index.row()
        if row >= len(self.files):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            name =  self.file_display_name(row)
            e = self.item_at(row)
            date = datetime.fromtimestamp(e.stat_result.st_mtime)
            l2 = human_readable(e.stat_result.st_size) + date.strftime(' [%Y/%m/%d]')
            return name + '\n' + l2
        if role == Qt.ItemDataRole.DecorationRole:
            ef = self.files[row]
            fmt = ef.relpath.rpartition('.')[-1].lower()
            return self.fi.icon_from_ext(fmt)
        return None

    def flags(self, index):
        return Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEnabled


class DataFilesManager(Dialog):

    def __init__(self, db, book_id, parent=None):
        self.db = db.new_api
        self.book_title = title = self.db.field_for('title', book_id) or _('Unknown')
        self.book_id = book_id
        super().__init__(_('Manage data files for {}').format(title), 'manage-data-files-xx',
                         parent=parent, default_buttons=QDialogButtonBox.StandardButton.Close)

    def sizeHint(self):
        return QSize(400, 500)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)

        self.fview = v = QListView(self)
        l.addWidget(v)
        self.files = Files(self.db.new_api, self.book_id, parent=v)
        v.setModel(self.files)
        v.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        if self.files.rowCount():
            v.setCurrentIndex(self.files.index(0))
        v.selectionModel().currentChanged.connect(self.current_changed)

        self.current_label = la = QLabel(self)
        la.setWordWrap(True)
        l.addWidget(la)

        l.addWidget(self.bb)
        self.add_button = b = QPushButton(QIcon.ic('plus.png'), _('&Add files'), self)
        b.clicked.connect(self.add_files)
        self.bb.addButton(b, QDialogButtonBox.ButtonRole.ActionRole)

        self.current_changed()
        self.resize(self.sizeHint())

    def current_changed(self):
        idx = self.fview.currentIndex()
        txt = ''
        if idx.isValid():
            txt = self.files.file_display_name(idx.row())
        self.current_label.setText(txt)

    @property
    def current_item(self):
        ci = self.fview.currentIndex()
        try:
            return self.files.item_at(ci.row())
        except Exception:
            return None

    @contextmanager
    def preserve_state(self):
        selected = set()
        vs = self.fview.verticalScrollBar()
        pos = vs.value()
        for idx in self.fview.selectionModel().selectedRows():
            e = self.files.item_at(idx.row())
            selected.add(e.relpath)
        current = self.current_item
        try:
            yield
        finally:
            sm = self.fview.selectionModel()
            for i in range(self.files.rowCount()):
                e = self.files.item_at(i)
                flags = QItemSelectionModel.SelectionFlag.NoUpdate
                if current is not None and e.relpath == current.relpath:
                    flags |= QItemSelectionModel.SelectionFlag.Current
                if e.relpath in selected:
                    flags |= QItemSelectionModel.SelectionFlag.Select
                if flags != QItemSelectionModel.SelectionFlag.NoUpdate:
                    sm.select(self.files.index(i), flags)
            self.current_changed()
            vs.setValue(pos)

    def add_files(self):
        files = choose_files(self, 'choose-data-files-to-add', _('Choose files to add'))
        if not files:
            return
        q = self.db.are_paths_inside_book_dir(self.book_id, files, DATA_DIR_NAME)
        if q:
            return error_dialog(
                self, _('Cannot add'), _(
                    'Cannot add these data files to the book because they are already in the book\'s data files folder'
                ), show=True, det_msg='\n'.join(q))

        m = {f'{DATA_DIR_NAME}/{os.path.basename(x)}': x for x in files}
        added = self.db.add_extra_files(self.book_id, m, replace=False, auto_rename=False)
        collisions = set(m) - set(added)
        if collisions:
            if question_dialog(self, _('Replace existing files?'), _(
                    'The following files already exist as data files in the book. Replace them?'
            ) + '\n' + '\n'.join(x.partition('/')[2] for x in collisions)):
                self.db.add_extra_files(self.book_id, m, replace=True, auto_rename=False)
        with self.preserve_state():
            self.files.refresh()


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db as di
    app = Application([])
    dfm = DataFilesManager(di(os.path.expanduser('~/test library')), 1893)
    dfm.exec()
