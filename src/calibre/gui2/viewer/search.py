#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import json
import regex
from collections import Counter, OrderedDict
from html import escape
from qt.core import (
    QAbstractItemView, QCheckBox, QComboBox, QFont, QHBoxLayout, QIcon, QLabel, Qt,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, pyqtSignal
)
from threading import Thread

from calibre.ebooks.conversion.search_replace import REGEX_FLAGS
from calibre.gui2 import warning_dialog
from calibre.gui2.gestures import GestureManager
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.viewer.config import vprefs
from calibre.gui2.viewer.web_view import get_data, get_manifest
from calibre.gui2.viewer.widgets import ResultsDelegate, SearchBox
from calibre.utils.icu import primary_collator_without_punctuation
from polyglot.builtins import iteritems
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
invisible_chars = '(?:[\u00ad\u200c\u200d]{0,1})'
SEARCH_RESULT_ROLE = Qt.ItemDataRole.UserRole
RESULT_NUMBER_ROLE = SEARCH_RESULT_ROLE + 1
SPINE_IDX_ROLE = RESULT_NUMBER_ROLE + 1


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
                    part = invisible_chars.join(map(regex.escape, part))
                    ans.append(part)
    if has_leading:
        ans.insert(0, r'\s+')
    if has_trailing:
        ans.append(r'\s+')
    return ''.join(ans)


class Search:

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
                        words.append(fr'\b{text_to_regex(part)}\b')
                    expr = r'\s+'.join(words)
                else:
                    expr = text_to_regex(expr)
            self._regex = regex.compile(expr, flags)
        return self._regex

    def __str__(self):
        from collections import namedtuple
        s = ('text', 'mode', 'case_sensitive', 'backwards')
        return str(namedtuple('Search', s)(*tuple(getattr(self, x) for x in s)))


class SearchFinished:

    def __init__(self, search_query):
        self.search_query = search_query


