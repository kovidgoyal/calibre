#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import textwrap
from collections import Counter
from threading import Thread

import regex
from PyQt5.Qt import (
    QCheckBox, QComboBox, QHBoxLayout, QIcon, QLabel, QListWidget, Qt, QToolButton,
    QVBoxLayout, QWidget, pyqtSignal
)

from calibre.ebooks.conversion.search_replace import REGEX_FLAGS
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.viewer.web_view import get_data, get_manifest, vprefs
from calibre.gui2.widgets2 import HistoryComboBox
from polyglot.builtins import iteritems, unicode_type
from polyglot.functools import lru_cache
from polyglot.queue import Queue


class BusySpinner(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.pi = ProgressIndicator(self, 24)
        l.addWidget(self.pi)
        self.la = la = QLabel(_('Searching...'))
        l.addWidget(la)
        l.addStretch(10)

    def start(self):
        self.setVisible(True)
        self.pi.start()

    def stop(self):
        self.setVisible(False)
        self.pi.stop()


class Search(object):

    def __init__(self, text, mode, case_sensitive, backwards):
        self.text, self.mode = text, mode
        self.case_sensitive = case_sensitive
        self.backwards = backwards
        self._regex = None

    def __eq__(self, other):
        return self.text == other.text and self.mode == other.mode and self.case_sensitive == other.case_sensitive

    @property
    def regex(self):
        if self._regex is None:
            expr = self.text
            flags = REGEX_FLAGS
            if not self.case_sensitive:
                flags = regex.IGNORECASE
            if self.mode != 'regex':
                expr = regex.escape(expr)
            self._regex = regex.compile(expr, flags)
        return self._regex


class SearchFinished(object):

    def __init__(self, search_query):
        self.search_query = search_query


class SearchResult(object):

    __slots__ = ('search_query', 'before', 'text', 'after', 'spine_idx', 'index', 'file_name')

    def __init__(self, search_query, before, text, after, name, spine_idx, index):
        self.search_query = search_query
        self.before, self.text, self.after = before, text, after
        self.spine_idx, self.index = spine_idx, index
        self.file_name = name


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
        before = raw[start-ctx_size:start]
        after = raw[end:end+ctx_size]
        yield before, match.group(), after


class SearchBox(HistoryComboBox):

    history_saved = pyqtSignal(object, object)

    def save_history(self):
        ret = HistoryComboBox.save_history(self)
        self.history_saved.emit(self.text(), self.history)
        return ret


class SearchInput(QWidget):  # {{{

    do_search = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
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
        qt.addItem(_('Normal'), 'normal')
        qt.addItem(_('Regex'), 'regex')
        qt.setToolTip(textwrap.fill(_('Choose the type of search: Normal will search'
            ' for the entered text, Regex will interpret the text as a'
            ' regular expression')))
        qt.setCurrentIndex(qt.findData(vprefs.get('viewer-search-mode', 'normal') or 'normal'))
        h.addWidget(qt)

        self.case_sensitive = cs = QCheckBox(_('Case sensitive'), self)
        cs.setFocusPolicy(Qt.NoFocus)
        cs.setChecked(bool(vprefs.get('viewer-search-case-sensitive', False)))
        h.addWidget(cs)

    def history_saved(self, new_text, history):
        if new_text:
            sss = vprefs.get('saved-search-settings') or {}
            sss[new_text] = {'case_sensitive': self.case_sensitive.isChecked(), 'mode': self.query_type.currentData()}
            history = frozenset(history)
            sss = {k: v for k, v in iteritems(sss) if k in history}
            vprefs['saved-search-settings'] = sss

    def saved_search_selected(self):
        text = self.search_box.currentText().strip()
        if text:
            s = (vprefs.get('saved-search-settings') or {}).get(text)
            if s:
                if 'case_sensitive' in s:
                    self.case_sensitive.setChecked(s['case_sensitive'])
                if 'mode' in s:
                    idx = self.query_type.findData(s['mode'])
                    if idx > -1:
                        self.query_type.setCurrentIndex(idx)

    def search_query(self, backwards=False):
        text = self.search_box.currentText().strip()
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


class Results(QListWidget):

    def __init__(self, parent=None):
        QListWidget.__init__(self, parent)
        self.setFocusPolicy(Qt.NoFocus)


class SearchPanel(QWidget):

    search_requested = pyqtSignal(object)
    results_found = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.current_search = None
        self.l = l = QVBoxLayout(self)
        self.search_input = si = SearchInput(self)
        self.searcher = None
        self.search_tasks = Queue()
        self.results_found.connect(self.on_result_found, type=Qt.QueuedConnection)
        si.do_search.connect(self.search_requested)
        l.addWidget(si)
        self.results = r = Results(self)
        l.addWidget(r, 100)
        self.spinner = s = BusySpinner(self)
        s.setVisible(False)
        l.addWidget(s)

    def focus_input(self):
        self.search_input.focus_input()

    def start_search(self, search_query, current_name):
        if self.current_search is not None and search_query == self.current_search:
            # TODO: go to next or previous result as required
            return
        if self.searcher is None:
            self.searcher = Thread(name='Searcher', target=self.run_searches)
            self.searcher.daemon = True
            self.searcher.start()
        # TODO: Clear the current search results
        self.spinner.start()
        self.current_search = search_query
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
            names = spine[spine_idx:] + spine[:spine_idx]
            for name in names:
                counter = Counter()
                spine_idx = idx_map[name]
                try:
                    for i, result in enumerate(search_in_name(name, search_query)):
                        before, text, after = result
                        counter[text] += 1
                        self.results_found.emit(SearchResult(search_query, before, text, after, name, spine_idx, counter[text]))
                except Exception:
                    import traceback
                    traceback.print_exc()
            self.results_found.emit(SearchFinished(search_query))

    def on_result_found(self, result):
        if self.current_search is None or result.search_query != self.current_search:
            return
        if isinstance(result, SearchFinished):
            self.spinner.stop()
            return

    def clear_searches(self):
        self.current_search = None
        searchable_text_for_name.cache_clear()
        self.spinner.stop()
        self.results.clear()

    def shutdown(self):
        self.search_tasks.put(None)
        self.spinner.stop()
        self.current_search = None
        self.searcher = None
