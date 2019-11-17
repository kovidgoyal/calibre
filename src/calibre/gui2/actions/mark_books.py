#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from PyQt5.Qt import QTimer, QApplication, Qt

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from polyglot.builtins import unicode_type


class MarkBooksAction(InterfaceAction):

    name = 'Mark Books'
    action_spec = (_('Mark books'), 'marked.png', _('Temporarily mark books for easy access'), 'Ctrl+M')
    action_type = 'current'
    action_add_menu = True
    dont_add_to = frozenset([
        'context-menu-device', 'menubar-device', 'context-menu-cover-browser'])
    action_menu_clone_qaction = _('Toggle mark for selected books')

    accepts_drops = True

    def accept_enter_event(self, event, mime_data):
        if mime_data.hasFormat("application/calibre+from_library"):
            return True
        return False

    def accept_drag_move_event(self, event, mime_data):
        if mime_data.hasFormat("application/calibre+from_library"):
            return True
        return False

    def drop_event(self, event, mime_data):
        mime = 'application/calibre+from_library'
        if mime_data.hasFormat(mime):
            self.dropped_ids = tuple(map(int, mime_data.data(mime).data().split()))
            QTimer.singleShot(1, self.do_drop)
            return True
        return False

    def do_drop(self):
        book_ids = self.dropped_ids
        del self.dropped_ids
        if book_ids:
            self.toggle_ids(book_ids)

    def genesis(self):
        self.qaction.triggered.connect(self.toggle_selected)
        self.menu = m = self.qaction.menu()
        m.aboutToShow.connect(self.about_to_show_menu)
        ma = partial(self.create_menu_action, m)
        self.show_marked_action = a = ma('show-marked', _('Show marked books'), icon='search.png', shortcut='Shift+Ctrl+M')
        a.triggered.connect(self.show_marked)
        self.clear_marked_action = a = ma('clear-all-marked', _('Clear all marked books'), icon='clear_left.png')
        a.triggered.connect(self.clear_all_marked)
        m.addSeparator()
        self.mark_author_action = a = ma('mark-author', _('Mark all books by selected author(s)'), icon='plus.png')
        connect_lambda(a.triggered, self, lambda self: self.mark_field('authors', True))
        self.mark_series_action = a = ma('mark-series', _('Mark all books in the selected series'), icon='plus.png')
        connect_lambda(a.triggered, self, lambda self: self.mark_field('series', True))
        m.addSeparator()
        self.unmark_author_action = a = ma('unmark-author', _('Clear all books by selected author(s)'), icon='minus.png')
        connect_lambda(a.triggered, self, lambda self: self.mark_field('authors', False))
        self.unmark_series_action = a = ma('unmark-series', _('Clear all books in the selected series'), icon='minus.png')
        connect_lambda(a.triggered, self, lambda self: self.mark_field('series', False))

    def gui_layout_complete(self):
        for x in self.gui.bars_manager.main_bars + self.gui.bars_manager.child_bars:
            try:
                w = x.widgetForAction(self.qaction)
                w.installEventFilter(self)
            except:
                continue

    def eventFilter(self, obj, ev):
        if ev.type() == ev.MouseButtonPress and ev.button() == Qt.LeftButton:
            mods = QApplication.keyboardModifiers()
            if mods & Qt.ControlModifier or mods & Qt.ShiftModifier:
                self.show_marked()
                return True
        return False

    def about_to_show_menu(self):
        db = self.gui.current_db
        num = len(frozenset(db.data.marked_ids).intersection(db.new_api.all_book_ids()))
        text = _('Show marked book') if num == 1 else (_('Show marked books') + (' (%d)' % num))
        self.show_marked_action.setText(text)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)
        for action in self.menu.actions():
            action.setEnabled(enabled)

    def toggle_selected(self):
        book_ids = self._get_selected_ids()
        if book_ids:
            self.toggle_ids(book_ids)

    def _get_selected_ids(self):
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot mark'), _('No books selected'))
            d.exec_()
            return set()
        return set(map(self.gui.library_view.model().id, rows))

    def toggle_ids(self, book_ids):
        self.gui.current_db.data.toggle_marked_ids(book_ids)

    def show_marked(self):
        self.gui.search.set_search_string('marked:true')

    def clear_all_marked(self):
        self.gui.current_db.data.set_marked_ids(())
        if unicode_type(self.gui.search.text()).startswith('marked:'):
            self.gui.search.set_search_string('')

    def mark_field(self, field, add):
        book_ids = self._get_selected_ids()
        if not book_ids:
            return
        db = self.gui.current_db
        items = set()
        for book_id in book_ids:
            items |= set(db.new_api.field_ids_for(field, book_id))
        book_ids = set()
        for item_id in items:
            book_ids |= db.new_api.books_for_field(field, item_id)
        mids = db.data.marked_ids.copy()
        for book_id in book_ids:
            if add:
                mids[book_id] = True
            else:
                mids.pop(book_id, None)
        db.data.set_marked_ids(mids)