class SearchResult:

    __slots__ = (
        'search_query', 'before', 'text', 'after', 'q', 'spine_idx',
        'index', 'file_name', 'is_hidden', 'offset', 'toc_nodes',
        'result_num'
    )

    def __init__(self, search_query, before, text, after, q, name, spine_idx, index, offset, result_num):
        self.search_query = search_query
        self.q = q
        self.result_num = result_num
        self.before, self.text, self.after = before, text, after
        self.spine_idx, self.index = spine_idx, index
        self.file_name = name
        self.is_hidden = False
        self.offset = offset
        try:
            self.toc_nodes = toc_nodes_for_search_result(self)
        except Exception:
            import traceback
            traceback.print_exc()
            self.toc_nodes = ()

    @property
    def for_js(self):
        return {
            'file_name': self.file_name, 'spine_idx': self.spine_idx, 'index': self.index, 'text': self.text,
            'before': self.before, 'after': self.after, 'mode': self.search_query.mode, 'q': self.q,
            'result_num': self.result_num
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
    removed_tails = []
    for child in serialized_data['tree']['c']:
        if child.get('n') == 'body':
            stack.append(child)
            # the JS code does not add the tail of body tags to flat text
            removed_tails.append((child.pop('l', None), child))
    ignore_text = {'script', 'style', 'title'}
    text_pos = 0
    anchor_offset_map = OrderedDict()
    while stack:
        node = stack.pop()
        if isinstance(node, str):
            ans.append(node)
            text_pos += len(node)
            continue
        g = node.get
        name = g('n')
        text = g('x')
        tail = g('l')
        children = g('c')
        attributes = g('a')
        if attributes:
            for x in attributes:
                if x[0] == 'id':
                    aid = x[1]
                    if aid not in anchor_offset_map:
                        anchor_offset_map[aid] = text_pos
        if name and text and name not in ignore_text:
            ans.append(text)
            text_pos += len(text)
        if tail:
            stack.append(tail)
        if children:
            stack.extend(reversed(children))
    for (tail, body) in removed_tails:
        if tail is not None:
            body['l'] = tail
    return ''.join(ans), anchor_offset_map


@lru_cache(maxsize=2)
def get_toc_data():
    manifest = get_manifest() or {}
    spine = manifest.get('spine') or []
    spine_toc_map = {name: [] for name in spine}
    parent_map = {}

    def process_node(node):
        items = spine_toc_map.get(node['dest'])
        if items is not None:
            items.append(node)
        children = node.get('children')
        if children:
            for child in children:
                parent_map[id(child)] = node
                process_node(child)

    toc = manifest.get('toc')
    if toc:
        process_node(toc)
    return {
        'spine': tuple(spine), 'spine_toc_map': spine_toc_map,
        'spine_idx_map': {name: idx for idx, name in enumerate(spine)},
        'parent_map': parent_map
    }


class ToCOffsetMap:

    def __init__(self, toc_nodes=(), offset_map=None, previous_toc_node=None, parent_map=None):
        self.toc_nodes = toc_nodes
        self.offset_map = offset_map or {}
        self.previous_toc_node = previous_toc_node
        self.parent_map = parent_map or {}

    def toc_nodes_for_offset(self, offset):
        matches = []
        for node in self.toc_nodes:
            q = self.offset_map.get(node.get('id'))
            if q is not None:
                if q > offset:
                    break
                matches.append(node)
        if not matches and self.previous_toc_node is not None:
            matches.append(self.previous_toc_node)
        if matches:
            ancestors = []
            node = matches[-1]
            parent = self.parent_map.get(id(node))
            while parent is not None:
                ancestors.append(parent)
                parent = self.parent_map.get(id(parent))
            if len(ancestors) > 1:
                ancestors.pop()  # root node
                yield from reversed(ancestors)
            yield node


@lru_cache(maxsize=None)
def toc_offset_map_for_name(name):
    anchor_map = searchable_text_for_name(name)[1]
    toc_data = get_toc_data()
    try:
        idx = toc_data['spine_idx_map'][name]
        toc_nodes = toc_data['spine_toc_map'][name]
    except Exception:
        idx = -1
    if idx < 0:
        return ToCOffsetMap()
    offset_map = {}
    for node in toc_nodes:
        node_id = node.get('id')
        if node_id is not None:
            aid = node.get('frag')
            offset = anchor_map.get(aid, 0)
            offset_map[node_id] = offset
    prev_toc_node = None
    for spine_name in reversed(toc_data['spine'][:idx]):
        try:
            ptn = toc_data['spine_toc_map'][spine_name]
        except Exception:
            continue
        if ptn:
            prev_toc_node = ptn[-1]
            break
    return ToCOffsetMap(toc_nodes, offset_map, prev_toc_node, toc_data['parent_map'])


def toc_nodes_for_search_result(sr):
    sidx = sr.spine_idx
    toc_data = get_toc_data()
    try:
        name = toc_data['spine'][sidx]
    except Exception:
        return ()
    tmap = toc_offset_map_for_name(name)
    return tuple(tmap.toc_nodes_for_offset(sr.offset))


def search_in_name(name, search_query, ctx_size=75):
    raw = searchable_text_for_name(name)[0]

    if search_query.mode == 'regex' or search_query.case_sensitive:
        def miter():
            for match in search_query.regex.finditer(raw):
                yield match.span()
    else:
        spans = []
        a = lambda s, l: spans.append((s, s + l))
        primary_collator_without_punctuation().find_all(search_query.text, raw, a, search_query.mode == 'word')
        miter = lambda: spans

    for (start, end) in miter():
        before = raw[max(0, start-ctx_size):start]
        after = raw[end:end+ctx_size]
        yield before, raw[start:end], after, start


class SearchInput(QWidget):  # {{{

    do_search = pyqtSignal(object)
    cleared = pyqtSignal()
    go_back = pyqtSignal()

    def __init__(self, parent=None, panel_name='search'):
        QWidget.__init__(self, parent)
        self.ignore_search_type_changes = False
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)

        self.search_box = sb = SearchBox(self)
        self.panel_name = panel_name
        sb.initialize(f'viewer-{panel_name}-panel-expression')
        sb.item_selected.connect(self.saved_search_selected)
        sb.history_saved.connect(self.history_saved)
        sb.history_cleared.connect(self.history_cleared)
        sb.cleared.connect(self.cleared)
        sb.lineEdit().returnPressed.connect(self.find_next)
        h.addWidget(sb)

        self.next_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        nb.setIcon(QIcon.ic('arrow-down.png'))
        nb.clicked.connect(self.find_next)
        nb.setToolTip(_('Find next match'))

        self.prev_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        nb.setIcon(QIcon.ic('arrow-up.png'))
        nb.clicked.connect(self.find_previous)
        nb.setToolTip(_('Find previous match'))

        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)
        self.query_type = qt = QComboBox(self)
        qt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        qt.addItem(_('Contains'), 'normal')
        qt.addItem(_('Whole words'), 'word')
        qt.addItem(_('Regex'), 'regex')
        qt.setToolTip('<p>' + _(
            'Choose the type of search: <ul>'
            '<li><b>Contains</b> will search for the entered text anywhere. It will ignore punctuation,'
            ' spaces and accents, unless Case sensitive searching is enabled.'
            '<li><b>Whole words</b> will search for whole words that equal the entered text. As with'
            ' "Contains" searches punctuation and accents are ignored.'
            '<li><b>Regex</b> will interpret the text as a regular expression.'
        ))
        qt.setCurrentIndex(qt.findData(vprefs.get(f'viewer-{self.panel_name}-mode', 'normal') or 'normal'))
        qt.currentIndexChanged.connect(self.save_search_type)
        h.addWidget(qt)

        self.case_sensitive = cs = QCheckBox(_('&Case sensitive'), self)
        cs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cs.setChecked(bool(vprefs.get(f'viewer-{self.panel_name}-case-sensitive', False)))
        cs.stateChanged.connect(self.save_search_type)
        h.addWidget(cs)

        self.return_button = rb = QToolButton(self)
        rb.setIcon(QIcon.ic('back.png'))
        rb.setToolTip(_('Go back to where you were before searching'))
        rb.clicked.connect(self.go_back)
        h.addWidget(rb)

    def history_saved(self, new_text, history):
        if new_text:
            sss = vprefs.get(f'saved-{self.panel_name}-settings') or {}
            sss[new_text] = {'case_sensitive': self.case_sensitive.isChecked(), 'mode': self.query_type.currentData()}
            history = frozenset(history)
            sss = {k: v for k, v in iteritems(sss) if k in history}
            vprefs[f'saved-{self.panel_name}-settings'] = sss

    def history_cleared(self):
        vprefs[f'saved-{self.panel_name}-settings'] = {}

    def save_search_type(self):
        text = self.search_box.currentText()
        if text and not self.ignore_search_type_changes:
            sss = vprefs.get(f'saved-{self.panel_name}-settings') or {}
            sss[text] = {'case_sensitive': self.case_sensitive.isChecked(), 'mode': self.query_type.currentData()}
            vprefs[f'saved-{self.panel_name}-settings'] = sss

    def saved_search_selected(self):
        text = self.search_box.currentText()
        if text:
            s = (vprefs.get(f'saved-{self.panel_name}-settings') or {}).get(text)
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
        vprefs[f'viewer-{self.panel_name}-case-sensitive'] = self.case_sensitive.isChecked()
        vprefs[f'viewer-{self.panel_name}-mode'] = self.query_type.currentData()
        sq = self.search_query(backwards)
        if sq is not None:
            self.do_search.emit(sq)

    def find_next(self):
        self.emit_search()

    def find_previous(self):
        self.emit_search(backwards=True)

    def focus_input(self, text=None):
        if text and hasattr(text, 'rstrip'):
            self.search_box.setText(text)
        self.search_box.setFocus(Qt.FocusReason.OtherFocusReason)
        le = self.search_box.lineEdit()
        le.end(False)
        le.selectAll()
