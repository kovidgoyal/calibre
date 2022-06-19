#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import math
import os
import re
import time
import traceback
from contextlib import suppress
from functools import partial
from itertools import count
from qt.core import (
    QAbstractItemModel, QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox,
    QFont, QHBoxLayout, QIcon, QLabel, QMenu, QModelIndex, QPixmap, QPushButton,
    QRect, QSize, QSplitter, QStackedWidget, Qt, QTreeView, QVBoxLayout, QWidget,
    pyqtSignal
)
from threading import Event, Thread

from calibre import fit_image, prepare_string_for_xml
from calibre.db import FTSQueryError
from calibre.ebooks.metadata import authors_to_string, fmt_sidx
from calibre.gui2 import config, error_dialog, gprefs, question_dialog, safe_open_url
from calibre.gui2.fts.utils import get_db
from calibre.gui2.library.annotations import BusyCursor
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.ui import get_gui
from calibre.gui2.viewer.widgets import ResultsDelegate, SearchBox
from calibre.gui2.widgets2 import HTMLDisplay

ROOT = QModelIndex()
sanitize_text_pat = re.compile(r'\s+')
fts_url = 'https://www.sqlite.org/fts5.html#full_text_query_syntax'


def mark_books(*book_ids):
    gui = get_gui()
    if gui is not None:
        gui.iactions['Mark Books'].add_ids(book_ids)


