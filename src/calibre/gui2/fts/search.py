#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import os
import traceback
from contextlib import suppress
from itertools import count
from qt.core import (
    QAbstractItemModel, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QIcon,
    QModelIndex, QPushButton, QSize, Qt, QTreeView, QVBoxLayout, QWidget, pyqtSignal
)
from threading import Event, Thread

from calibre.gui2 import gprefs
from calibre.gui2.fts.utils import get_db
from calibre.gui2.library.annotations import BusyCursor
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.viewer.widgets import ResultsDelegate, SearchBox

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

    result_found = pyqtSignal(int, object)
    all_results_found = pyqtSignal(int)
    search_started = pyqtSignal()
    search_complete = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results = []
        self.query_id_counter = count()
        self.current_query_id = -1
        self.current_thread_abort = Event()
        self.current_thread = None
        self.current_search_key = None
        self.result_found.connect(self.result_with_text_found, type=Qt.ConnectionType.QueuedConnection)
        self.all_results_found.connect(self.signal_search_complete, type=Qt.ConnectionType.QueuedConnection)

    def search(self, fts_engine_query, use_stemming=True, restrict_to_book_ids=None):
        db = get_db()

        def construct(all_matches):
            self.result_map = r = {}
            sr = self.results = []

            for x in all_matches:
                book_id = x['book_id']
                results = r.get(book_id)
                if results is None:
                    results = Results(book_id)
                    r[book_id] = len(sr)
                    sr.append(results)

        sk = fts_engine_query, use_stemming, restrict_to_book_ids, id(db)
        if sk == self.current_search_key:
            return False
        self.current_thread_abort.set()
        self.current_search_key = sk
        self.search_started.emit()
        self.beginResetModel()
        db.fts_search(
            fts_engine_query, use_stemming=use_stemming, highlight_start='\x1d', highlight_end='\x1d', snippet_size=64,
            restrict_to_book_ids=restrict_to_book_ids, result_type=construct, return_text=False
        )
        self.endResetModel()
        self.current_query_id = next(self.query_id_counter)
        self.current_thread_abort = Event()
        self.current_thread = Thread(
            name='FTSQuery', daemon=True, target=self.search_text_in_thread, args=(
                self.current_query_id, self.current_thread_abort, fts_engine_query,), kwargs=dict(
                use_stemming=use_stemming, highlight_start='\x1d', highlight_end='\x1d', snippet_size=64,
                restrict_to_book_ids=restrict_to_book_ids, return_text=True)
        )
        self.current_thread.start()
        return True

    def search_text_in_thread(self, query_id, abort, *a, **kw):
        db = get_db()
        generator = db.fts_search(*a, **kw, result_type=lambda x: x)
        for result in generator:
            if abort.is_set():
                with suppress(StopIteration):
                    generator.send(True)
                return
            self.result_found.emit(query_id, result)
        self.all_results_found.emit(query_id)

    def result_with_text_found(self, query_id, result):
        if query_id != self.current_query_id:
            return
        bid = result['book_id']
        i = self.result_map.get(bid)
        if i is not None:
            parent = self.results[i]
            parent_idx = self.index(i, 0)
            r = len(parent)
            self.beginInsertRows(parent_idx, r, r)
            parent.append(result)
            self.endInsertRows()

    def signal_search_complete(self, query_id):
        if query_id == self.current_query_id:
            self.current_query_id = -1
            self.current_thread = None
            self.search_complete.emit()

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

    search_started = pyqtSignal()
    search_complete = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.m = ResultsModel(self)
        self.m.search_complete.connect(self.search_complete)
        self.m.search_started.connect(self.search_started)
        self.setModel(self.m)
        self.delegate = SearchDelegate(self)
        self.setItemDelegate(self.delegate)

    def search(self, *a, **kw):
        with BusyCursor():
            self.m.search(*a, **kw)
            self.expandAll()


class Spinner(ProgressIndicator):

    def sizeHint(self):
        return QSize(8, 8)

    def paintEvent(self, ev):
        if self.isAnimated():
            super().paintEvent(ev)


class SearchInputPanel(QWidget):

    search_signal = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        QHBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.v1 = v1 = QVBoxLayout()
        v1.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.layout().addLayout(v1)
        self.search_box = sb = SearchBox(self)
        sb.initialize('library-fts-search-box')
        sb.lineEdit().returnPressed.connect(self.search_requested)
        sb.lineEdit().setPlaceholderText(_('Enter words to search for'))
        v1.addWidget(sb)
        self.h1 = h1 = QHBoxLayout()
        v1.addLayout(h1)
        self.restrict = r = QCheckBox(_('&Restrict searched books'))
        r.setToolTip('<p>' + _(
            'Restrict search results to only the books currently showing in the main'
            ' library screen. This means that any Virtual libraries or search results'
            ' are applied.'))
        r.setChecked(gprefs['fts_library_restrict_books'])
        r.stateChanged.connect(lambda state: gprefs.set('fts_library_restrict_books', state != Qt.CheckState.Unchecked))
        self.related = rw = QCheckBox(_('&Match on related words'))
        rw.setToolTip('<p>' + _(
            'With this option searching for words will also match on any related words (supported in several languages). For'
            ' example, in the English language: <i>correction</i> matches <i>correcting</i> and <i>corrected</i> as well'))
        rw.setChecked(gprefs['fts_library_use_stemmer'])
        rw.stateChanged.connect(lambda state: gprefs.set('fts_library_use_stemmer', state != Qt.CheckState.Unchecked))
        h1.addWidget(r), h1.addWidget(rw), h1.addStretch()

        self.search_button = sb = QPushButton(QIcon.ic('search.png'), _('&Search'), self)
        sb.clicked.connect(self.search_requested)
        self.v2 = v2 = QVBoxLayout()
        v2.addWidget(sb)
        self.pi = pi = Spinner(self)
        v2.addWidget(pi)

        self.layout().addLayout(v2)

    def start(self):
        self.pi.start()

    def stop(self):
        self.pi.stop()

    def search_requested(self):
        text = self.search_box.text().strip()
        self.search_signal.emit(text)


class ResultsPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.sip = sip = SearchInputPanel(parent=self)
        l.addWidget(sip)
        self.results_view = rv = ResultsView(parent=self)
        l.addWidget(rv)
        self.search = rv.search
        rv.search_started.connect(self.sip.start)
        rv.search_complete.connect(self.sip.stop)
        sip.search_signal.connect(self.search)


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    app = Application([])
    d = QDialog()
    d.sizeHint = lambda : QSize(1000, 680)
    l = QVBoxLayout(d)
    bb = QDialogButtonBox(d)
    bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)
    get_db.db = db(os.path.expanduser('~/test library'))
    w = ResultsPanel(parent=d)
    l.addWidget(w)
    l.addWidget(bb)
    w.sip.search_box.setText('asimov')
    d.exec()