# }}}


class Results(QTreeWidget):  # {{{

    show_search_result = pyqtSignal(object)
    current_result_changed = pyqtSignal(object)
    count_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        QTreeWidget.__init__(self, parent)
        self.setHeaderHidden(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delegate = ResultsDelegate(self)
        self.setItemDelegate(self.delegate)
        self.itemClicked.connect(self.item_activated)
        self.blank_icon = QIcon.ic('blank.png')
        self.not_found_icon = QIcon.ic('dialog_warning.png')
        self.currentItemChanged.connect(self.current_item_changed)
        self.section_font = QFont(self.font())
        self.section_font.setItalic(True)
        self.section_map = {}
        self.search_results = []
        self.item_map = {}
        self.gesture_manager = GestureManager(self)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def viewportEvent(self, ev):
        try:
            ret = self.gesture_manager.handle_event(ev)
        except AttributeError:
            ret = None
        if ret is not None:
            return ret
        return super().viewportEvent(ev)

    def current_item_changed(self, current, previous):
        if current is not None:
            r = current.data(0, SEARCH_RESULT_ROLE)
            if isinstance(r, SearchResult):
                self.current_result_changed.emit(r)
        else:
            self.current_result_changed.emit(None)

    def add_result(self, result):
        section_title = _('Unknown')
        section_id = -1
        toc_nodes = getattr(result, 'toc_nodes', ()) or ()
        if toc_nodes:
            section_title = toc_nodes[-1].get('title') or _('Unknown')
            section_id = toc_nodes[-1].get('id')
            if section_id is None:
                section_id = -1
        section_key = section_id
        section = self.section_map.get(section_key)
        spine_idx = getattr(result, 'spine_idx', -1)
        if section is None:
            section = QTreeWidgetItem([section_title], 1)
            section.setFlags(Qt.ItemFlag.ItemIsEnabled)
            section.setFont(0, self.section_font)
            section.setData(0, SPINE_IDX_ROLE, spine_idx)
            lines = []
            for i, node in enumerate(toc_nodes):
                lines.append('\xa0\xa0' * i + '➤ ' + (node.get('title') or _('Unknown')))
            if lines:
                tt = ngettext('Table of Contents section:', 'Table of Contents sections:', len(lines))
                tt += '\n' + '\n'.join(lines)
                section.setToolTip(0, tt)
            self.section_map[section_key] = section
            for s in range(self.topLevelItemCount()):
                ti = self.topLevelItem(s)
                if ti.data(0, SPINE_IDX_ROLE) > spine_idx:
                    self.insertTopLevelItem(s, section)
                    break
            else:
                self.addTopLevelItem(section)
            section.setExpanded(True)
        item = QTreeWidgetItem(section, [' '], 2)
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemNeverHasChildren)
        item.setData(0, SEARCH_RESULT_ROLE, result)
        item.setData(0, RESULT_NUMBER_ROLE, len(self.search_results))
        item.setData(0, SPINE_IDX_ROLE, spine_idx)
        if isinstance(result, SearchResult):
            tt = '<p>…' + escape(result.before, False) + '<b>' + escape(
                result.text, False) + '</b>' + escape(result.after, False) + '…'
            item.setData(0, Qt.ItemDataRole.ToolTipRole, tt)
        item.setIcon(0, self.blank_icon)
        self.item_map[len(self.search_results)] = item
        self.search_results.append(result)
        n = self.number_of_results
        self.count_changed.emit(n)

    def item_activated(self):
        i = self.currentItem()
        if i:
            sr = i.data(0, SEARCH_RESULT_ROLE)
            if isinstance(sr, SearchResult):
                if not sr.is_hidden:
                    self.show_search_result.emit(sr)

    def find_next(self, previous):
        if self.number_of_results < 1:
            return
        item = self.currentItem()
        if item is None:
            return
        i = int(item.data(0, RESULT_NUMBER_ROLE))
        i += -1 if previous else 1
        i %= self.number_of_results
        self.setCurrentItem(self.item_map[i])
        self.item_activated()

    def search_result_not_found(self, sr):
        for i in range(self.number_of_results):
            item = self.item_map[i]
            r = item.data(0, SEARCH_RESULT_ROLE)
            if r.is_result(sr):
                r.is_hidden = True
                item.setIcon(0, self.not_found_icon)
                break

    def search_result_discovered(self, sr):
        q = sr['result_num']
        for i in range(self.number_of_results):
            item = self.item_map[i]
            r = item.data(0, SEARCH_RESULT_ROLE)
            if r.result_num == q:
                self.setCurrentItem(item)

    @property
    def current_result_is_hidden(self):
        item = self.currentItem()
        if item is not None:
            sr = item.data(0, SEARCH_RESULT_ROLE)
            if isinstance(sr, SearchResult) and sr.is_hidden:
                return True
        return False

    @property
    def number_of_results(self):
        return len(self.search_results)

    def clear_all_results(self):
        self.section_map = {}
        self.item_map = {}
        self.search_results = []
        self.clear()
        self.count_changed.emit(-1)

    def select_first_result(self):
        if self.number_of_results:
            item = self.item_map[0]
            self.setCurrentItem(item)

    def ensure_current_result_visible(self):
        item = self.currentItem()
        if item is not None:
            self.scrollToItem(item)
