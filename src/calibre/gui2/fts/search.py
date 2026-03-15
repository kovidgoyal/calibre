#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import os
import re
import time
import traceback
from contextlib import suppress
from functools import partial
from itertools import count
from threading import Event, Thread

from qt.core import (
    QAbstractItemModel,
    QAbstractItemView,
    QAction,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFont,
    QHBoxLayout,
    QIcon,
    QImage,
    QKeySequence,
    QLabel,
    QMenu,
    QModelIndex,
    QPalette,
    QPixmap,
    QPushButton,
    QRect,
    QSize,
    QSplitter,
    QStackedLayout,
    QStackedWidget,
    Qt,
    QTimer,
    QToolButton,
    QTreeView,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre import fit_image, prepare_string_for_xml
from calibre.db import FTSQueryError
from calibre.ebooks.metadata import authors_to_string, fmt_sidx
from calibre.gui2 import config, error_dialog, gprefs, info_dialog, question_dialog
from calibre.gui2.fts.cards import CardsView
from calibre.gui2.fts.utils import fts_url, get_db, help_panel, jump_shortcut, markup_text
from calibre.gui2.library.models import render_pin
from calibre.gui2.ui import get_gui
from calibre.gui2.viewer.widgets import ResultsDelegate, SearchBox
from calibre.gui2.widgets import BusyCursor
from calibre.gui2.widgets2 import HTMLDisplay
from calibre.utils.localization import ngettext

ROOT = QModelIndex()
sanitize_text_pat = re.compile(r'\s+')


def mark_books(*book_ids):
    gui = get_gui()
    if gui is not None:
        gui.iactions['Mark Books'].add_ids(book_ids)


def reindex_book(book_id, parent):
    get_db().reindex_fts_book(book_id)
    info_dialog(parent, _('Scheduled for re-indexing'), _(
        'This book has been scheduled for re-indexing, which typically takes a few seconds, if'
        ' no other books are being re-indexed. Once indexing is complete, you can re-run the search'
        ' to see updated results.'), show=True)


def jump_to_book(book_id, parent=None):
    gui = get_gui()
    if gui is not None:
        parent = parent or gui
        if gui.library_view.select_rows((book_id,)):
            gui.raise_and_focus()
        elif gprefs['fts_library_restrict_books']:
            error_dialog(parent, _('Not found'), _('This book was not found in the calibre library'), show=True)
        else:
            error_dialog(parent, _('Not found'), _(
                'This book is not currently visible in the calibre library.'
                ' If you have a search or Virtual library active, try clearing that.'
                ' Or click the "Restrict searched books" checkbox in this window to'
                ' only search currently visible books.'), show=True)


def show_in_viewer(book_id, text, fmt):
    text = text.strip('…').replace('\x1d', '').replace('\xa0', ' ')
    text = sanitize_text_pat.sub(' ', text)
    gui = get_gui()
    if gui is not None:
        if fmt in config['internally_viewed_formats']:
            gui.iactions['View'].view_format_by_id(book_id, fmt, open_at=f'search:{text}')
        else:
            gui.iactions['View'].view_format_by_id(book_id, fmt)


def open_book(results, match_index=None):
    gui = get_gui()
    if gui is None:
        return
    book_id = results.book_id
    if match_index is None:
        gui.iactions['View'].view_historical(book_id)
        return
    result_dict = results.result_dicts[match_index]
    formats = results.formats[match_index]
    from calibre.gui2.actions.view import preferred_format
    show_in_viewer(book_id, result_dict['text'], preferred_format(formats))


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

    _title = _authors = _series = _series_index = _book_in_db = None

    def __init__(self, book_id):
        self.book_id = book_id
        self.text_map = {}
        self.result_dicts = []
        self.formats = []

    def add_result_with_text(self, result):
        text = result['text']
        q = sanitize_text_pat.sub('', text)
        fmt = result['format']
        i = self.text_map.get(q)
        if i is None:
            i = self.text_map[q] = len(self.result_dicts)
            self.result_dicts.append(result)
            self.formats.append(set())
        self.formats[i].add(fmt)

    def __len__(self):
        return len(self.result_dicts)

    def __getitem__(self, x):
        return self.result_dicts[x]

    @property
    def title(self):
        if self._title is None:
            with suppress(Exception):
                self._title = get_db().field_for('title', self.book_id)
            self._title = self._title or _('Unknown book')
        return self._title

    @property
    def authors(self):
        if self._authors is None:
            with suppress(Exception):
                self._authors = get_db().field_for('authors', self.book_id)
            self._authors = self._authors or [_('Unknown author')]
        return self._authors

    @property
    def cover(self):
        try:
            ans = get_db().cover(self.book_id, as_pixmap=True)
        except Exception:
            ans = QPixmap()
        if ans.isNull():
            ic = QIcon.ic('default_cover.png')
            ans = ic.pixmap(ic.availableSizes()[0])
        return ans

    @property
    def cover_as_image(self):
        try:
            ans = get_db().cover(self.book_id, as_image=True)
        except Exception:
            ans = QImage()
        return ans

    @property
    def series(self):
        if self._series is None:
            try:
                self._series = get_db().field_for('series', self.book_id)
            except Exception:
                self._series = ''
        return self._series

    @property
    def series_index(self):
        if self._series_index is None:
            try:
                self._series_index = get_db().field_for('series_index', self.book_id)
            except Exception:
                self._series_index = 1
        return self._series_index

    @property
    def book_in_db(self):
        if self._book_in_db is None:
            self._book_in_db = get_db().has_book(self.book_id)
        return self._book_in_db

    def preload(self, titles, authors, series, series_indices, in_db):
        self._title = titles[self.book_id]
        self._authors = authors[self.book_id]
        self._series = series[self.book_id]
        self._series_index = series_indices[self.book_id]
        self._book_in_db = in_db[self.book_id]


class ResultsModel(QAbstractItemModel):

    result_found = pyqtSignal(int, object)
    all_results_found = pyqtSignal(int)
    search_started = pyqtSignal()
    matches_found = pyqtSignal(int)
    search_complete = pyqtSignal()
    query_failed = pyqtSignal(str, str)
    result_with_context_found = pyqtSignal(object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.italic_font = parent.font() if parent else QFont()
        self.italic_font.setItalic(True)
        self.results = []
        self.query_id_counter = count()
        self.current_query_id = -1
        self.current_thread_abort = Event()
        self.current_thread = None
        self.current_search_key = None
        self.result_found.connect(self.result_with_text_found, type=Qt.ConnectionType.QueuedConnection)
        self.all_results_found.connect(self.signal_search_complete, type=Qt.ConnectionType.QueuedConnection)

    def all_book_ids(self):
        for r in self.results:
            yield r.book_id

    def clear_results(self):
        self.current_query_id = -1
        self.current_thread_abort.set()
        self.current_search_key = None
        self.search_started.emit()
        self.matches_found.emit(-1)
        self.beginResetModel()
        self.results = []
        self.endResetModel()
        self.search_complete.emit()

    def abort_search(self):
        self.current_thread_abort.set()
        self.signal_search_complete(self.current_query_id)
        self.current_search_key = None  # so that re-doing the search works

    def get_result(self, book_id, result_num):
        idx = self.result_map[book_id]
        results = self.results[idx]
        return results.result_dicts[result_num]

    def search(self, fts_engine_query, use_stemming=True, restrict_to_book_ids=None):
        db = get_db()
        failure = []
        matching_book_ids = []

        def construct(all_matches):
            self.result_map = r = {}
            sr = self.results = []

            try:
                for x in all_matches:
                    book_id = x['book_id']
                    results = r.get(book_id)
                    if results is None:
                        results = Results(book_id)
                        r[book_id] = len(sr)
                        sr.append(results)
                        matching_book_ids.append(book_id)
            except FTSQueryError as e:
                failure.append(e)

        sk = fts_engine_query, use_stemming, restrict_to_book_ids, id(db)
        if sk == self.current_search_key:
            return False
        self.current_thread_abort.set()
        self.current_search_key = sk
        self.search_started.emit()
        self.matches_found.emit(-1)
        self.beginResetModel()
        db.fts_search(
            fts_engine_query, use_stemming=use_stemming, highlight_start='\x1d', highlight_end='\x1d', snippet_size=64,
            restrict_to_book_ids=restrict_to_book_ids, result_type=construct, return_text=False
        )
        self.endResetModel()
        if not failure:
            self.matches_found.emit(len(self.results))
        self.current_query_id = next(self.query_id_counter)
        self.current_thread_abort = Event()
        if failure:
            self.current_thread = Thread(target=lambda *a: None)
            self.all_results_found.emit(self.current_query_id)
            if fts_engine_query.strip():
                self.query_failed.emit(fts_engine_query, str(failure[0]))
        else:
            self.current_thread = Thread(
                name='FTSQuery', daemon=True, target=self.search_text_in_thread, args=(
                    self.current_query_id, self.current_thread_abort, matching_book_ids, fts_engine_query),
                kwargs=dict(
                    use_stemming=use_stemming, highlight_start='\x1d', highlight_end='\x1d', snippet_size=64,
                    return_text=True)
            )
        self.current_thread.start()
        return True

    def remove_book(self, book_id):
        idx = self.result_map.get(book_id)
        if idx is not None:
            self.beginRemoveRows(ROOT, idx, idx)
            del self.results[idx]
            del self.result_map[book_id]
            self.endRemoveRows()
            self.matches_found.emit(len(self.results))
            return True
        return False

    def search_text_in_thread(self, query_id, abort, book_ids, *a, **kw):
        db = get_db()
        for book_id in book_ids:
            kw['restrict_to_book_ids'] = {book_id}
            for result in db.fts_search(*a, **kw):
                # wait for some time so that other threads/processes can be scheduled
                if abort.wait(0.01):
                    return
                try:
                    self.result_found.emit(query_id, result)
                except RuntimeError:  # if dialog is deleted from under us
                    return
        with suppress(RuntimeError):
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
            parent.add_result_with_text(result)
            self.endInsertRows()
            self.result_with_context_found.emit(parent, r)

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

    def flags(self, index):
        item = self.index_to_entry(index)
        if item is None:
            return Qt.ItemFlag.NoItemFlags
        if isinstance(item, Results):
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemNeverHasChildren

    def data_for_book(self, item, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return item.title
        if role == Qt.ItemDataRole.UserRole:
            return item
        if role == Qt.ItemDataRole.FontRole:
            return self.italic_font

    def data_for_match(self, item, role):
        if role == Qt.ItemDataRole.UserRole:
            return item

    def data_for_index(self, index):
        item = self.index_to_entry(index)
        if item is None:
            return None, None
        if isinstance(item, Results):
            return item, None
        return self.index_to_entry(self.parent(index)), item


class ResultsView(QTreeView):

    current_changed = pyqtSignal(object, object)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHeaderHidden(True)
        self.setModel(model)
        self.delegate = SearchDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setUniformRowHeights(True)

    def keyPressEvent(self, ev):
        i = self.currentIndex()
        ret = super().keyPressEvent(ev)
        if self.currentIndex() != i:
            self.scrollTo(self.currentIndex())
        return ret

    def currentChanged(self, current, previous):
        results, individual_match = self.model().data_for_index(current)
        if individual_match is not None:
            individual_match = current.row()
        self.current_changed.emit(results, individual_match)

    def focus_self(self):
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_context_menu(self, pos):
        index = self.indexAt(pos)
        results, match = self.model().data_for_index(index)
        m = QMenu(self)
        if results:
            m.addAction(QIcon.ic('lt.png'), _('Jump to this book in the library'), partial(jump_to_book, results.book_id, self))
            m.addAction(QIcon.ic('marked.png'), _('Mark this book in the library'), partial(mark_books, results.book_id))
            if match is not None:
                match = index.row()
                m.addAction(QIcon.ic('view.png'), _('View this book at this search result'), partial(open_book, results, match_index=match))
            else:
                m.addAction(QIcon.ic('view.png'), _('View this book'), partial(open_book, results))
        m.addSeparator()
        m.addAction(QIcon.ic('plus.png'), _('Expand all'), self.expandAll)
        m.addAction(QIcon.ic('minus.png'), _('Collapse all'), self.collapseAll)
        m.exec(self.mapToGlobal(pos))


class Summary(QLabel):

    frames = ('⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏')
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.linkActivated.connect(self.stop_requested)
        self.timer = t = QTimer(self)
        t.setInterval(120)
        t.timeout.connect(self.update_summary)
        self.stopped_at = self.started_at = 0
        self.num_matches_found = self.frame = -1

    def start(self):
        self.frame = -1
        self.num_matches_found = -2
        self.stopped_at = 0
        self.started_at = time.monotonic()
        self.timer.start()

    def stop(self):
        self.stopped_at = time.monotonic()
        self.timer.stop()
        self.update_summary()

    def set_num_of_matches_found(self, num: int) -> None:
        self.num_matches_found = num
        self.update_summary()

    def update_summary(self):
        if self.num_matches_found < 0:
            self.setText(_('Searching...') if self.num_matches_found == -2 else '')
            return
        self.frame += 1
        self.frame %= len(self.frames)
        frame = self.frames[self.frame]
        base = ngettext('One book', '{num} books', self.num_matches_found).format(num=self.num_matches_found)
        dim_color = self.palette().color(QPalette.Disabled, QPalette.Text).name()
        duration = (self.stopped_at or time.monotonic()) - self.started_at
        if duration < 60:
            if self.stopped_at:
                duration = str(round(duration)) + 's'
            else:
                duration = f'{duration:.1f}s'
        else:
            m, s = divmod(int(duration), 60)
            duration = f'{m}m {s}s'
        duration_text = f'<span style="color:{dim_color}">{duration}</span>'
        if self.stopped_at:
            self.setText(f'{base} {duration_text}')
        else:
            self.setText(
                f'{base} {frame} <a href="stop://me.com" style="text-decoration: none">{_("Stop")}</a> {duration_text}')


class SwitchViewButton(QToolButton):

    visualisation_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.update_state()
        self.clicked.connect(self.toggle_state)

    def update_state(self):
        if gprefs['fts_visualisation'] == 'cards':
            ic = QIcon.ic('highlight_only_on.png')
            tt = _('Switch to a compact view of the results')
        else:
            ic = QIcon.ic('grid.png')
            tt = _('Switch to a detailed view of the results, with covers')
        self.setIcon(ic)
        self.setToolTip(tt)

    def toggle_state(self):
        val = 'compact' if gprefs['fts_visualisation'] == 'cards' else 'cards'
        gprefs['fts_visualisation'] = val
        self.update_state()
        self.visualisation_changed.emit(val)


class SearchInputPanel(QWidget):

    search_signal = pyqtSignal(str)
    clear_search = pyqtSignal()
    request_stop_search = pyqtSignal()
    visualisation_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.started_at = self.stopped_at = 0
        self.num_matches_found = -1
        self.search_box = sb = SearchBox(self)
        sb.cleared.connect(self.clear_search)
        sb.initialize('library-fts-search-box')
        sb.lineEdit().returnPressed.connect(self.search_requested)
        sb.lineEdit().setPlaceholderText(_('Enter words to search for'))
        self.search_button = sb = QPushButton(QIcon.ic('search.png'), _('&Search'), self)
        sb.clicked.connect(self.search_requested)
        self.restrict = r = QCheckBox(_('&Restrict searched books'))
        r.setToolTip('<p>' + _(
            'Restrict search results to only the books currently showing in the main'
            ' library screen. This means that any Virtual libraries or search results'
            ' are applied.'))
        r.setChecked(gprefs['fts_library_restrict_books'])
        r.stateChanged.connect(lambda state: gprefs.set('fts_library_restrict_books', state != Qt.CheckState.Unchecked.value))
        self.related = rw = QCheckBox(_('&Match on related words'))
        rw.setToolTip('<p>' + _(
            'With this option searching for words will also match on any related words (supported in several languages). For'
            ' example, in the English language: {0} matches {1} and {2} as well').format(
            '<i>correction</i>', '<i>correcting</i>', '<i>corrected</i>'))
        rw.setChecked(gprefs['fts_library_use_stemmer'])
        rw.stateChanged.connect(lambda state: gprefs.set('fts_library_use_stemmer', state != Qt.CheckState.Unchecked.value))
        self.summary = s = Summary(self)
        s.stop_requested.connect(self.request_stop_search)
        self.switch_view_button = b = SwitchViewButton(self)
        b.visualisation_changed.connect(self.visualisation_changed)
        self.do_layout()

    def do_layout(self):
        QVBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.hsb = hsb = QHBoxLayout()
        self.layout().addLayout(hsb)
        hsb.addWidget(self.switch_view_button)
        hsb.addWidget(self.search_box, stretch=10)
        hsb.addWidget(self.search_button)
        self.h1 = h1 = QHBoxLayout()
        self.layout().addLayout(h1)
        h1.addWidget(self.restrict), h1.addWidget(self.related), h1.addStretch(), h1.addWidget(self.summary)

    def clear_history(self):
        self.search_box.clear_history()

    def set_search_text(self, text):
        self.search_box.setText(text)

    def start(self):
        self.summary.start()

    def stop(self):
        self.summary.stop()

    def search_requested(self):
        text = self.search_box.text().strip()
        self.search_signal.emit(text)

    def matches_found(self, num):
        self.summary.set_num_of_matches_found(num)


class ResultDetails(QWidget):

    show_in_viewer = pyqtSignal(int, int, str)
    remove_book_from_results = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.key = None
        self.pixmap_label = pl = QLabel(self)
        pl.setScaledContents(True)
        self.book_info = bi = HTMLDisplay(self)
        bi.setDefaultStyleSheet('a { text-decoration: none; }')
        bi.anchor_clicked.connect(self.book_info_anchor_clicked)
        self.results = r = HTMLDisplay(self)
        r.setDefaultStyleSheet('a { text-decoration: none; }')
        r.anchor_clicked.connect(self.results_anchor_clicked)

    @property
    def current_book_id(self):
        return -1 if self.key is None else self.key[0]

    @property
    def current_individual_match(self):
        return None if self.key is None else self.key[2]

    def book_info_anchor_clicked(self, url):
        if self.current_book_id > 0:
            if url.host() == 'mark':
                mark_books(self.current_book_id)
            elif url.host() == 'jump':
                jump_to_book(self.current_book_id, self)
            elif url.host() == 'unindex':
                db = get_db()
                db.fts_unindex(self.current_book_id)
                self.remove_book_from_results.emit(self.current_book_id)
            elif url.host() == 'reindex':
                reindex_book(self.current_book_id, self)
                self.remove_book_from_results.emit(self.current_book_id)

    def results_anchor_clicked(self, url):
        if self.current_book_id > 0 and url.scheme() == 'book':
            book_id, result_num, fmt = url.path().strip('/').split('/')
            book_id, result_num = int(book_id), int(result_num)
            self.show_in_viewer.emit(int(book_id), int(result_num), fmt)

    def resizeEvent(self, ev):
        self.do_layout()

    def do_layout(self):
        g = self.geometry()
        max_width, max_height = g.width() // 2, g.height() // 3
        p = self.pixmap_label.pixmap()
        scaled, nw, nh = fit_image(p.width(), p.height(), max_width, max_height)
        self.pixmap_label.setGeometry(QRect(0, 0, nw, nh))
        w = g.width() - nw - 8
        d = self.book_info.document()
        d.setDocumentMargin(0)
        d.setTextWidth(float(w))
        ph = self.pixmap_label.height()
        self.book_info.setGeometry(QRect(self.pixmap_label.geometry().right() + 8, 0, w, ph))
        top = max(self.book_info.geometry().bottom(), self.pixmap_label.geometry().bottom())
        self.results.setGeometry(QRect(0, top, g.width(), g.height() - top))

    def show_result(self, results, individual_match=None):
        key = results.book_id, len(results.result_dicts), individual_match
        if key == self.key:
            return False
        old_current_book_id = self.current_book_id
        self.key = key
        if old_current_book_id != self.current_book_id:
            self.pixmap_label.setPixmap(results.cover)
            self.render_book_info(results)
        self.render_results(results, individual_match)
        self.do_layout()
        return True

    def result_with_context_found(self, results, individual_match):
        if results.book_id == self.current_book_id:
            return self.show_result(results, self.current_individual_match)
        return False

    def render_book_info(self, results):
        t = results.title
        if len(t) > 72:
            t = t[:71] + '…'
        text = f'<p><b>{prepare_string_for_xml(t)}</b><br>'
        au = results.authors
        if len(au) > 3:
            au = list(au[:3]) + ['…']
        text += f'{prepare_string_for_xml(authors_to_string(au))}</p>'
        if results.series:
            sidx = fmt_sidx(results.series_index or 0, use_roman=config['use_roman_numerals_for_series_number'])
            series = results.series
            if len(series) > 60:
                series = series[:59] + '…'
            series = prepare_string_for_xml(series)
            text += '<p>' + _('{series_index} of {series}').format(series_index=sidx, series=series) + '</p>'
        ict = '<img valign="bottom" src="calibre-icon:///{}" width=16 height=16>'
        text += '<p><a href="calibre://jump" title="{1}">{2}\xa0{0}</a>\xa0\xa0\xa0 '.format(
            _('Select'), '<p>' + _('Scroll to this book in the calibre library book list and select it [{}]').format(
                jump_shortcut()), ict.format('lt.png'))
        text += '<a href="calibre://mark" title="{1}">{2}\xa0{0}</a></p>'.format(
            _('Mark'), '<p>' + _(
                'Put a pin on this book in the calibre library, for future reference.\n'
                'You can search for marked books using the search term: {0}').format('<p>marked:true'), ict.format('marked.png'))
        if get_db().has_id(results.book_id):
            text += '<p><a href="calibre://reindex" title="{1}">{2}\xa0{0}</a>'.format(
                _('Re-index'), _('Re-index this book. Useful if the book has been changed outside of calibre, and thus not automatically re-indexed.'),
                ict.format('view-refresh.png'))
        else:
            text += '<p><a href="calibre://unindex" title="{1}">{2}\xa0{0}</a>'.format(
                _('Un-index'), _('This book has been deleted from the library but is still present in the'
                                          ' full text search index. Remove it.'), ict.format('trash.png'))
        text += '<p>' + _('This book may have more than one match, only a single match per book is shown.')
        self.book_info.setHtml(text)

    def render_results(self, results, individual_match=None):
        html = []

        ci = self.current_individual_match
        for i, (result, formats) in enumerate(zip(results.result_dicts, results.formats)):
            if ci is not None and ci != i:
                continue
            text = result['text']
            text = markup_text(text)
            html.append('<hr>')
            for fmt in formats:
                fmt = fmt.upper()
                tt = _('Open the book, in the {fmt} format.\nWhen using the calibre E-book viewer, it will attempt to scroll\n'
                       'to this search result automatically.'
                       ).format(fmt=fmt)
                html.append(f'<a title="{tt}" href="book:///{self.current_book_id}/{i}/{fmt}">{fmt}</a>\xa0 ')
            html.append(f'<p>{text}</p>')
        self.results.setHtml('\n'.join(html))

    def clear(self):
        self.key = None
        self.book_info.setHtml('')
        self.results.setHtml('')
        self.pixmap_label.setPixmap(QPixmap())


class DetailsPanel(QStackedWidget):

    show_in_viewer = pyqtSignal(int, int, str)
    remove_book_from_results = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.help_panel = hp = help_panel(self)
        self.addWidget(hp)
        self.result_details = rd = ResultDetails(self)
        rd.show_in_viewer.connect(self.show_in_viewer)
        rd.remove_book_from_results.connect(self.remove_book_from_results)
        self.addWidget(rd)

    def sizeHint(self):
        return QSize(400, 700)

    def show_result(self, results=None, individual_match=None):
        if results is None:
            self.setCurrentIndex(0)
        else:
            self.setCurrentIndex(1)
            self.result_details.show_result(results, individual_match)

    def result_with_context_found(self, results, individual_match):
        if self.currentIndex() == 1:
            self.result_details.result_with_context_found(results, individual_match)

    def clear(self):
        self.setCurrentIndex(0)
        self.result_details.clear()


class LeftPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        QVBoxLayout(self).setContentsMargins(0, 0, 0, 0)

    def sizeHint(self):
        return QSize(700, 700)


class SplitView(QSplitter):

    show_in_viewer = pyqtSignal(int, int, str)
    remove_book_from_results = pyqtSignal(int)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setChildrenCollapsible(False)
        self.left_panel = lp = LeftPanel(self)
        self.addWidget(lp)
        self.results_view = rv = ResultsView(model, parent=self)
        lp.layout().addWidget(rv)
        self.details = d = DetailsPanel(parent=self)
        self.addWidget(d)
        model.result_with_context_found.connect(d.result_with_context_found)
        model.matches_found.connect(self.matches_found)
        model.search_started.connect(self.search_started)
        d.show_in_viewer.connect(self.show_in_viewer)
        d.remove_book_from_results.connect(self.remove_book_from_results)
        rv.current_changed.connect(d.show_result)
        st = gprefs.get('fts_search_splitter_state')
        if st is not None:
            self.restoreState(st)

    def shutdown(self):
        b = self.saveState()
        gprefs['fts_search_splitter_state'] = bytearray(b)

    def search_started(self):
        self.results_view.focus_self()
        self.details.clear()

    def matches_found(self, num):
        self.results_view.expandAll()
        self.results_view.setCurrentIndex(self.results_view.model().index(0, 0))

    def current_result(self):
        idx = self.results_view.currentIndex()
        if idx.isValid():
            results, match = self.results_view.model().data_for_index(idx)
            if match is None:
                match = idx.row()
            return results, match
        return None, None


class ResultsPanel(QWidget):

    switch_to_scan_panel = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.jump_to_current_book_action = ac = QAction(self)
        ac.triggered.connect(self.jump_to_current_book)
        ac.setShortcut(QKeySequence('Ctrl+S', QKeySequence.SequenceFormat.PortableText))
        jump_shortcut(ac.shortcut().toString(QKeySequence.SequenceFormat.NativeText))
        self.mark_all_books_action = ac = QAction(QIcon.ic('marked.png'), _('Mark all matched books in the library'), self)
        ac.triggered.connect(partial(self.mark_books, 'mark'))
        ac.setShortcut(QKeySequence('Ctrl+Alt+M', QKeySequence.SequenceFormat.PortableText))
        self.select_all_books_action = ac = QAction(QIcon.ic('edit-select-all.png'), _('Select all matched books in the library'), self)
        ac.triggered.connect(partial(self.mark_books, 'select'))
        ac.setShortcut(QKeySequence('Ctrl+Alt+S', QKeySequence.SequenceFormat.PortableText))
        self.mark_select_all_books_action = ac = QAction(_('Mark and select all matched books in the library'), self)
        ac.triggered.connect(partial(self.mark_books, 'mark-select'))
        ac.setShortcut(QKeySequence('Ctrl+Alt+B', QKeySequence.SequenceFormat.PortableText))
        if isinstance(parent, QDialog):
            parent.finished.connect(self.shutdown)
        self.results_model = m = ResultsModel(self)
        m.query_failed.connect(self.query_failed, type=Qt.ConnectionType.QueuedConnection)
        m.search_started.connect(self.search_started)
        m.matches_found.connect(self.matches_found)
        m.search_complete.connect(self.search_complete)
        self.sip = sip = SearchInputPanel(parent=self)
        sip.request_stop_search.connect(self.request_stop_search)
        sip.search_signal.connect(self.search)
        sip.clear_search.connect(self.clear_results)
        sip.visualisation_changed.connect(self.set_view_mode)
        self.split_view = sv = SplitView(self.results_model, self)
        sv.show_in_viewer.connect(self.show_in_viewer)
        sv.remove_book_from_results.connect(self.remove_book_from_results)
        QStackedLayout(self)
        self.layout().addWidget(sv)
        self.card_view = cv = CardsView(self.results_model, self)
        cv.link_activated.connect(self._cards_link_activated)
        self.layout().addWidget(cv)
        self.set_view_mode(gprefs['fts_visualisation'])

    def set_view_mode(self, mode: str = 'compact'):
        if mode == 'compact':
            self.split_view.left_panel.layout().insertWidget(0, self.sip)
            self.layout().setCurrentIndex(0)
        else:
            self.card_view.layout().insertWidget(0, self.sip)
            self.layout().setCurrentIndex(1)

    @property
    def current_view(self):
        self.layout().currentWidget()

    def search(self, text: str):
        gui = get_gui()
        restrict = None
        if gui and gprefs['fts_library_restrict_books']:
            restrict = frozenset(gui.library_view.model().all_current_book_ids())
        with BusyCursor():
            self.results_model.search(text, restrict_to_book_ids=restrict, use_stemming=gprefs['fts_library_use_stemmer'])

    def search_started(self):
        self.sip.start()

    def search_complete(self):
        self.sip.stop()

    def matches_found(self, num):
        self.sip.matches_found(num)

    def jump_to_current_book(self):
        results, match = self.current_view.current_result()
        if results:
            jump_to_book(results.book_id, self)

    def view_current_result(self):
        results, match = self.current_view.current_result()
        if results:
            open_book(results, match)
            return True
        return False

    def clear_history(self):
        self.sip.clear_history()

    def set_search_text(self, text):
        self.sip.set_search_text(text)

    def remove_book_from_results(self, book_id):
        self.results_model.remove_book(book_id)

    def _cards_link_activated(self, url: QUrl):
        which = url.host()
        parts = url.path().strip('/').split('/')
        book_id = int(parts[0])
        match which:
            case 'jump':
                jump_to_book(book_id, self)
            case 'mark':
                mark_books(book_id)
            case 'unindex':
                get_db().fts_unindex(book_id)
                self.remove_book_from_results(book_id)
            case 'reindex':
                reindex_book(book_id, self)
                self.remove_book_from_results(book_id)
            case 'show':
                self.show_in_viewer(book_id, int(parts[2]), parts[1])

    def show_in_viewer(self, book_id, result_num, fmt):
        r = self.results_model.get_result(book_id, result_num)
        show_in_viewer(book_id, r['text'], fmt)

    def request_stop_search(self):
        if question_dialog(self, _('Are you sure?'), _('Abort the current search?')):
            self.results_model.abort_search()

    def specialize_button_box(self, bb):
        bb.clear()
        bb.addButton(QDialogButtonBox.StandardButton.Close)
        bb.addButton(_('Show &indexing status'), QDialogButtonBox.ButtonRole.ActionRole).clicked.connect(self.switch_to_scan_panel)
        b = bb.addButton(_('&Mark all books'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('marked.png'))
        m = QMenu(b)
        m.addAction(self.mark_all_books_action)
        m.addAction(self.select_all_books_action)
        if not hasattr(self, 'colored_pin'):
            self.colored_pin = QIcon(render_pin())
            self.mark_select_all_books_action.setIcon(self.colored_pin)
        m.addAction(self.mark_select_all_books_action)
        b.setMenu(m)

    def mark_books(self, which):
        gui = get_gui()
        if gui is not None:
            book_ids = tuple(self.results_view.model().all_book_ids())
            if which == 'mark':
                gui.iactions['Mark Books'].add_ids(book_ids)
            elif which == 'select':
                gui.library_view.select_rows(book_ids)
            elif which == 'mark-select':
                gui.iactions['Mark Books'].add_ids(book_ids)
                gui.library_view.select_rows(book_ids)

    def clear_results(self):
        self.results_model.clear_results()

    def shutdown(self):
        self.split_view.shutdown()
        self.card_view.shutdown()
        self.clear_results()
        self.sip.search_box.setText('')

    def on_show(self):
        self.sip.search_box.setFocus(Qt.FocusReason.OtherFocusReason)

    def query_failed(self, query, err_msg):
        error_dialog(self, _('Invalid search query'), _(
            'The search query: {query} was not understood. See <a href="{fts_url}">here</a> for details on the'
            ' supported query syntax.').format(
                query=query, fts_url=fts_url), det_msg=err_msg, show=True)


def develop(view='compact'):
    from calibre.gui2 import Application
    from calibre.library import db
    app = Application([])
    d = QDialog()
    d.sizeHint = lambda: QSize(1000, 680)
    l = QVBoxLayout(d)
    bb = QDialogButtonBox(d)
    bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)
    get_db.db = db(os.path.expanduser('~/test library'))
    w = ResultsPanel(parent=d)
    w.set_view_mode(view)
    l.addWidget(w)
    l.addWidget(bb)
    from calibre.srv.render_book import Profiler
    with Profiler():
        w.sip.search_box.setText('asimov')
        w.sip.search_button.click()
        d.exec()
    del app


if __name__ == '__main__':
    develop()
