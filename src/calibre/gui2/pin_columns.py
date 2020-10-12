#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


from PyQt5.Qt import QSplitter, QTableView

from calibre.gui2.library import DEFAULT_SORT
from calibre.gui2 import gprefs
from polyglot.builtins import range


class PinTableView(QTableView):

    def __init__(self, books_view, parent=None):
        QTableView.__init__(self, parent)
        self.books_view = books_view
        self.verticalHeader().close()
        self.splitter = None
        self.disable_save_state = False

    @property
    def column_map(self):
        return self.books_view.column_map

    def set_context_menu(self, menu):
        self.context_menu = menu

    def contextMenuEvent(self, event):
        self.books_view.show_context_menu(self.context_menu, event)

    def get_default_state(self):
        old_state = {
            'hidden_columns': ['last_modified', 'languages'],
            'sort_history':[DEFAULT_SORT],
            'column_positions': {},
            'column_sizes': {},
        }
        h = self.column_header
        cm = self.column_map
        for i in range(h.count()):
            name = cm[i]
            old_state['column_positions'][name] = i
            if name != 'ondevice':
                old_state['column_sizes'][name] = \
                    min(350, max(self.sizeHintForColumn(i),
                        h.sectionSizeHint(i)))
                if name in ('timestamp', 'last_modified'):
                    old_state['column_sizes'][name] += 12
        return old_state

    def apply_state(self, state):
        self.disable_save_state = True  # moveSection() can cause save_state() to be called
        h = self.column_header
        cmap = {}
        hidden = state.get('hidden_columns', [])
        for i, c in enumerate(self.column_map):
            cmap[c] = i
            if c != 'ondevice':
                h.setSectionHidden(i, c in hidden)

        positions = state.get('column_positions', {})
        pmap = {}
        for col, pos in positions.items():
            if col in cmap:
                pmap[pos] = col
        for pos in sorted(pmap.keys()):
            col = pmap[pos]
            idx = cmap[col]
            current_pos = h.visualIndex(idx)
            if current_pos != pos:
                h.moveSection(current_pos, pos)

        # Because of a bug in Qt 5 we have to ensure that the header is actually
        # relaid out by changing this value, without this sometimes ghost
        # columns remain visible when changing libraries
        for i in range(h.count()):
            val = h.isSectionHidden(i)
            h.setSectionHidden(i, not val)
            h.setSectionHidden(i, val)

        sizes = state.get('column_sizes', {})
        for col, size in sizes.items():
            if col in cmap:
                sz = sizes[col]
                if sz < 3:
                    sz = h.sectionSizeHint(cmap[col])
                h.resizeSection(cmap[col], sz)

        for i in range(h.count()):
            if not h.isSectionHidden(i) and h.sectionSize(i) < 3:
                sz = h.sectionSizeHint(i)
                h.resizeSection(i, sz)
        self.disable_save_state = False

    def get_state(self):
        h = self.column_header
        cm = self.column_map
        state = {}
        state['hidden_columns'] = [cm[i] for i in range(h.count())
                if h.isSectionHidden(i) and cm[i] != 'ondevice']
        state['column_positions'] = {}
        state['column_sizes'] = {}
        for i in range(h.count()):
            name = cm[i]
            state['column_positions'][name] = h.visualIndex(i)
            if name != 'ondevice':
                state['column_sizes'][name] = h.sectionSize(i)
        return state

    def save_state(self):
        db = getattr(self.model(), 'db', None)
        if db is not None and not self.disable_save_state:
            state = self.get_state()
            db.new_api.set_pref('books view split pane state', state)
            if self.splitter is not None:
                self.splitter.save_state()

    def restore_state(self):
        db = getattr(self.model(), 'db', None)
        if db is not None:
            state = db.new_api.pref('books view split pane state', None)
            if self.splitter is not None:
                self.splitter.restore_state()
            if state:
                self.apply_state(state)


class PinContainer(QSplitter):

    def __init__(self, books_view, parent=None):
        QSplitter.__init__(self, parent)
        self.setChildrenCollapsible(False)
        self.books_view = books_view
        self.addWidget(books_view)
        self.addWidget(books_view.pin_view)
        books_view.pin_view.splitter = self

    @property
    def splitter_state(self):
        return bytearray(self.saveState())

    @splitter_state.setter
    def splitter_state(self, val):
        if val is not None:
            self.restoreState(val)

    def save_state(self):
        gprefs['book_list_pin_splitter_state'] = self.splitter_state

    def restore_state(self):
        val = gprefs.get('book_list_pin_splitter_state', None)
        self.splitter_state = val
