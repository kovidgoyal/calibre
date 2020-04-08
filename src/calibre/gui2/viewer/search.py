#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
from collections import Counter
from threading import Thread

import regex
from PyQt5.Qt import (
    QCheckBox, QComboBox, QHBoxLayout, QIcon, QLabel, QListWidget,
    QListWidgetItem, QStaticText, QStyle, QStyledItemDelegate, Qt, QToolButton,
    QVBoxLayout, QWidget, pyqtSignal
)

from calibre.ebooks.conversion.search_replace import REGEX_FLAGS
from calibre.gui2 import warning_dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.viewer.web_view import get_data, get_manifest, vprefs
from calibre.gui2.widgets2 import HistoryComboBox
from polyglot.builtins import iteritems, unicode_type
from polyglot.functools import lru_cache
from polyglot.queue import Queue


class BusySpinner(QWidget):  # {{{

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.pi = ProgressIndicator(self, 24)
        l.addWidget(self.pi)
        self.la = la = QLabel(_('Searching...'))
        l.addWidget(la)
        l.addStretch(10)
        self.is_running = False

    def start(self):
        self.setVisible(True)
        self.pi.start()
        self.is_running = True

    def stop(self):
        self.setVisible(False)
        self.pi.stop()
        self.is_running = False
# }}}


quote_map= {'"':'"“”', "'": "'‘’"}
qpat = regex.compile(r'''(['"])''')
spat = regex.compile(r'(\s+)')


def text_to_regex(text):
    has_leading = text.lstrip() != text
    has_trailing = text.rstrip() != text
    if text and not text.strip():
        return r'\s+'
    ans = []
    for wpart in spat.split(text.strip()):
        if not wpart.strip():
            ans.append(r'\s+')
        else:
            for part in qpat.split(wpart):
                r = quote_map.get(part)
                if r is not None:
                    ans.append('[' + r + ']')
                else:
                    ans.append(regex.escape(part))
    if has_leading:
        ans.insert(0, r'\s+')
    if has_trailing:
        ans.append(r'\s+')
    return ''.join(ans)


class Search(object):

    def __init__(self, text, mode, case_sensitive, backwards):
        self.text, self.mode = text, mode
        self.case_sensitive = case_sensitive
        self.backwards = backwards
        self._regex = None

    def __eq__(self, other):
        if not isinstance(other, Search):
            return False
        return self.text == other.text and self.mode == other.mode and self.case_sensitive == other.case_sensitive

    @property
    def regex(self):
        if self._regex is None:
            expr = self.text
            flags = REGEX_FLAGS
            if not self.case_sensitive:
                flags = regex.IGNORECASE
            if self.mode != 'regex':
                if self.mode == 'word':
                    words = []
                    for part in expr.split():
                        words.append(r'\b{}\b'.format(text_to_regex(part)))
                    expr = r'\s+'.join(words)
                else:
                    expr = text_to_regex(expr)
            self._regex = regex.compile(expr, flags)
        return self._regex

    def __str__(self):
        from collections import namedtuple
        s = ('text', 'mode', 'case_sensitive', 'backwards')
        return str(namedtuple('Search', s)(*tuple(getattr(self, x) for x in s)))


class SearchFinished(object):

    def __init__(self, search_query):
        self.search_query = search_query


class SearchResult(object):

    __slots__ = ('search_query', 'before', 'text', 'after', 'q', 'spine_idx', 'index', 'file_name', '_static_text', 'is_hidden')

    def __init__(self, search_query, before, text, after, q, name, spine_idx, index):
        self.search_query = search_query
        self.q = q
        self.before, self.text, self.after = before, text, after
        self.spine_idx, self.index = spine_idx, index
        self.file_name = name
        self._static_text = None
        self.is_hidden = False

    @property
    def static_text(self):
        if self._static_text is None:
            before_words = self.before.split()
            before = ' '.join(before_words[-3:])
            before_extra = len(before) - 15
            if before_extra > 0:
                before = before[before_extra:]
            before = '…' + before
            before_space = '' if self.before.rstrip() == self.before else ' '
            after_words = self.after.split()
            after = ' '.join(after_words[:3])[:15] + '…'
            after_space = '' if self.after.lstrip() == self.after else ' '
            self._static_text = st = QStaticText('<p>{}{}<b>{}</b>{}{}'.format(before, before_space, self.text, after_space, after))
            st.setTextFormat(Qt.RichText)
            st.setTextWidth(10000)
        return self._static_text

    @property
    def for_js(self):
        return {
            'file_name': self.file_name, 'spine_idx': self.spine_idx, 'index': self.index, 'text': self.text,
            'before': self.before, 'after': self.after, 'mode': self.search_query.mode, 'q': self.q
        }

    def is_result(self, result_from_js):
        return result_from_js['spine_idx'] == self.spine_idx and self.index == result_from_js['index'] and result_from_js['q'] == self.q

    def __str__(self):
        from collections import namedtuple
        s = self.__slots__[:-1]
        return str(namedtuple('SearchResult', s)(*tuple(getattr(self, x) for x in s)))


