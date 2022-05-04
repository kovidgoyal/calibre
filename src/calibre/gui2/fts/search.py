#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import os
import traceback
from qt.core import (
    QAbstractItemModel, QDialog, QDialogButtonBox, QModelIndex, Qt, QTreeView,
    QVBoxLayout
)

from calibre.gui2.fts.utils import get_db
from calibre.gui2.viewer.widgets import ResultsDelegate

ROOT = QModelIndex()


class SearchDelegate(ResultsDelegate):

    def result_data(self, result):
        if not isinstance(result, dict):
            return None, None, None, None, None
        full_text = result['text']
        parts = full_text.split('\x1d', 2)
        before = after = ''
        if len(parts) > 2:
            before, text = parts[:2]
            after = parts[2].replace('\x1d', '')
        elif len(parts) == 2:
            before, text = parts
        else:
            text = parts[0]
        return False, before, text, after, False


class Results:

    _title = None

    def __init__(self, book_id):
        self.book_id = book_id
        self.search_results = []
        self.append = self.search_results.append

    def __len__(self):
        return len(self.search_results)

    def __getitem__(self, x):
        return self.search_results[x]

    @property
    def title(self):
        if self._title is None:
            try:
                self._title = get_db().field_for('title', self.book_id)
            except Exception:
                self._title = _('Unknown book')
        return self._title


class ResultsModel(QAbstractItemModel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results = []

    def search(self, fts_engine_query, use_stemming=True, restrict_to_book_ids=None):
        db = get_db()

        def construct(all_matches):
            r = {}
            sr = self.results = []

            for x in all_matches:
                book_id = x['book_id']
                results = r.get(book_id)
                if results is None:
                    results = Results(book_id)
                    r[book_id] = results
                    sr.append(results)
                results.append(x)

        self.beginResetModel()
        db.fts_search(
            fts_engine_query, use_stemming=use_stemming, highlight_start='\x1d', highlight_end='\x1d', snippet_size=64,
            restrict_to_book_ids=restrict_to_book_ids, result_type=construct
        )
        self.endResetModel()

    def index_to_entry(self, idx):
        q = idx.internalId()
        if q:
            # search result
            list_idx = q - 1
            try:
                q = self.results[list_idx]
                return q[idx.row()]
            except Exception:
                traceback.print_exc()
                return None
        else:
            ans = idx.row()
            if -1 < ans < len(self.results):
                return self.results[ans]

    def index(self, row, column, parent=ROOT):
        if parent.isValid():
            return self.createIndex(row, column, parent.row() + 1)
        return self.createIndex(row, column, 0)

    def parent(self, index):
        q = index.internalId()
        if q:
            return self.index(q - 1, 0)
        return ROOT

    def rowCount(self, parent=ROOT):
        if parent.isValid():
            x = self.index_to_entry(parent)
            if isinstance(x, Results):
                return len(x)
            return 0
        return len(self.results)

    def columnCount(self, parent=ROOT):
        return 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        item = self.index_to_entry(index)
        if item is None:
            return
        if isinstance(item, Results):
            return self.data_for_book(item, role)
        return self.data_for_match(item, role)

    def data_for_book(self, item, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return item.title
        if role == Qt.ItemDataRole.UserRole:
            return item

    def data_for_match(self, item, role):
        if role == Qt.ItemDataRole.UserRole:
            return item


class ResultsView(QTreeView):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.m = ResultsModel(self)
        self.setModel(self.m)
        self.delegate = SearchDelegate(self)
        self.setItemDelegate(self.delegate)


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    app = Application([])
    d = QDialog()
    l = QVBoxLayout(d)
    bb = QDialogButtonBox(d)
    bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)
    get_db.db = db(os.path.expanduser('~/test library'))
    w = ResultsView(parent=d)
    l.addWidget(w)
    l.addWidget(bb)
    w.model().search('asimov')
    d.exec()
