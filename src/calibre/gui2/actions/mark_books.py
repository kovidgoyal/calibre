#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from qt.core import (QTimer, QApplication, Qt, QEvent, QDialog, QMenu, QIcon,
                     QDialogButtonBox, QPushButton, QLabel, QGridLayout)

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.widgets2 import HistoryComboBox
from calibre.utils.icu import sort_key


class MyHistoryComboBox(HistoryComboBox):
    # This is here so we can change the following two class variables without
    # affecting other users of the HistoryComboBox class
    max_history_items = 10
    min_history_entry_length = 1


class MarkWithTextDialog(QDialog):

    def __init__(self, gui):
        QDialog.__init__(self, parent=gui)
        self.gui = gui
        self.setWindowTitle(_('Mark books with text label'))
        layout = QGridLayout()
        layout.setColumnStretch(1, 10)
        self.setLayout(layout)

        self.text_box = textbox = MyHistoryComboBox()
        textbox.initialize('mark_with_text')

        history = textbox.all_items
        button_rows = min(4, len(history)-1)
        for i in range(0, button_rows):
            if i == 0:
                layout.addWidget(QLabel(_('Recently used values:')), 0, 0, 1, 2)
            button = QPushButton()
            text = history[i+1]
            button.setText(text)
            button.clicked.connect(partial(self.button_pushed, text=text))
            row = i + 1
            layout.addWidget(button, row, 1)
            label = QLabel('&' + str(row+1))
            label.setBuddy(button)
            layout.addWidget(label, row, 0)
        if button_rows > 0:
            layout.addWidget(QLabel(_('Enter a value:')), button_rows+1, 0, 1, 2)
        textbox.show_initial_value(history[0] if history else '')
        layout.addWidget(textbox, button_rows+2, 1)
        textbox.setFocus()
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                      QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box, button_rows+3, 0, 1, 2)

    def text(self):
        return self.text_box.text().strip()

    def button_pushed(self, checked, text=''):
        self.text_box.setText(text)
        self.text_box.save_history()
        self.accept()

    def accept(self):
        if not self.text_box.text().strip():
            d = error_dialog(self.gui, _('Value cannot be empty'), _('You must provide a value'))
            d.exec_()
        else:
            super().accept()


mark_books_with_text = None


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
        self.search_icon = QIcon.ic('search.png')
        self.qaction.triggered.connect(self.toggle_selected)
        self.menu = m = self.qaction.menu()
        m.aboutToShow.connect(self.about_to_show_menu)
        ma = partial(self.create_menu_action, m)
        self.show_marked_action = a = ma('mark_with_text', _('Mark books with text label'), icon='marked.png')
        a.triggered.connect(partial(self.mark_with_text, book_ids=None))
        global mark_books_with_text
        mark_books_with_text = self.mark_with_text
        self.show_marked_action = a = ma('show-marked', _('Show marked books'), icon='search.png', shortcut='Shift+Ctrl+M')
        a.triggered.connect(self.show_marked)
        self.show_marked_with_text = QMenu(_('Show marked books with text label'))
        self.show_marked_with_text.setIcon(self.search_icon)
        m.addMenu(self.show_marked_with_text)
        self.clear_selected_marked_action = a = ma('clear-marks-on-selected', _('Clear marks for selected books'), icon='clear_left.png')
        a.triggered.connect(self.clear_marks_on_selected_books)
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
        if ev.type() == QEvent.Type.MouseButtonPress and ev.button() == Qt.MouseButton.LeftButton:
            mods = QApplication.keyboardModifiers()
            if mods & Qt.KeyboardModifier.ControlModifier or mods & Qt.KeyboardModifier.ShiftModifier:
                self.show_marked()
                return True
        return False

    def about_to_show_menu(self):
        db = self.gui.current_db
        marked_ids = db.data.marked_ids
        num = len(frozenset(marked_ids).intersection(db.new_api.all_book_ids()))
        text = _('Show marked book') if num == 1 else (_('Show marked books') + (' (%d)' % num))
        self.show_marked_action.setText(text)
        counts = dict()
        for v in marked_ids.values():
            counts[v] = counts.get(v, 0) + 1
        labels = sorted(counts.keys(), key=sort_key)
        self.show_marked_with_text.clear()
        if len(labels):
            labs = labels[0:40]
            self.show_marked_with_text.setEnabled(True)
            for t in labs:
                ac = self.show_marked_with_text.addAction(self.search_icon, f'{t} ({counts[t]})')
                ac.triggered.connect(partial(self.show_marked_text, txt=t))
            if len(labs) < len(labels):
                self.show_marked_with_text.addAction(
                    _('{0} labels not shown').format(len(labels) - len(labs)))
        else:
            self.show_marked_with_text.setEnabled(False)

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
            d.exec()
            return set()
        return set(map(self.gui.library_view.model().id, rows))

    def toggle_ids(self, book_ids):
        self.gui.current_db.data.toggle_marked_ids(book_ids)

    def add_ids(self, book_ids):
        self.gui.current_db.data.add_marked_ids(book_ids)

    def show_marked(self):
        self.gui.search.set_search_string('marked:true')

    def show_marked_text(self, txt=None):
        self.gui.search.set_search_string(f'marked:"={txt}"')

    def clear_all_marked(self):
        self.gui.current_db.data.set_marked_ids(())
        if str(self.gui.search.text()).startswith('marked:'):
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

    def mark_with_text(self, book_ids=None):
        if book_ids is None:
            book_ids = self._get_selected_ids()
        if not book_ids:
            return
        dialog = MarkWithTextDialog(self.gui)
        if dialog.exec_() != QDialog.DialogCode.Accepted:
            return
        txt = dialog.text()
        txt = txt if txt else 'true'
        db = self.gui.current_db
        mids = db.data.marked_ids.copy()
        for book_id in book_ids:
            mids[book_id] = txt
        db.data.set_marked_ids(mids)

    def clear_marks_on_selected_books(self):
        book_ids = self._get_selected_ids()
        if not book_ids:
            return
        db = self.gui.current_db
        items = db.data.marked_ids.copy()
        for book_id in book_ids:
            items.pop(book_id, None)
        self.gui.current_db.data.set_marked_ids(items)