@lru_cache(maxsize=None)
def searchable_text_for_name(name):
    ans = []
    serialized_data = json.loads(get_data(name)[0])
    stack = []
    for child in serialized_data['tree']['c']:
        if child.get('n') == 'body':
            stack.append(child)
    ignore_text = {'script', 'style', 'title'}
    while stack:
        node = stack.pop()
        if isinstance(node, unicode_type):
            ans.append(node)
            continue
        g = node.get
        name = g('n')
        text = g('x')
        tail = g('l')
        children = g('c')
        if name and text and name not in ignore_text:
            ans.append(text)
        if tail:
            stack.append(tail)
        if children:
            stack.extend(reversed(children))
    return ''.join(ans)


def search_in_name(name, search_query, ctx_size=50):
    raw = searchable_text_for_name(name)
    for match in search_query.regex.finditer(raw):
        start, end = match.span()
        before = raw[max(0, start-ctx_size):start]
        after = raw[end:end+ctx_size]
        yield before, match.group(), after


class SearchBox(HistoryComboBox):

    history_saved = pyqtSignal(object, object)

    def save_history(self):
        ret = HistoryComboBox.save_history(self)
        self.history_saved.emit(self.text(), self.history)
        return ret

    def contextMenuEvent(self, event):
        menu = self.lineEdit().createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(_('Clear search history'), self.clear_history)
        menu.exec_(event.globalPos())


