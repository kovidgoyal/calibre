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
    QCheckBox, QComboBox, QHBoxLayout, QIcon, Qt, QToolButton, QVBoxLayout, QWidget,
    pyqtSignal
)

from calibre.ebooks.conversion.search_replace import REGEX_FLAGS
from calibre.gui2.viewer.web_view import get_data, get_manifest, vprefs
from calibre.gui2.widgets2 import HistoryComboBox
from polyglot.builtins import unicode_type
from polyglot.functools import lru_cache
from polyglot.queue import Queue


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
        self.spine_idx, self.index = self.spine_idx, index
        self.file_name = name


@lru_cache(maxsize=1024)
def searchable_text_for_name(name):
    ans = []
    serialized_data = json.loads(get_data(name)[0])
    stack = []
    for child in serialized_data['tree']['c']:
        if child.get('n') == 'body':
            stack.append(child)
    ignore_text = {'script':True, 'style':True, 'title': True}
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
        if name and not ignore_text[name] and text:
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


class SearchInput(QWidget):

    do_search = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)

        self.search_box = sb = HistoryComboBox(self)
        sb.lineEdit().setPlaceholderText(_('Search'))
        sb.lineEdit().setClearButtonEnabled(True)
        sb.lineEdit().returnPressed.connect(self.find_next)
        sb.initialize('viewer-search-box-history')
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

    def search_query(self, backwards=False):
        text = self.search_box.currentText().strip()
        if text:
            return Search(text, self.query_type.currentData() or 'normal', self.case_sensitive.isChecked(), backwards)

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
        l.addStretch(10)

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
        # TODO: Clear the current search results, and start spinner
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
                    pass
            self.results_found.emit(SearchFinished(search_query))

    def on_result_found(self, result):
        if self.current_search is None or result.search_query != self.current_search:
            return
        if isinstance(result, SearchFinished):
            # TODO: Hide spinner
            return

    def clear_searches(self):
        self.current_search = None
        searchable_text_for_name.cache_clear()
        # TODO: clear the results list and hide the searching spinner

    def shutdown(self):
        self.search_tasks.put(None)
        self.searcher = None
