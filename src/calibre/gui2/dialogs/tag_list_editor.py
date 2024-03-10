#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>


import copy
from contextlib import contextmanager
from functools import partial

from qt.core import (
    QAbstractItemView, QAction, QApplication, QColor, QDialog,
    QDialogButtonBox, QFrame, QIcon, QLabel, QMenu, QSize, QStyledItemDelegate,
    Qt, QTableWidgetItem, QTimer, pyqtSignal, sip,
)

from calibre import sanitize_file_name
from calibre.gui2 import (error_dialog, gprefs, question_dialog, choose_files,
                          choose_save_file)
from calibre.gui2.actions.show_quickview import get_quickview_action_plugin
from calibre.gui2.complete2 import EditWithComplete
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.tag_list_editor_table_widget import TleTableWidget
from calibre.gui2.dialogs.tag_list_editor_ui import Ui_TagListEditor
from calibre.gui2.widgets import EnLineEdit
from calibre.utils.config import prefs
from calibre.utils.icu import (
    capitalize, contains, lower as icu_lower, primary_contains, primary_startswith,
    upper as icu_upper,
)
from calibre.utils.titlecase import titlecase

QT_HIDDEN_CLEAR_ACTION = '_q_qlineeditclearaction'


class NameTableWidgetItem(QTableWidgetItem):

    def __init__(self, sort_key):
        QTableWidgetItem.__init__(self)
        self.initial_value = ''
        self.current_value = ''
        self.is_deleted = False
        self.is_placeholder = False
        self.sort_key = sort_key

    def data(self, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if self.is_deleted:
                return ''
            return self.current_value
        elif role == Qt.ItemDataRole.EditRole:
            return self.current_value
        else:
            return QTableWidgetItem.data(self, role)

    def set_is_deleted(self, to_what):
        if to_what:
            self.setIcon(QIcon.cached_icon('trash.png'))
        else:
            self.setIcon(QIcon.cached_icon())
            self.current_value = self.initial_value
        self.is_deleted = to_what

    def setData(self, role, data):
        if role == Qt.ItemDataRole.EditRole:
            self.current_value = data
        QTableWidgetItem.setData(self, role, data)

    def set_initial_text(self, txt):
        self.initial_value = txt

    def initial_text(self):
        return self.initial_value

    def text_is_modified(self):
        return not self.is_deleted and self.current_value != self.initial_value

    def text(self):
        return self.current_value

    def setText(self, txt):
        self.is_placeholder = False
        self.current_value = txt
        QTableWidgetItem.setText(self, txt)

    # Before this method is called, signals should be blocked for the
    # table containing this item
    def set_placeholder(self, txt):
        self.text_before_placeholder = self.current_value
        self.setText(txt)
        self.is_placeholder = True

    # Before this method is called, signals should be blocked for the
    # table containing this item
    def reset_placeholder(self):
        if self.is_placeholder:
            self.setText(self.text_before_placeholder)

    def __ge__(self, other):
        return (self.sort_key(str(self.text())) >=
                    self.sort_key(str(other.text())))

    def __lt__(self, other):
        return (self.sort_key(str(self.text())) <
                    self.sort_key(str(other.text())))


class CountTableWidgetItem(QTableWidgetItem):

    def __init__(self, count):
        QTableWidgetItem.__init__(self, str(count))
        self._count = count

    def __ge__(self, other):
        return self._count >= other._count

    def __lt__(self, other):
        return self._count < other._count


class NotesTableWidgetItem(QTableWidgetItem):

    # These define the sort order for notes columns
    EMPTY = 0
    UNCHANGED = 1
    EDITED = 2
    DELETED = 3

    def __init__(self):
        QTableWidgetItem.__init__(self, '')
        self.set_sort_val(self.EMPTY)

    def set_sort_val(self, val):
        self._sort_val = val

    def __ge__(self, other):
        return self._sort_val >= other._sort_val

    def __lt__(self, other):
        return self._sort_val < other._sort_val


class NotesUtilities():

    def __init__(self, table, category, item_id_getter):
        self.table = table
        self.modified_notes = {}
        self.category = category
        self.item_id_getter = item_id_getter

    def is_note_modified(self, item_id) -> bool:
        return item_id in self.modified_notes

    def get_db(self):
        from calibre.gui2.ui import get_gui
        return get_gui().current_db.new_api

    def restore_all_notes(self):
        # should only be called from reject()
        db = self.get_db()
        for item_id, before in self.modified_notes.items():
            if before:
                db.import_note(self.category, item_id, before.encode('utf-8'), path_is_data=True)
            else:
                db.set_notes_for(self.category, item_id, '')
        self.modified_notes.clear()

    def set_icon(self, item, id_, has_value):
        with block_signals(self.table):
            if id_ not in self.modified_notes:
                if not has_value:
                    item.setIcon(QIcon.cached_icon())
                    item.set_sort_val(NotesTableWidgetItem.EMPTY)
                else:
                    item.setIcon(QIcon.cached_icon('notes.png'))
                    item.set_sort_val(NotesTableWidgetItem.UNCHANGED)
            else:
                if has_value:
                    item.setIcon(QIcon.cached_icon('modified.png'))
                    item.set_sort_val(NotesTableWidgetItem.EDITED)
                elif not bool(self.modified_notes[id_]):
                    item.setIcon(QIcon.cached_icon())
                    item.set_sort_val(NotesTableWidgetItem.EMPTY)
                else:
                    item.setIcon(QIcon.cached_icon('trash.png'))
                    item.set_sort_val(NotesTableWidgetItem.DELETED)
        self.table.cellChanged.emit(item.row(), item.column())
        self.table.itemChanged.emit(item)

    def edit_note(self, item):
        item_id = self.item_id_getter(item)
        from calibre.gui2.dialogs.edit_category_notes import EditNoteDialog
        db = self.get_db()
        before = db.notes_for(self.category, item_id)
        note = db.export_note(self.category, item_id) if before else ''
        d = EditNoteDialog(self.category, item_id, db, parent=self.table)
        if d.exec() == QDialog.DialogCode.Accepted:
            after = db.notes_for(self.category, item_id)
            if item_id not in self.modified_notes:
                self.modified_notes[item_id] = note
            self.set_icon(item, item_id, bool(after))

    def undo_note_edit(self, item):
        item_id = self.item_id_getter(item)
        before = self.modified_notes.pop(item_id, None)
        db = self.get_db()
        if before is not None:
            if before:
                db.import_note(self.category, item_id, before.encode('utf-8'), path_is_data=True)
            else:
                db.set_notes_for(self.category, item_id, '')
        self.set_icon(item, item_id, bool(before))

    def delete_note(self, item):
        item_id = self.item_id_getter(item)
        db = self.get_db()
        if item_id not in self.modified_notes:
            self.modified_notes[item_id] = db.notes_for(self.category, item_id)
        db.set_notes_for(self.category, item_id, '')
        self.set_icon(item, item_id, False)

    def do_export(self, item, item_name):
        item_id = self.item_id_getter(item)
        dest = choose_save_file(self.table, 'save-exported-note', _('Export note to a file'),
                                filters=[(_('HTML files'), ['html'])],
                                initial_filename=f'{sanitize_file_name(item_name)}.html',
                                all_files=False)
        if dest:
            html = self.get_db().export_note(self.category, item_id)
            with open(dest, 'wb') as f:
                f.write(html.encode('utf-8'))

    def do_import(self, item):
        src = choose_files(self.table, 'load-imported-note', _('Import note from a file'),
                           filters=[(_('HTML files'), ['html'])],
                           all_files=False, select_only_single_file=True)
        if src:
            item_id = self.item_id_getter(item)
            db = self.get_db()
            before = db.notes_for(self.category, item_id)
            if item_id not in self.modified_notes:
                self.modified_notes[item_id] = before
            db.import_note(self.category, item_id, src[0])
            after = db.notes_for(self.category, item_id)
            self.set_icon(item, item_id, bool(after))

    def context_menu(self, menu, item, item_name):
        m = menu
        item_id = self.item_id_getter(item)
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db.new_api
        has_note = bool(db.notes_for(self.category, item_id))

        ac = m.addAction(QIcon.cached_icon('edit-undo.png'), _('Undo'))
        ac.setEnabled(item_id in self.modified_notes)
        ac.triggered.connect(partial(self.undo_note_edit, item))

        ac = m.addAction(QIcon.cached_icon('edit_input.png'), _('Edit note') if has_note else _('Create note'))
        ac.triggered.connect(partial(self.table.editItem, item))

        ac = m.addAction(QIcon.cached_icon('trash.png'), _('Delete note'))
        ac.setEnabled(has_note)
        ac.triggered.connect(partial(self.delete_note, item))

        ac = m.addAction(QIcon.cached_icon('forward.png'), _('Export note to a file'))
        ac.setEnabled(has_note)
        ac.triggered.connect(partial(self.do_export, item, item_name))

        ac = m.addAction(QIcon.cached_icon('back.png'), _('Import note from a file'))
        ac.triggered.connect(partial(self.do_import, item))


VALUE_COLUMN = 0
COUNT_COLUMN = 1
WAS_COLUMN = 2
LINK_COLUMN = 3
NOTES_COLUMN = 4


class EditColumnDelegate(QStyledItemDelegate):
    editing_finished = pyqtSignal(int)
    editing_started  = pyqtSignal(int)

    def __init__(self, table, check_for_deleted_items, category, notes_utilities, item_id_getter, parent=None):
        super().__init__(table)
        self.table = table
        self.completion_data = None
        self.check_for_deleted_items = check_for_deleted_items
        self.category = category
        self.notes_utilities = notes_utilities
        self.item_id_getter = item_id_getter

    def set_completion_data(self, data):
        self.completion_data = data

    def createEditor(self, parent, option, index):
        if index.column() == VALUE_COLUMN:
            if self.check_for_deleted_items(show_error=True):
                return None
            self.editing_started.emit(index.row())
            self.item = self.table.itemFromIndex(index)
            if self.completion_data:
                editor = EditWithComplete(parent)
                editor.set_separator(None)
                editor.update_items_cache(self.completion_data)
            else:
                editor = EnLineEdit(parent)
            return editor
        if index.column() == NOTES_COLUMN:
            self.notes_utilities.edit_note(self.table.itemFromIndex(index))
            return None
        self.editing_started.emit(index.row())
        editor = EnLineEdit(parent)
        editor.setClearButtonEnabled(True)
        return editor

    def destroyEditor(self, editor, index):
        self.editing_finished.emit(index.row())
        super().destroyEditor(editor, index)


@contextmanager
def block_signals(widget):
    old = widget.blockSignals(True)
    try:
        yield
    finally:
        widget.blockSignals(old)


class TagListEditor(QDialog, Ui_TagListEditor):

    def __init__(self, window, cat_name, tag_to_match, get_book_ids, sorter,
                 ttm_is_first_letter=False, category=None, fm=None, link_map=None):
        QDialog.__init__(self, window)
        Ui_TagListEditor.__init__(self)
        self.setupUi(self)

        from calibre.gui2.ui import get_gui
        self.supports_notes = bool(category and get_gui().current_db.new_api.field_supports_notes(category))
        self.search_box.setMinimumContentsLength(25)
        if category is not None:
            item_map = get_gui().current_db.new_api.get_item_name_map(category)
            self.original_links = {item_map[k]:v for k,v in link_map.items()}
            self.current_links = copy.copy(self.original_links)
        else:
            self.original_links = {}
            self.current_links = {}

        # Put the category name into the title bar
        self.category_name = cat_name
        self.category = category
        self.setWindowTitle(_('Manage {}').format(cat_name))
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        # initialization
        self.to_rename = {}
        self.to_delete = set()
        self.all_tags = {}
        self.original_names = {}
        self.links = {}
        self.notes_utilities = NotesUtilities(None, self.category, self.get_item_id)

        self.ordered_tags = []
        self.sorter = sorter
        self.get_book_ids = get_book_ids
        self.text_before_editing = ''

        self.sort_names = ('name', 'count', 'was', 'link', 'notes')
        self.last_sorted_by = 'name'
        self.name_order = self.count_order = self.was_order = self.link_order = self.notes_order = 0

        if prefs['case_sensitive']:
            self.string_contains = contains
        else:
            self.string_contains = self.case_insensitive_compare

        self.delete_button.clicked.connect(self.delete_tags)
        self.rename_button.clicked.connect(self.edit_button_clicked)
        self.undo_button.clicked.connect(self.undo_edit)

        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText(_('&OK'))
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText(_('&Cancel'))
        self.buttonBox.accepted.connect(self.accepted)
        self.buttonBox.rejected.connect(self.rejected)

        self.search_box.initialize('tag_list_search_box_' + cat_name)
        le = self.search_box.lineEdit()
        ac = le.findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
        if ac is not None:
            ac.triggered.connect(self.clear_search)
        self.search_box.textChanged.connect(self.search_text_changed)
        self.search_button.clicked.connect(self.do_search)
        self.search_button.setDefault(True)

        self.filter_box.initialize('tag_list_filter_box_' + cat_name)
        le = self.filter_box.lineEdit()
        ac = le.findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
        if ac is not None:
            ac.triggered.connect(self.clear_filter)
        le.returnPressed.connect(self.do_filter)
        self.filter_button.clicked.connect(self.do_filter)
        self.show_button_layout.setSpacing(0)
        self.show_button_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_all_checkbox.setContentsMargins(0, 0, 0, 0)
        self.apply_all_checkbox.setChecked(True)
        self.apply_vl_checkbox.toggled.connect(self.vl_box_changed)
        self.apply_selection_checkbox.setContentsMargins(0, 0, 0, 0)
        self.apply_selection_checkbox.toggled.connect(self.apply_selection_box_changed)

        self.is_enumerated = False
        if fm:
            if fm['datatype'] == 'enumeration':
                self.is_enumerated = True
                self.enum_permitted_values = fm.get('display', {}).get('enum_values', None)
        # Add the data
        self.search_item_row = -1
        self.table = None
        self.fill_in_table(None, tag_to_match, ttm_is_first_letter)

    def sizeHint(self):
        return super().sizeHint() + QSize(150, 100)

    def link_context_menu(self, menu, item):
        m = menu
        is_deleted = bool(self.table.item(item.row(), VALUE_COLUMN).is_deleted)
        item_id = self.get_item_id(item)

        ca = m.addAction(_('Copy'))
        ca.triggered.connect(partial(self.copy_to_clipboard, item))
        ca.setIcon(QIcon.cached_icon('edit-copy.png'))
        ca.setEnabled(not is_deleted)

        ca = m.addAction(_('Paste'))
        ca.setIcon(QIcon.cached_icon('edit-paste.png'))
        ca.triggered.connect(partial(self.paste_from_clipboard, item))
        ca.setEnabled(not is_deleted)

        ca = m.addAction(_('Undo'))
        ca.setIcon(QIcon.cached_icon('edit-undo.png'))
        ca.triggered.connect(partial(self.undo_link_edit, item, item_id))
        ca.setEnabled(not is_deleted and self.link_is_edited(item_id))

        ca = m.addAction(_('Edit'))
        ca.setIcon(QIcon.cached_icon('edit_input.png'))
        ca.triggered.connect(partial(self.table.editItem, item))
        ca.setEnabled(not is_deleted)

        ca = m.addAction(_('Delete link'))
        ca.setIcon(QIcon.cached_icon('trash.png'))
        def delete_link_text(item):
            item.setText('')
        ca.triggered.connect(partial(delete_link_text, item))
        ca.setEnabled(not is_deleted)

    def value_context_menu(self, menu, item):
        m = menu
        self.table.setCurrentItem(item)

        ca = m.addAction(_('Copy'))
        ca.triggered.connect(partial(self.copy_to_clipboard, item))
        ca.setIcon(QIcon.cached_icon('edit-copy.png'))
        ca.setEnabled(not item.is_deleted)

        ca = m.addAction(_('Paste'))
        ca.setIcon(QIcon.cached_icon('edit-paste.png'))
        ca.triggered.connect(partial(self.paste_from_clipboard, item))
        ca.setEnabled(not item.is_deleted)

        ca = m.addAction(_('Undo'))
        ca.setIcon(QIcon.cached_icon('edit-undo.png'))
        if item.is_deleted:
            ca.triggered.connect(self.undo_edit)
        else:
            ca.triggered.connect(partial(self.undo_value_edit, item, self.get_item_id(item)))
        ca.setEnabled(item.is_deleted or item.text() != self.original_names[self.get_item_id(item)])

        ca = m.addAction(_('Edit'))
        ca.setIcon(QIcon.cached_icon('edit_input.png'))
        ca.triggered.connect(self.edit_button_clicked)
        ca.setEnabled(not item.is_deleted)

        ca = m.addAction(_('Delete'))
        ca.setIcon(QIcon.cached_icon('trash.png'))
        ca.triggered.connect(self.delete_tags)
        item_name = str(item.text())
        ca.setEnabled(not item.is_deleted)

        ca = m.addAction(_('Search for {}').format(item_name))
        ca.setIcon(QIcon.cached_icon('search.png'))
        ca.triggered.connect(partial(self.set_search_text, item_name))
        item_name = str(item.text())
        ca.setEnabled(not item.is_deleted)

        ca = m.addAction(_('Filter by {}').format(item_name))
        ca.setIcon(QIcon.cached_icon('filter.png'))
        ca.triggered.connect(partial(self.set_filter_text, item_name))
        ca.setEnabled(not item.is_deleted)

        if self.category is not None:
            ca = m.addAction(_("Search the library for {0}").format(item_name))
            ca.setIcon(QIcon.cached_icon('lt.png'))
            ca.triggered.connect(partial(self.search_for_books, item))
            ca.setEnabled(not item.is_deleted)

        if self.table.state() == QAbstractItemView.State.EditingState:
            m.addSeparator()
            case_menu = QMenu(_('Change case'))
            case_menu.setIcon(QIcon.cached_icon('font_size_larger.png'))
            action_upper_case = case_menu.addAction(_('Upper case'))
            action_lower_case = case_menu.addAction(_('Lower case'))
            action_swap_case = case_menu.addAction(_('Swap case'))
            action_title_case = case_menu.addAction(_('Title case'))
            action_capitalize = case_menu.addAction(_('Capitalize'))
            action_upper_case.triggered.connect(partial(self.do_case, icu_upper))
            action_lower_case.triggered.connect(partial(self.do_case, icu_lower))
            action_swap_case.triggered.connect(partial(self.do_case, self.swap_case))
            action_title_case.triggered.connect(partial(self.do_case, titlecase))
            action_capitalize.triggered.connect(partial(self.do_case, capitalize))
            m.addMenu(case_menu)

    def show_context_menu(self, point):
        item = self.table.itemAt(point)
        if item is None or item.column() in (WAS_COLUMN, COUNT_COLUMN):
            return
        m = QMenu()
        if item.column() == NOTES_COLUMN:
            self.notes_utilities.context_menu(m, item, self.table.item(item.row(), VALUE_COLUMN).text())
        elif item.column() == VALUE_COLUMN:
            self.value_context_menu(m, item)
        elif item.column() == LINK_COLUMN:
            self.link_context_menu(m, item)
        m.exec(self.table.viewport().mapToGlobal(point))

    def search_for_books(self, item):
        from calibre.gui2.ui import get_gui
        get_gui().search.set_search_string('{}:"={}"'.format(self.category,
                                   str(item.text()).replace(r'"', r'\"')))

        qv = get_quickview_action_plugin()
        if qv:
            view = get_gui().library_view
            rows = view.selectionModel().selectedRows()
            if len(rows) > 0:
                current_row = rows[0].row()
                current_col = view.column_map.index(self.category)
                index = view.model().index(current_row, current_col)
                qv.change_quickview_column(index, show=False)

    def copy_to_clipboard(self, item):
        cb = QApplication.clipboard()
        cb.setText(str(item.text()))

    def paste_from_clipboard(self, item):
        cb = QApplication.clipboard()
        item.setText(cb.text())

    def case_insensitive_compare(self, l, r):
        if prefs['use_primary_find_in_search']:
            return primary_contains(l, r)
        return contains(l.lower(), r.lower())

    def do_case(self, func):
        items = self.table.selectedItems()
        # block signals to avoid the "edit one changes all" behavior
        with block_signals(self.table):
            for item in items:
                item.setText(func(str(item.text())))

    def swap_case(self, txt):
        return txt.swapcase()

    def vl_box_changed(self):
        self.search_item_row = -1
        self.fill_in_table(None, None, False)

    def apply_selection_box_changed(self):
        self.search_item_row = -1
        self.fill_in_table(None, None, False)

    def selection_to_apply(self):
        if self.apply_selection_checkbox.isChecked():
            return 'selection'
        if self.apply_vl_checkbox.isChecked():
            return 'virtual_library'
        return None

    def do_search(self):
        self.not_found_label.setVisible(False)
        find_text = str(self.search_box.currentText())
        if not find_text:
            return
        for _ in range(0, self.table.rowCount()):
            r = self.search_item_row = (self.search_item_row + 1) % self.table.rowCount()
            if self.string_contains(find_text, self.table.item(r, VALUE_COLUMN).text()):
                self.table.setCurrentItem(self.table.item(r, VALUE_COLUMN))
                self.table.setFocus(Qt.FocusReason.OtherFocusReason)
                return
        # Nothing found. Pop up the little dialog for 1.5 seconds
        self.not_found_label.setVisible(True)
        self.not_found_label_timer.start(1500)

    def search_text_changed(self):
        self.search_item_row = -1

    def clear_search(self):
        self.search_item_row = -1
        self.search_box.setText('')

    def set_search_text(self, txt):
        self.search_box.setText(txt)
        self.do_search()

    def create_table(self):
        # For some reason we must recreate the table if we change the row count.
        # If we don't then the old items remain even if replaced by setItem().
        # I'm not sure if this is standard Qt behavior or behavior triggered by
        # something in this class, but replacing the table fixes it.
        if self.table is not None:
            self.save_geometry()
            self.central_layout.removeWidget(self.table)
            sip.delete(self.table)
        self.table = TleTableWidget(self)
        self.central_layout.addWidget(self.table)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)

        hh = self.table.horizontalHeader()
        hh.sectionResized.connect(self.table_column_resized)
        hh.setSectionsClickable(True)
        self.table.setSortingEnabled(True)
        hh.sectionClicked.connect(self.record_sort)
        hh.setSortIndicatorShown(True)

        vh = self.table.verticalHeader()
        vh.setDefaultSectionSize(gprefs.get('general_category_editor_row_height', vh.defaultSectionSize()))
        vh.sectionResized.connect(self.row_height_changed)

        self.table.setColumnCount(5)

        self.notes_utilities.table = self.table
        self.edit_delegate = EditColumnDelegate(self.table, self.check_for_deleted_items,
                                                self.category, self.notes_utilities, self.get_item_id)
        self.edit_delegate.editing_finished.connect(self.stop_editing)
        self.edit_delegate.editing_started.connect(self.start_editing)
        self.table.setItemDelegateForColumn(VALUE_COLUMN, self.edit_delegate)
        self.table.setItemDelegateForColumn(LINK_COLUMN, self.edit_delegate)
        self.table.setItemDelegateForColumn(NOTES_COLUMN, self.edit_delegate)

        self.table.delete_pressed.connect(self.delete_pressed)
        self.table.itemDoubleClicked.connect(self.edit_item)
        self.table.itemChanged.connect(self.finish_editing)
        self.table.itemSelectionChanged.connect(self.selection_changed)

        l = QLabel(self.table)
        self.not_found_label = l
        l.setFrameStyle(QFrame.Shape.StyledPanel)
        l.setAutoFillBackground(True)
        l.setText(_('No matches found'))
        l.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        l.resize(l.sizeHint())
        l.move(10, 0)
        l.setVisible(False)
        self.not_found_label_timer = QTimer()
        self.not_found_label_timer.setSingleShot(True)
        self.not_found_label_timer.timeout.connect(
                self.not_found_label_timer_event, type=Qt.ConnectionType.QueuedConnection)

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)

        self.restore_geometry(gprefs, 'tag_list_editor_dialog_geometry')
        self.table_column_widths = gprefs.get('tag_list_editor_table_widths', None)
        if self.table_column_widths is not None:
            for col,width in enumerate(self.table_column_widths):
                self.table.setColumnWidth(col, width)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def get_item_id(self, item):
        return int(self.table.item(item.row(), VALUE_COLUMN).data(Qt.ItemDataRole.UserRole))

    def row_height_changed(self, row, old, new):
        self.table.verticalHeader().setDefaultSectionSize(new)

    def link_is_edited(self, item_id):
        return self.current_links.get(item_id, None) != self.original_links.get(item_id)

    def set_link_icon(self, id_, item):
        with block_signals(self.table):
            if self.link_is_edited(id_):
                item.setIcon(QIcon.cached_icon('modified.png'))
            else:
                item.setIcon(QIcon.cached_icon())

    def fill_in_table(self, tags, tag_to_match, ttm_is_first_letter):
        self.create_table()

        data = self.get_book_ids(self.selection_to_apply())
        self.all_tags = {}
        filter_text = icu_lower(str(self.filter_box.text()))
        for k,v,count in data:
            if not filter_text or self.string_contains(filter_text, icu_lower(v)):
                self.all_tags[v] = {'key': k, 'count': count, 'cur_name': v,
                                   'is_deleted': k in self.to_delete}
                self.original_names[k] = v
        if self.is_enumerated:
            self.edit_delegate.set_completion_data(self.enum_permitted_values)
        else:
            self.edit_delegate.set_completion_data(self.original_names.values())

        self.ordered_tags = sorted(self.all_tags.keys(), key=self.sorter)
        if tags is None:
            tags = self.ordered_tags

        select_item = None
        with block_signals(self.table):
            self.name_col = QTableWidgetItem(self.category_name)
            self.table.setHorizontalHeaderItem(VALUE_COLUMN, self.name_col)
            self.count_col = QTableWidgetItem(_('Count'))
            self.table.setHorizontalHeaderItem(1, self.count_col)
            self.was_col = QTableWidgetItem(_('Was'))
            self.table.setHorizontalHeaderItem(2, self.was_col)
            self.link_col = QTableWidgetItem(_('Link'))
            self.table.setHorizontalHeaderItem(LINK_COLUMN, self.link_col)
            if self.supports_notes:
                self.notes_col = QTableWidgetItem(_('Notes'))
                self.table.setHorizontalHeaderItem(4, self.notes_col)

            self.table.setRowCount(len(tags))
            if self.supports_notes:
                from calibre.gui2.ui import get_gui
                all_items_that_have_notes = get_gui().current_db.new_api.get_all_items_that_have_notes(self.category)
            for row,tag in enumerate(tags):
                item = NameTableWidgetItem(self.sorter)
                is_deleted = self.all_tags[tag]['is_deleted']
                item.set_is_deleted(is_deleted)
                id_ = self.all_tags[tag]['key']
                item.setData(Qt.ItemDataRole.UserRole, id_)
                item.set_initial_text(tag)
                if id_ in self.to_rename:
                    item.setText(self.to_rename[id_])
                else:
                    item.setText(tag)
                if self.is_enumerated and str(item.text()) not in self.enum_permitted_values:
                    item.setBackground(QColor('#FF2400'))
                    item.setToolTip(
                        '<p>' +
                        _("This is not one of this column's permitted values ({0})"
                          ).format(', '.join(self.enum_permitted_values)) + '</p>')
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, VALUE_COLUMN, item)
                if select_item is None:
                    if ttm_is_first_letter:
                        if primary_startswith(tag, tag_to_match):
                            select_item = item
                    elif tag == tag_to_match:
                        select_item = item
                if item.text_is_modified():
                    item.setIcon(QIcon.cached_icon('modified.png'))

                item = CountTableWidgetItem(self.all_tags[tag]['count'])
                item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                self.table.setItem(row, COUNT_COLUMN, item)

                item = QTableWidgetItem()
                item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                if id_ in self.to_rename or id_ in self.to_delete:
                    item.setData(Qt.ItemDataRole.DisplayRole, tag)
                self.table.setItem(row, WAS_COLUMN, item)

                item = QTableWidgetItem()
                if self.original_links is None:
                    item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                    item.setText(_('no links available'))
                else:
                    if is_deleted:
                        item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                    else:
                        item.setFlags(item.flags() | (Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                        self.set_link_icon(id_, item)
                    item.setText(self.current_links.get(id_, ''))
                self.table.setItem(row, LINK_COLUMN, item)

                if self.supports_notes:
                    item = NotesTableWidgetItem()
                    self.notes_utilities.set_icon(item, id_, id_ in all_items_that_have_notes)
                    if is_deleted:
                        item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                    else:
                        item.setFlags(item.flags() | (Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                    self.table.setItem(row, NOTES_COLUMN, item)

            # re-sort the table
            column = self.sort_names.index(self.last_sorted_by)
            sort_order = getattr(self, self.last_sorted_by + '_order')
            self.table.sortByColumn(column, Qt.SortOrder(sort_order))

            if select_item is not None:
                self.table.setCurrentItem(select_item)
                self.table.setFocus(Qt.FocusReason.OtherFocusReason)
                self.start_find_pos = select_item.row()
            else:
                self.table.setCurrentCell(0, 0)
                self.search_box.setFocus()
                self.start_find_pos = -1
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def not_found_label_timer_event(self):
        self.not_found_label.setVisible(False)

    def clear_filter(self):
        self.filter_box.setText('')
        self.do_filter()

    def set_filter_text(self, txt):
        self.filter_box.setText(txt)
        self.do_filter()

    def do_filter(self):
        self.fill_in_table(None, None, False)

    def table_column_resized(self, *args):
        self.table_column_widths = []
        for c in range(0, self.table.columnCount()):
            self.table_column_widths.append(self.table.columnWidth(c))

    def resizeEvent(self, *args):
        QDialog.resizeEvent(self, *args)
        if self.table_column_widths is not None:
            for c,w in enumerate(self.table_column_widths):
                self.table.setColumnWidth(c, w)
        else:
            # the vertical scroll bar might not be rendered, so might not yet
            # have a width. Assume 25. Not a problem because user-changed column
            # widths will be remembered
            w = self.table.width() - 25 - self.table.verticalHeader().width()
            w //= self.table.columnCount()
            for c in range(0, self.table.columnCount()):
                self.table.setColumnWidth(c, w)

    def start_editing(self, on_row):
        current_column = self.table.currentItem().column()
        # We don't support editing multiple link or notes rows at the same time.
        # Use the current cell.
        if current_column != VALUE_COLUMN:
            self.table.setCurrentItem(self.table.item(on_row, current_column))
        items = self.table.selectedItems()
        with block_signals(self.table):
            self.table.setSortingEnabled(False)
            for item in items:
                if item.row() != on_row:
                    item.set_placeholder(_('Editing...'))
                else:
                    self.text_before_editing = item.text()

    def stop_editing(self, on_row):
        # This works because the link and notes fields doesn't support editing
        # on multiple lines, so the on_row check will always be false.
        items = self.table.selectedItems()
        with block_signals(self.table):
            for item in items:
                if item.row() != on_row and item.is_placeholder:
                    item.reset_placeholder()
            self.table.setSortingEnabled(True)

    def finish_editing(self, edited_item):
        if edited_item.column() == LINK_COLUMN:
            id_ = self.get_item_id(edited_item)
            txt = edited_item.text()
            if txt:
                self.current_links[id_] = txt
            else:
                self.current_links.pop(id_, None)
            self.set_link_icon(id_, edited_item)
            return

        if edited_item.column() == NOTES_COLUMN:
            # Done elsewhere
            return

        # Item value column
        if not edited_item.text():
            error_dialog(self, _('Item is blank'), _(
                'An item cannot be set to nothing. Delete it instead.'), show=True)
            with block_signals(self.table):
                edited_item.setText(self.text_before_editing)
            return
        new_text = str(edited_item.text())
        if self.is_enumerated and new_text not in self.enum_permitted_values:
            error_dialog(self, _('Item is not a permitted value'), '<p>' + _(
                "This column has a fixed set of permitted values. The entered "
                "text must be one of ({0}).").format(', '.join(self.enum_permitted_values)) +
                '</p>', show=True)
            with block_signals(self.table):
                edited_item.setText(self.text_before_editing)
            return

        items = self.table.selectedItems()
        with block_signals(self.table):
            for item in items:
                id_ = int(item.data(Qt.ItemDataRole.UserRole))
                self.to_rename[id_] = new_text
                orig = self.table.item(item.row(), WAS_COLUMN)
                item.setText(new_text)
                if item.text_is_modified():
                    item.setIcon(QIcon.cached_icon('modified.png'))
                    orig.setData(Qt.ItemDataRole.DisplayRole, item.initial_text())
                else:
                    item.setIcon(QIcon.cached_icon())
                    orig.setData(Qt.ItemDataRole.DisplayRole, '')

    def undo_link_edit(self, item, item_id):
        if item_id in self.original_links:
            link_txt = self.current_links[item_id] = self.original_links[item_id]
        else:
            self.current_links.pop(item_id, None)
            link_txt = ''
        item = self.table.item(item.row(), LINK_COLUMN)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable)
        item.setText(link_txt)
        item.setIcon(QIcon.cached_icon())

    def undo_value_edit(self, item, item_id):
        with block_signals(self.table):
            item.setText(item.initial_text())
            self.to_rename.pop(item_id, None)
            row = item.row()
            self.table.item(row, WAS_COLUMN).setData(Qt.ItemDataRole.DisplayRole, '')
            item.setIcon(QIcon.cached_icon('modified.png') if item.text_is_modified() else QIcon.cached_icon())

    def undo_edit(self):
        col_zero_items = (self.table.item(item.row(), VALUE_COLUMN) for item in self.table.selectedItems())
        if not col_zero_items:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of available items.')).exec()
            return

        if not confirm(
            _('Do you really want to undo all your changes on selected rows?'),
            'tag_list_editor_undo'):
            return
        with block_signals(self.table):
            for col_zero_item in col_zero_items:
                id_ = self.get_item_id(col_zero_item)
                row = col_zero_item.row()

                # item value column
                self.undo_value_edit(col_zero_item, id_)
                col_zero_item.set_is_deleted(False)
                self.to_delete.discard(id_)

                # Link column
                self.undo_link_edit(self.table.item(row, LINK_COLUMN), id_)
                # Notes column
                item = self.table.item(row, NOTES_COLUMN)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable)
                if id_ in self.notes_utilities.modified_notes:
                    self.notes_utilities.undo_note_edit(item)
                    item.setIcon(QIcon.cached_icon())

    def selection_changed(self):
        if self.table.currentIndex().isValid():
            col = self.table.currentIndex().column()
            with block_signals(self.table):
                if col != VALUE_COLUMN:
                    self.table.setCurrentIndex(self.table.currentIndex())
                else:
                    for itm in (item for item in self.table.selectedItems() if item.column() != col):
                        itm.setSelected(False)

    def check_for_deleted_items(self, show_error=False):
        for col_zero_item in (self.table.item(item.row(), VALUE_COLUMN) for item in self.table.selectedItems()):
            if col_zero_item.is_deleted:
                if show_error:
                    error_dialog(self, _('Selection contains deleted items'),
                                '<p>'+_('The selection contains deleted items. You '
                                        'must undelete them before editing.')+'<br>',
                                show=True)
                return True
        return False

    def edit_button_clicked(self):
        self.edit_item(self.table.currentItem())

    def edit_item(self, item):
        if item is None:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of available items.')).exec()
            return
        if self.check_for_deleted_items():
            if not question_dialog(self, _('Undelete items?'),
                   '<p>'+_('Items must be undeleted to continue. Do you want '
                           'to do this?')+'<br>'):
                return
        with block_signals(self.table):
            for col_zero_item in (self.table.item(item.row(), VALUE_COLUMN)
                                  for item in self.table.selectedItems()):
                # undelete any deleted items
                if col_zero_item.is_deleted:
                    col_zero_item.set_is_deleted(False)
                    self.to_delete.discard(int(col_zero_item.data(Qt.ItemDataRole.UserRole)))
                    orig = self.table.item(col_zero_item.row(), WAS_COLUMN)
                    orig.setData(Qt.ItemDataRole.DisplayRole, '')
        self.table.editItem(item)

    def delete_pressed(self):
        if self.table.currentColumn() == VALUE_COLUMN:
            self.delete_tags()
            return
        if not confirm(
            '<p>'+_('Are you sure you want to delete the selected links? '
                    'There is no undo.')+'<br>',
            'tag_list_editor_link_delete'):
            return
        for item in self.table.selectedItems():
            item.setText('')

    def delete_tags(self):
        # This check works because we ensure that the selection is in only one column
        if self.table.currentItem().column() != VALUE_COLUMN:
            return
        # We know the selected items are in column zero
        deletes = self.table.selectedItems()
        if not deletes:
            error_dialog(self, _('No items selected'),
                         _('You must select at least one item from the list.')).exec()
            return
        to_del = []
        for item in deletes:
            if not item.is_deleted:
                to_del.append(item)

        if to_del:
            ct = ', '.join([str(item.text()) for item in to_del])
            if not confirm(
                '<p>'+_('Are you sure you want to delete the following items?')+'<br>'+ct,
                'tag_list_editor_delete'):
                return

        row = self.table.row(deletes[0])
        with block_signals(self.table):
            for item in deletes:
                id_ = int(item.data(Qt.ItemDataRole.UserRole))
                self.to_delete.add(id_)
                item.set_is_deleted(True)
                row = item.row()
                orig = self.table.item(row, WAS_COLUMN)
                orig.setData(Qt.ItemDataRole.DisplayRole, item.initial_text())
                link = self.table.item(row, LINK_COLUMN)
                link.setFlags(link.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                note = self.table.item(row, NOTES_COLUMN)
                note.setFlags(link.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
        if row >= self.table.rowCount():
            row = self.table.rowCount() - 1
        if row >= 0:
            self.table.scrollToItem(self.table.item(row, VALUE_COLUMN))

    def record_sort(self, section):
        # Note what sort was done so we can redo it when the table is rebuilt
        sort_name = self.sort_names[section]
        sort_order_attr = sort_name + '_order'
        setattr(self, sort_order_attr, 1 - getattr(self, sort_order_attr))
        self.last_sorted_by = sort_name

    def save_geometry(self):
        gprefs['general_category_editor_row_height'] = self.table.verticalHeader().defaultSectionSize()
        gprefs['tag_list_editor_table_widths'] = self.table_column_widths
        super().save_geometry(gprefs, 'tag_list_editor_dialog_geometry')

    def accepted(self):
        for t in self.all_tags.values():
            if t['is_deleted']:
                continue
            if t['key'] in self.to_rename:
                name = self.to_rename[t['key']]
            else:
                name = t['cur_name']
            self.links[name] = self.current_links.get(t['key'], '')
        self.save_geometry()

    def rejected(self):
        self.notes_utilities.restore_all_notes()
        self.save_geometry()