class SearchInput(QWidget):  # {{{

    do_search = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.ignore_search_type_changes = False
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)

        self.search_box = sb = SearchBox(self)
        sb.initialize('viewer-search-panel-expression')
        sb.item_selected.connect(self.saved_search_selected)
        sb.history_saved.connect(self.history_saved)
        sb.lineEdit().setPlaceholderText(_('Search'))
        sb.lineEdit().setClearButtonEnabled(True)
        sb.lineEdit().returnPressed.connect(self.find_next)
        h.addWidget(sb)

        self.next_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.NoFocus)
        nb.setIcon(QIcon(I('arrow-down.png')))
        nb.clicked.connect(self.find_next)
        nb.setToolTip(_('Find next match'))

        self.prev_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.NoFocus)
        nb.setIcon(QIcon(I('arrow-up.png')))
        nb.clicked.connect(self.find_previous)
        nb.setToolTip(_('Find previous match'))

        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)
        self.query_type = qt = QComboBox(self)
        qt.setFocusPolicy(Qt.NoFocus)
        qt.addItem(_('Contains'), 'normal')
        qt.addItem(_('Whole words'), 'word')
        qt.addItem(_('Regex'), 'regex')
        qt.setToolTip(('<p>' + _(
            'Choose the type of search: <ul>'
            '<li><b>Contains</b> will search for the entered text anywhere.'
            '<li><b>Whole words</b> will search for whole words that equal the entered text.'
            '<li><b>Regex</b> will interpret the text as a regular expression.'
        )))
        qt.setCurrentIndex(qt.findData(vprefs.get('viewer-search-mode', 'normal') or 'normal'))
        qt.currentIndexChanged.connect(self.save_search_type)
        h.addWidget(qt)

        self.case_sensitive = cs = QCheckBox(_('&Case sensitive'), self)
        cs.setFocusPolicy(Qt.NoFocus)
        cs.setChecked(bool(vprefs.get('viewer-search-case-sensitive', False)))
        cs.stateChanged.connect(self.save_search_type)
        h.addWidget(cs)

    def history_saved(self, new_text, history):
        if new_text:
            sss = vprefs.get('saved-search-settings') or {}
            sss[new_text] = {'case_sensitive': self.case_sensitive.isChecked(), 'mode': self.query_type.currentData()}
            history = frozenset(history)
            sss = {k: v for k, v in iteritems(sss) if k in history}
            vprefs['saved-search-settings'] = sss

    def save_search_type(self):
        text = self.search_box.currentText()
        if text and not self.ignore_search_type_changes:
            sss = vprefs.get('saved-search-settings') or {}
            sss[text] = {'case_sensitive': self.case_sensitive.isChecked(), 'mode': self.query_type.currentData()}
            vprefs['saved-search-settings'] = sss

    def saved_search_selected(self):
        text = self.search_box.currentText()
        if text:
            s = (vprefs.get('saved-search-settings') or {}).get(text)
            if s:
                self.ignore_search_type_changes = True
                if 'case_sensitive' in s:
                    self.case_sensitive.setChecked(s['case_sensitive'])
                if 'mode' in s:
                    idx = self.query_type.findData(s['mode'])
                    if idx > -1:
                        self.query_type.setCurrentIndex(idx)
                self.ignore_search_type_changes = False
            self.find_next()

    def search_query(self, backwards=False):
        text = self.search_box.currentText()
        if text:
            return Search(
                text, self.query_type.currentData() or 'normal',
                self.case_sensitive.isChecked(), backwards
            )

    def emit_search(self, backwards=False):
        vprefs['viewer-search-case-sensitive'] = self.case_sensitive.isChecked()
        vprefs['viewer-search-mode'] = self.query_type.currentData()
        sq = self.search_query(backwards)
        if sq is not None:
            self.do_search.emit(sq)

    def find_next(self):
        self.emit_search()

    def find_previous(self):
        self.emit_search(backwards=True)

    def focus_input(self):
        self.search_box.setFocus(Qt.OtherFocusReason)
        le = self.search_box.lineEdit()
        le.end(False)
        le.selectAll()
# }}}


class ResultsDelegate(QStyledItemDelegate):  # {{{

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, index)
        result = index.data(Qt.UserRole)
        painter.save()
        p = option.palette
        c = p.HighlightedText if option.state & QStyle.State_Selected else p.Text
        group = (p.Active if option.state & QStyle.State_Active else p.Inactive)
        c = p.color(group, c)
        painter.setClipRect(option.rect)
        painter.setPen(c)
        height = result.static_text.size().height()
        tl = option.rect.topLeft()
        x, y = tl.x(), tl.y()
        y += (option.rect.height() - height) // 2
        if result.is_hidden:
            x += option.decorationSize.width() + 4
        try:
            painter.drawStaticText(x, y, result.static_text)
        except Exception:
            import traceback
            traceback.print_exc()
        painter.restore()
# }}}