def jump_to_book(book_id):
    gui = get_gui()
    if gui is not None:
        gui.library_view.select_rows((book_id,))


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

    _title = _authors = _series = _series_index = None

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
            try:
                self._title = get_db().field_for('title', self.book_id)
            except Exception:
                self._title = _('Unknown book')
        return self._title

    @property
    def authors(self):
        if self._authors is None:
            try:
                self._authors = get_db().field_for('authors', self.book_id)
            except Exception:
                self._authors = _('Unknown author'),
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
            return 0
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

    search_started = pyqtSignal()
    matches_found = pyqtSignal(int)
    search_complete = pyqtSignal()
    current_changed = pyqtSignal(object, object)
    result_with_context_found = pyqtSignal(object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHeaderHidden(True)
        self.m = ResultsModel(self)
        self.m.result_with_context_found.connect(self.result_with_context_found)
        self.m.search_complete.connect(self.search_complete)
        self.m.search_started.connect(self.search_started)
        self.m.search_started.connect(self.focus_self)
        self.m.query_failed.connect(self.query_failed, type=Qt.ConnectionType.QueuedConnection)
        self.m.matches_found.connect(self.matches_found)
        self.setModel(self.m)
        self.delegate = SearchDelegate(self)
        self.setItemDelegate(self.delegate)

    def currentChanged(self, current, previous):
        results, individual_match = self.m.data_for_index(current)
        if individual_match is not None:
            individual_match = current.row()
        self.current_changed.emit(results, individual_match)

    def focus_self(self):
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def query_failed(self, query, err_msg):
        error_dialog(self, _('Invalid search query'), _(
            'The search query: {query} was not understood. See <a href="{fts_url}">here</a> for details on the'
            ' supported query syntax.').format(
                query=query, fts_url=fts_url), det_msg=err_msg, show=True)

    def search(self, *a):
        gui = get_gui()
        restrict = None
        if gui and gprefs['fts_library_restrict_books']:
            restrict = gui.library_view.get_selected_ids(as_set=True)
        with BusyCursor():
            self.m.search(*a, restrict_to_book_ids=restrict, use_stemming=gprefs['fts_library_use_stemmer'])
            self.expandAll()

    def show_context_menu(self, pos):
        index = self.indexAt(pos)
        results, match = self.m.data_for_index(index)
        m = QMenu(self)
        if results:
            m.addAction(QIcon.ic('lt.png'), _('Jump to this book in the library'), partial(jump_to_book, results.book_id))
            m.addAction(QIcon.ic('marked.png'), _('Mark this book in the library'), partial(mark_books, results.book_id))
        m.addSeparator()
        m.addAction(QIcon.ic('plus.png'), _('Expand all'), self.expandAll)
        m.addAction(QIcon.ic('minus.png'), _('Collapse all'), self.collapseAll)
        m.exec(self.mapToGlobal(pos))


class Spinner(ProgressIndicator):

    last_mouse_press_at = 0
    clicked = pyqtSignal(object)

    def __init__(self, *a):
        super().__init__(*a)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        return QSize(8, 8)

    def paintEvent(self, ev):
        if self.isAnimated():
            super().paintEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_press_at = time.monotonic()
            ev.accept()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            dt = time.monotonic() - self.last_mouse_press_at
            self.last_mouse_press_at = 0
            if dt < 0.5:
                self.clicked.emit(ev)
                ev.accept()
                return
        super().mouseReleaseEvent(ev)


class SearchInputPanel(QWidget):

    search_signal = pyqtSignal(object)
    clear_search = pyqtSignal()
    request_stop_search = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        QHBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.v1 = v1 = QVBoxLayout()
        v1.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.layout().addLayout(v1)
        self.search_box = sb = SearchBox(self)
        sb.cleared.connect(self.clear_search)
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
        r.stateChanged.connect(lambda state: gprefs.set('fts_library_restrict_books', state != Qt.CheckState.Unchecked.value))
        self.related = rw = QCheckBox(_('&Match on related words'))
        rw.setToolTip('<p>' + _(
            'With this option searching for words will also match on any related words (supported in several languages). For'
            ' example, in the English language: <i>correction</i> matches <i>correcting</i> and <i>corrected</i> as well'))
        rw.setChecked(gprefs['fts_library_use_stemmer'])
        rw.stateChanged.connect(lambda state: gprefs.set('fts_library_use_stemmer', state != Qt.CheckState.Unchecked.value))
        self.summary = s = QLabel(self)
        h1.addWidget(r), h1.addWidget(rw), h1.addStretch(), h1.addWidget(s)

        self.search_button = sb = QPushButton(QIcon.ic('search.png'), _('&Search'), self)
        sb.clicked.connect(self.search_requested)
        self.v2 = v2 = QVBoxLayout()
        v2.addWidget(sb)
        self.pi = pi = Spinner(self)
        pi.clicked.connect(self.request_stop_search)
        v2.addWidget(pi)

        self.layout().addLayout(v2)

    def start(self):
        self.pi.start()

    def stop(self):
        self.pi.stop()

    def search_requested(self):
        text = self.search_box.text().strip()
        self.search_signal.emit(text)

    def matches_found(self, num):
        if num < 0:
            self.summary.setText('')
        else:
            self.summary.setText(ngettext('One book', '{num} books', num).format(num=num))


class ResultDetails(QWidget):

    show_in_viewer = pyqtSignal(int, int, str)

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
                jump_to_book(self.current_book_id)

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
        h = min(int(math.ceil(d.size().height())), self.pixmap_label.height())
        self.book_info.setGeometry(QRect(self.pixmap_label.geometry().right() + 8, 0, w, h))
        if self.book_info.horizontalScrollBar().isVisible():
            h += self.book_info.horizontalScrollBar().height() + 1
            self.book_info.setGeometry(QRect(self.pixmap_label.geometry().right() + 8, 0, w, h))
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
        text = f'<p><b>{prepare_string_for_xml(results.title)}</b><br>'
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
        text += '<p><a href="calibre://jump" title="{1}"><img valign="bottom" src="calibre-icon:///lt.png" width=16 height=16>\xa0{0}</a>\xa0\xa0\xa0 '.format(
            _('Select'), '<p>' + _('Scroll to this book in the calibre library book list and select it.'))
        text += '<a href="calibre://mark" title="{1}"><img valign="bottom" src="calibre-icon:///marked.png" width=16 height=16>\xa0{0}</a></p>'.format(
            _('Mark'), '<p>' + _(
                'Put a pin on this book in the calibre library, for future reference.'
                ' You can search for marked books using the search term: {0}').format('<p>marked:true'))
        self.book_info.setHtml(text)

    def render_results(self, results, individual_match=None):
        html = []
        space_pat = re.compile(r'\s+')
        markup_pat = re.compile('\x1d')

        def markup_text(text):
            count = 0

            def sub(m):
                nonlocal count
                count += 1
                return '<b><i>' if count % 2 else '</i></b>'

            return space_pat.sub(' ', markup_pat.sub(sub, text))

        ci = self.current_individual_match
        for i, (result, formats) in enumerate(zip(results.result_dicts, results.formats)):
            if ci is not None and ci != i:
                continue
            text = result['text']
            text = markup_text(prepare_string_for_xml(text))
            html.append('<hr>')
            for fmt in formats:
                fmt = fmt.upper()
                tt = _('Open the book, in the {fmt} format.\nWhen using the calibre viewer, it will attempt to scroll\nto this search result automatically.'
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

    def __init__(self, parent=None):
        super().__init__(parent)

        # help panel {{{
        self.help_panel = hp = HTMLDisplay(self)
        hp.setDefaultStyleSheet('a { text-decoration: none; }')
        hp.setHtml('''
<style>
div { margin-top: 0.5ex }
.h { font-weight: bold; }
.bq { margin-left: 1em; margin-top: 0.5ex; margin-bottom: 0.5ex; font-style: italic }
p { margin: 0; }
</style>
                   ''' + _('''
<div class="h">Search for single words</div>
<p>Simply type the word:</p>
<div class="bq">awesome<br>calibre</div>

<div class="h">Search for phrases</div>
<p>Enclose the phrase in quotes:</p>
<div class="bq">"early run"<br>"song of love"</div>

<div class="h">Boolean searches</div>
<div class="bq">(calibre AND ebook) NOT gun<br>simple NOT ("high bar" OR hard)</div>

<div class="h">Phrases near each other</div>
<div class="bq">NEAR("people" "in Asia" "try")<br>NEAR("Kovid" "calibre", 30)</div>
<p>Here, 30 is the most words allowed between near groups. Defaults to 10 when unspecified.</p>

<div style="margin-top: 1em"><a href="{fts_url}">Full syntax reference</a></div>
''').format(fts_url=fts_url))
        hp.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hp.document().setDocumentMargin(0)
        hp.anchor_clicked.connect(safe_open_url)
        self.addWidget(hp)
        # }}}

        self.result_details = rd = ResultDetails(self)
        rd.show_in_viewer.connect(self.show_in_viewer)
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
        QVBoxLayout(self)

    def sizeHint(self):
        return QSize(700, 700)


class ResultsPanel(QWidget):

    switch_to_scan_panel = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        if isinstance(parent, QDialog):
            parent.finished.connect(self.shutdown)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.splitter = s = QSplitter(self)
        s.setChildrenCollapsible(False)
        l.addWidget(s)

        self.lp = lp = LeftPanel(self)
        s.addWidget(lp)
        l = lp.layout()
        self.sip = sip = SearchInputPanel(parent=self)
        sip.request_stop_search.connect(self.request_stop_search)
        l.addWidget(sip)
        self.results_view = rv = ResultsView(parent=self)
        l.addWidget(rv)
        self.search = rv.search
        rv.search_started.connect(self.sip.start)
        rv.matches_found.connect(self.sip.matches_found)
        rv.search_complete.connect(self.sip.stop)
        sip.search_signal.connect(self.search)
        sip.clear_search.connect(self.clear_results)

        self.details = d = DetailsPanel(self)
        d.show_in_viewer.connect(self.show_in_viewer)
        rv.current_changed.connect(d.show_result)
        rv.search_started.connect(d.clear)
        rv.result_with_context_found.connect(d.result_with_context_found)
        s.addWidget(d)
        st = gprefs.get('fts_search_splitter_state')
        if st is not None:
            s.restoreState(st)

    def show_in_viewer(self, book_id, result_num, fmt):
        r = self.results_view.m.get_result(book_id, result_num)
        text = r['text'].strip('…').replace('\x1d', '').replace('\xa0', ' ')
        text = sanitize_text_pat.sub(' ', text)
        gui = get_gui()
        if gui is not None:
            gui.iactions['View'].view_format_by_id(book_id, fmt, open_at=f'search:{text}')

    def request_stop_search(self):
        if question_dialog(self, _('Are you sure?'), _('Abort the current search?')):
            self.results_view.m.abort_search()

    def specialize_button_box(self, bb):
        bb.clear()
        bb.addButton(QDialogButtonBox.StandardButton.Close)
        bb.addButton(_('Show &indexing status'), QDialogButtonBox.ButtonRole.ActionRole).clicked.connect(self.switch_to_scan_panel)
        b = bb.addButton(_('&Mark books'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('marked.png'))
        m = QMenu(b)
        m.addAction(QIcon.ic('marked.png'), _('Mark all matched books in the library'), partial(self.mark_books, 'mark'))
        m.addAction(QIcon.ic('edit-select-all.png'), _('Select all matched books in the library'), partial(self.mark_books, 'select'))
        b.setMenu(m)

    def mark_books(self, which):
        gui = get_gui()
        if gui is not None:
            book_ids = tuple(self.results_view.model().all_book_ids())
            if which == 'mark':
                gui.iactions['Mark Books'].add_ids(book_ids)
            elif which == 'select':
                gui.library_view.select_rows(book_ids)

    def clear_results(self):
        self.results_view.m.clear_results()

    def shutdown(self):
        b = self.splitter.saveState()
        gprefs['fts_search_splitter_state'] = bytearray(b)
        self.clear_results()
        self.sip.search_box.setText('')

    def on_show(self):
        self.sip.search_box.setFocus(Qt.FocusReason.OtherFocusReason)


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
    w.sip.search_button.click()
    d.exec()