# }}}


class SearchPanel(QWidget):  # {{{

    search_requested = pyqtSignal(object)
    results_found = pyqtSignal(object)
    show_search_result = pyqtSignal(object)
    count_changed = pyqtSignal(object)
    hide_search_panel = pyqtSignal()
    goto_cfi = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.discovery_counter = 0
        self.last_hidden_text_warning = None
        self.current_search = None
        self.anchor_cfi = None
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.search_input = si = SearchInput(self)
        self.searcher = None
        self.search_tasks = Queue()
        self.results_found.connect(self.on_result_found, type=Qt.ConnectionType.QueuedConnection)
        si.do_search.connect(self.search_requested)
        si.cleared.connect(self.search_cleared)
        si.go_back.connect(self.go_back)
        l.addWidget(si)
        self.results = r = Results(self)
        r.count_changed.connect(self.count_changed)
        r.show_search_result.connect(self.do_show_search_result, type=Qt.ConnectionType.QueuedConnection)
        r.current_result_changed.connect(self.update_hidden_message)
        l.addWidget(r, 100)
        self.spinner = s = BusySpinner(self)
        s.setVisible(False)
        l.addWidget(s)
        self.hidden_message = la = QLabel(_('This text is hidden in the book and cannot be displayed'))
        la.setStyleSheet('QLabel { margin-left: 1ex }')
        la.setWordWrap(True)
        la.setVisible(False)
        l.addWidget(la)

    def go_back(self):
        if self.anchor_cfi:
            self.goto_cfi.emit(self.anchor_cfi)

    def update_hidden_message(self):
        self.hidden_message.setVisible(self.results.current_result_is_hidden)

    def focus_input(self, text=None):
        self.search_input.focus_input(text)

    def search_cleared(self):
        self.results.clear_all_results()
        self.current_search = None

    def start_search(self, search_query, current_name):
        if self.current_search is not None and search_query == self.current_search:
            self.find_next_requested(search_query.backwards)
            return
        if self.searcher is None:
            self.searcher = Thread(name='Searcher', target=self.run_searches)
            self.searcher.daemon = True
            self.searcher.start()
        self.results.clear_all_results()
        self.hidden_message.setVisible(False)
        self.spinner.start()
        self.current_search = search_query
        self.last_hidden_text_warning = None
        self.search_tasks.put((search_query, current_name))
        self.discovery_counter += 1

    def set_anchor_cfi(self, pos_data):
        self.anchor_cfi = pos_data['cfi']

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
            num_in_spine = len(spine)
            result_num = 0
            for n in range(num_in_spine):
                idx = (spine_idx + n) % num_in_spine
                name = spine[idx]
                counter = Counter()
                try:
                    for i, result in enumerate(search_in_name(name, search_query)):
                        before, text, after, offset = result
                        q = (before or '')[-15:] + text + (after or '')[:15]
                        result_num += 1
                        self.results_found.emit(SearchResult(search_query, before, text, after, q, name, idx, counter[q], offset, result_num))
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
            if self.results.number_of_results:
                self.results.ensure_current_result_visible()
            else:
                self.show_no_results_found()
            return
        self.results.add_result(result)
        obj = result.for_js
        obj['on_discovery'] = self.discovery_counter
        self.show_search_result.emit(obj)
        self.update_hidden_message()

    def visibility_changed(self, visible):
        if visible:
            self.focus_input()

    def clear_searches(self):
        self.current_search = None
        self.last_hidden_text_warning = None
        searchable_text_for_name.cache_clear()
        toc_offset_map_for_name.cache_clear()
        get_toc_data.cache_clear()
        self.spinner.stop()
        self.results.clear_all_results()

    def shutdown(self):
        self.search_tasks.put(None)
        self.spinner.stop()
        self.current_search = None
        self.last_hidden_text_warning = None
        self.searcher = None

    def find_next_requested(self, previous):
        self.results.find_next(previous)

    def trigger(self):
        self.search_input.find_next()

    def do_show_search_result(self, sr):
        self.show_search_result.emit(sr.for_js)

    def search_result_not_found(self, sr):
        self.results.search_result_not_found(sr)
        self.update_hidden_message()

    def search_result_discovered(self, sr):
        self.results.search_result_discovered(sr)

    def show_no_results_found(self):
        msg = _('No matches were found for:')
        warning_dialog(self, _('No matches found'), msg + f'  <b>{self.current_search.text}</b>', show=True)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.hide_search_panel.emit()
            ev.accept()
            return
        return QWidget.keyPressEvent(self, ev)
# }}}