class Results(QListWidget):  # {{{

    show_search_result = pyqtSignal(object)

    def __init__(self, parent=None):
        QListWidget.__init__(self, parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.delegate = ResultsDelegate(self)
        self.setItemDelegate(self.delegate)
        self.itemClicked.connect(self.item_activated)
        self.blank_icon = QIcon(I('blank.png'))

    def add_result(self, result):
        i = QListWidgetItem(' ', self)
        i.setData(Qt.UserRole, result)
        i.setIcon(self.blank_icon)
        return self.count()

    def item_activated(self):
        i = self.currentItem()
        if i:
            sr = i.data(Qt.UserRole)
            if not sr.is_hidden:
                self.show_search_result.emit(sr)

    def find_next(self, previous):
        if self.count() < 1:
            return
        i = self.currentRow()
        i += -1 if previous else 1
        i %= self.count()
        self.setCurrentRow(i)
        self.item_activated()

    def search_result_not_found(self, sr):
        for i in range(self.count()):
            item = self.item(i)
            r = item.data(Qt.UserRole)
            if r.is_result(sr):
                r.is_hidden = True
                item.setIcon(QIcon(I('dialog_warning.png')))
                break

    @property
    def current_result_is_hidden(self):
        item = self.currentItem()
        if item and item.data(Qt.UserRole) and item.data(Qt.UserRole).is_hidden:
            return True
        return False
# }}}


class SearchPanel(QWidget):  # {{{

    search_requested = pyqtSignal(object)
    results_found = pyqtSignal(object)
    show_search_result = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.last_hidden_text_warning = None
        self.current_search = None
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.search_input = si = SearchInput(self)
        self.searcher = None
        self.search_tasks = Queue()
        self.results_found.connect(self.on_result_found, type=Qt.QueuedConnection)
        si.do_search.connect(self.search_requested)
        l.addWidget(si)
        self.results = r = Results(self)
        r.show_search_result.connect(self.do_show_search_result, type=Qt.QueuedConnection)
        r.currentRowChanged.connect(self.update_hidden_message)
        l.addWidget(r, 100)
        self.spinner = s = BusySpinner(self)
        s.setVisible(False)
        l.addWidget(s)
        self.hidden_message = la = QLabel(_('This text is hidden in the book and cannot be displayed'))
        la.setStyleSheet('QLabel { margin-left: 1ex }')
        la.setWordWrap(True)
        la.setVisible(False)
        l.addWidget(la)

    def update_hidden_message(self):
        self.hidden_message.setVisible(self.results.current_result_is_hidden)

    def focus_input(self):
        self.search_input.focus_input()

    def start_search(self, search_query, current_name):
        if self.current_search is not None and search_query == self.current_search:
            self.find_next_requested(search_query.backwards)
            return
        if self.searcher is None:
            self.searcher = Thread(name='Searcher', target=self.run_searches)
            self.searcher.daemon = True
            self.searcher.start()
        self.results.clear()
        self.hidden_message.setVisible(False)
        self.spinner.start()
        self.current_search = search_query
        self.last_hidden_text_warning = None
        self.search_tasks.put((search_query, current_name))

    def run_searches(self):
        while True:
            x = self.search_tasks.get()
            if x is None:
                break
            search_query, current_name = x
            try:
                manifest = get_manifest() or {}
                spine = manifest.get('spine', ())
                idx_map = {name: i for i, name in enumerate(spine)}
                spine_idx = idx_map.get(current_name, -1)
            except Exception:
                import traceback
                traceback.print_exc()
                spine_idx = -1
            if spine_idx < 0:
                self.results_found.emit(SearchFinished(search_query))
                continue
            for name in spine:
                counter = Counter()
                spine_idx = idx_map[name]
                try:
                    for i, result in enumerate(search_in_name(name, search_query)):
                        before, text, after = result
                        q = (before or '')[-5:] + text + (after or '')[:5]
                        self.results_found.emit(SearchResult(search_query, before, text, after, q, name, spine_idx, counter[q]))
                        counter[q] += 1
                except Exception:
                    import traceback
                    traceback.print_exc()
            self.results_found.emit(SearchFinished(search_query))

    def on_result_found(self, result):
        if self.current_search is None or result.search_query != self.current_search:
            return
        if isinstance(result, SearchFinished):
            self.spinner.stop()
            if not self.results.count():
                self.show_no_results_found()
            return
        if self.results.add_result(result) == 1:
            # first result
            self.results.setCurrentRow(0)
            self.results.item_activated()
        self.update_hidden_message()

    def visibility_changed(self, visible):
        if visible:
            self.focus_input()

    def clear_searches(self):
        self.current_search = None
        self.last_hidden_text_warning = None
        searchable_text_for_name.cache_clear()
        self.spinner.stop()
        self.results.clear()

    def shutdown(self):
        self.search_tasks.put(None)
        self.spinner.stop()
        self.current_search = None
        self.last_hidden_text_warning = None
        self.searcher = None

    def find_next_requested(self, previous):
        self.results.find_next(previous)

    def do_show_search_result(self, sr):
        self.show_search_result.emit(sr.for_js)

    def search_result_not_found(self, sr):
        self.results.search_result_not_found(sr)
        self.update_hidden_message()

    def show_no_results_found(self):
        msg = _('No matches were found for:')
        warning_dialog(self, _('No matches found'), msg + '  <b>{}</b>'.format(self.current_search.text), show=True)
# }}}
