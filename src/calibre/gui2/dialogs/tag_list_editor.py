#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>


from functools import partial
from qt.core import (
    QAbstractItemView, QAction, QApplication, QCheckBox, QColor, QDialog,
    QDialogButtonBox, QEvent, QFrame, QHBoxLayout, QIcon, QItemDelegate, QLabel, QMenu,
    QSize, Qt, QTableWidgetItem, QTimer, QToolButton, QWidget, pyqtSignal, sip,
)

from calibre import sanitize_file_name
from calibre.gui2 import error_dialog, gprefs, question_dialog, choose_files, choose_save_file
from calibre.gui2.actions.show_quickview import get_quickview_action_plugin
from calibre.gui2.complete2 import EditWithComplete
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.edit_category_notes import EditNoteDialog
from calibre.gui2.dialogs.tag_list_editor_ui import Ui_TagListEditor
from calibre.gui2.dialogs.tag_list_editor_table_widget import TleTableWidget
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
            self.setIcon(QIcon.ic('trash.png'))
        else:
            self.setIcon(QIcon())
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


class EditColumnDelegate(QItemDelegate):
    editing_finished = pyqtSignal(int)
    editing_started  = pyqtSignal(int)

    def __init__(self, table, check_for_deleted_items):
        QItemDelegate.__init__(self)
        self.table = table
        self.completion_data = None
        self.check_for_deleted_items = check_for_deleted_items

    def set_completion_data(self, data):
        self.completion_data = data

    def createEditor(self, parent, option, index):
        if index.column() == 0:
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
        self.editing_started.emit(index.row())
        editor = EnLineEdit(parent)
        editor.setClearButtonEnabled(True)
        return editor

    def destroyEditor(self, editor, index):
        self.editing_finished.emit(index.row())
        QItemDelegate.destroyEditor(self, editor, index)


# These My... classes are needed to make context menus work on disabled widgets

def event(ev, me=None, super_class=None, context_menu_handler=None):
    if not me.isEnabled() and ev.type() == QEvent.MouseButtonRelease:
        if ev.button() == Qt.MouseButton.RightButton:
            # let the event finish before the context menu is opened.
            QTimer.singleShot(0, partial(context_menu_handler, ev.position().toPoint()))
            return True
    # if the widget is enabled then it handles its own context menu events
    return super_class.event(ev)


class MyToolButton(QToolButton):

    def __init__(self, context_menu_handler):
        QToolButton.__init__(self)
        self.event = partial(event, me=self, super_class=super(), context_menu_handler=context_menu_handler)


class MyCheckBox(QCheckBox):

    def __init__(self, context_menu_handler):
        QCheckBox.__init__(self)
        self.event = partial(event, me=self, super_class=super(), context_menu_handler=context_menu_handler)


class NotesItemWidget(QWidget):
    '''
    This is a self-contained widget for manipulating notes. It can be used in a
    table (as a cellWidget) or in a layout. It currently contains a check box
    indicating that the item has a note, and buttons to edit/create or delete a
    note, or undo a deletion.
    '''

    '''
    This signal is emitted when a note is edited, after the notes editor
    returns, or deleted. It is provided in case the using class wants to know if
    a note has possibly changed. If not then using this signal isn't required.
    Parameters: self (this widget), field, item_id, note, db (new_api)
    '''
    note_edited = pyqtSignal(object, object, object, object, object)

    edit_icon = QIcon.ic('edit_input.png')
    delete_icon = QIcon.ic('trash.png')
    undo_delete_icon = QIcon.ic('edit-undo.png')
    export_icon = QIcon.ic('forward.png')
    import_icon = QIcon.ic('back.png')

    def __init__(self, db, field, item_id):
        '''
        :param db: A database instance, either old or new api
        :param field: the lookup name of a field
        :param item_id: Either the numeric item_id of an item in the field or
            the item's string value
        '''
        super().__init__()
        self.db = db = db.new_api
        self.field = field
        if isinstance(item_id, str):
            self.item_id = db.get_item_id(field, item_id)
            if self.item_id is None:
                raise ValueError(f"The item {item_id} doesn't exist")
        else:
            self.item_id = item_id
        self.item_val = db.get_item_name(self.field, self.item_id)
        self.can_undo = False

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        l = QHBoxLayout()
        l.setContentsMargins(2, 0, 0, 0)
        self.setLayout(l)
        cb = self.cb = MyCheckBox(self.show_context_menu)
        cb.setEnabled(False)
        l.addWidget(cb)

        self.buttons = {}
        for button_data in (('edit', 'Edit or create the note. Changes cannot be undone or cancelled'),
                            ('delete', 'Delete the note'),
                            ('undo_delete', 'Undo the deletion')):
            button_name = button_data[0]
            tool_tip = button_data[1]
            b = self.buttons[button_name] = MyToolButton(self.show_context_menu)
            b.setIcon(getattr(self, button_name + '_icon'))
            b.setToolTip(tool_tip)
            b.clicked.connect(getattr(self, 'do_' + button_name))
            b.setContentsMargins(0, 0, 0, 0)
            l.addWidget(b)
        l.addStretch(3)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.set_checked()
        self.customContextMenuRequested.connect(self.show_context_menu)

    @classmethod
    def get_item_id(cls, db, field: str, value: str):
        return db.new_api.get_item_id(field, value)

    def show_context_menu(self, point):
        m = QMenu()
        ac = m.addAction(self.edit_icon, _('Edit note') if self.cb.isChecked() else _('Create note'))
        ac.triggered.connect(self.do_edit)

        ac = m.addAction(self.delete_icon, _('Delete note'))
        ac.setEnabled(self.cb.isChecked())
        ac.triggered.connect(self.do_delete)

        ac = m.addAction(self.undo_delete_icon, _('Undo delete'))
        ac.setEnabled(self.can_undo)
        ac.triggered.connect(self.do_undo_delete)

        ac = m.addAction(self.export_icon, _('Export note to a file'))
        ac.setEnabled(self.cb.isChecked())
        ac.triggered.connect(self.do_export)

        ac = m.addAction(self.import_icon, _('Import note from a file'))
        ac.setEnabled(not self.cb.isChecked())
        ac.triggered.connect(self.do_import)

        m.exec(self.mapToGlobal(point))

    def do_edit(self):
        accepted = EditNoteDialog(self.field, self.item_id, self.db).exec()
        # Continue to allow an undo if it was allowed before and the dialog was cancelled.
        self.can_undo = not accepted and self.can_undo
        self.set_checked()

    def do_delete(self):
        self.db.set_notes_for(self.field, self.item_id, '')
        self.can_undo = True
        self.set_checked()

    def do_undo_delete(self):
        if self.can_undo:
            self.db.unretire_note_for(self.field, self.item_id)
            self.can_undo = False
            self.set_checked()

    def do_export(self):
        dest = choose_save_file(self, 'save-exported-note', _('Export note to a file'),
                                filters=[(_('HTML files'), ['html'])],
                                initial_filename=f'{sanitize_file_name(self.item_val)}.html',
                                all_files=False)
        if dest:
            html = self.db.export_note(self.field, self.item_id)
            with open(dest, 'wb') as f:
                f.write(html.encode('utf-8'))

    def do_import(self):
        src = choose_files(self, 'load-imported-note', _('Import note from a file'),
                           filters=[(_('HTML files'), ['html'])],
                           all_files=False, select_only_single_file=True)
        if src:
            self.db.import_note(self.field, self.item_id, src[0])
            self.can_undo = False
            self.set_checked()

    def set_checked(self):
        notes = self.db.notes_for(self.field, self.item_id)
        t = bool(notes)
        self.cb.setChecked(t)
        self.buttons['delete'].setEnabled(t)
        self.buttons['undo_delete'].setEnabled(self.can_undo)
        self.note_edited.emit(self, self.field, self.item_id, notes, self.db)

    def is_checked(self):
        # returns True if the checkbox is checked, meaning the note contains text
        return self.cb.isChecked()


class TagListEditor(QDialog, Ui_TagListEditor):

    VALUE_COLUMN = 0
    LINK_COLUMN = 3
    NOTES_COLUMN = 4

    def __init__(self, window, cat_name, tag_to_match, get_book_ids, sorter,
                 ttm_is_first_letter=False, category=None, fm=None, link_map=None):
        QDialog.__init__(self, window)
        Ui_TagListEditor.__init__(self)
        self.setupUi(self)
        self.verticalLayout_2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search_box.setMinimumContentsLength(25)
        self.link_map = link_map

        # Put the category name into the title bar
        t = self.windowTitle()
        self.category_name = cat_name
        self.category = category
        self.setWindowTitle(t + ' (' + cat_name + ')')
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

        self.ordered_tags = []
        self.sorter = sorter
        self.get_book_ids = get_book_ids
        self.text_before_editing = ''

        self.sort_names = ('name', 'count', 'was', 'link')
        self.last_sorted_by = 'name'
        self.name_order = self.count_order = self.was_order = self.link_order = 0

        if prefs['case_sensitive']:
            self.string_contains = contains
        else:
            self.string_contains = self.case_insensitive_compare

        self.delete_button.clicked.connect(self.delete_tags)
        self.rename_button.clicked.connect(self.rename_tag)
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
        self.apply_vl_checkbox.clicked.connect(self.vl_box_changed)

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

    def show_context_menu(self, point):
        idx = self.table.indexAt(point)
        if idx.column() != self.VALUE_COLUMN:
            return
        m = self.au_context_menu = QMenu(self)

        item = self.table.itemAt(point)
        disable_copy_paste_search = len(self.table.selectedItems()) != 1 or item.is_deleted
        ca = m.addAction(_('Copy'))
        ca.triggered.connect(partial(self.copy_to_clipboard, item))
        ca.setIcon(QIcon.ic('edit-copy.png'))
        if disable_copy_paste_search:
            ca.setEnabled(False)
        ca = m.addAction(_('Paste'))
        ca.setIcon(QIcon.ic('edit-paste.png'))
        ca.triggered.connect(partial(self.paste_from_clipboard, item))
        if disable_copy_paste_search:
            ca.setEnabled(False)
        ca = m.addAction(_('Undo'))
        ca.setIcon(QIcon.ic('edit-undo.png'))
        ca.triggered.connect(self.undo_edit)
        ca.setEnabled(False)
        for item in self.table.selectedItems():
            if (item.text() != self.original_names[int(item.data(Qt.ItemDataRole.UserRole))] or item.is_deleted):
                ca.setEnabled(True)
                break
        ca = m.addAction(_('Edit'))
        ca.setIcon(QIcon.ic('edit_input.png'))
        ca.triggered.connect(self.rename_tag)
        ca = m.addAction(_('Delete'))
        ca.setIcon(QIcon.ic('trash.png'))
        ca.triggered.connect(self.delete_tags)
        item_name = str(item.text())
        ca = m.addAction(_('Search for {}').format(item_name))
        ca.setIcon(QIcon.ic('search.png'))
        ca.triggered.connect(partial(self.set_search_text, item_name))
        item_name = str(item.text())
        ca = m.addAction(_('Filter by {}').format(item_name))
        ca.setIcon(QIcon.ic('filter.png'))
        ca.triggered.connect(partial(self.set_filter_text, item_name))
        if self.category is not None:
            ca = m.addAction(_("Search the library for {0}").format(item_name))
            ca.setIcon(QIcon.ic('lt.png'))
            ca.triggered.connect(partial(self.search_for_books, item))
            if disable_copy_paste_search:
                ca.setEnabled(False)
        if self.table.state() == QAbstractItemView.State.EditingState:
            m.addSeparator()
            case_menu = QMenu(_('Change case'))
            case_menu.setIcon(QIcon.ic('font_size_larger.png'))
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
        m.exec(self.table.mapToGlobal(point))

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
        self.table.blockSignals(True)
        for item in items:
            item.setText(func(str(item.text())))
        self.table.blockSignals(False)

    def swap_case(self, txt):
        return txt.swapcase()

    def vl_box_changed(self):
        self.search_item_row = -1
        self.fill_in_table(None, None, False)

    def do_search(self):
        self.not_found_label.setVisible(False)
        find_text = str(self.search_box.currentText())
        if not find_text:
            return
        for _ in range(0, self.table.rowCount()):
            r = self.search_item_row = (self.search_item_row + 1) % self.table.rowCount()
            if self.string_contains(find_text, self.table.item(r, self.VALUE_COLUMN).text()):
                self.table.setCurrentItem(self.table.item(r, self.VALUE_COLUMN))
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
            self.gridlayout.removeWidget(self.table)
            sip.delete(self.table)
        self.table = TleTableWidget(self)
        self.gridlayout.addWidget(self.table, 2, 1, 1, 4)

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

        self.edit_delegate = EditColumnDelegate(self.table, self.check_for_deleted_items)
        self.edit_delegate.editing_finished.connect(self.stop_editing)
        self.edit_delegate.editing_started.connect(self.start_editing)
        self.table.setItemDelegateForColumn(self.VALUE_COLUMN, self.edit_delegate)
        self.table.setItemDelegateForColumn(self.LINK_COLUMN, self.edit_delegate)

        self.table.delete_pressed.connect(self.delete_pressed)
        self.table.itemDoubleClicked.connect(self._rename_tag)
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

    def row_height_changed(self, row, old, new):
        self.table.verticalHeader().setDefaultSectionSize(new)

    def fill_in_table(self, tags, tag_to_match, ttm_is_first_letter):
        self.create_table()

        data = self.get_book_ids(self.apply_vl_checkbox.isChecked())
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
        self.table.blockSignals(True)
        self.name_col = QTableWidgetItem(self.category_name)
        self.table.setHorizontalHeaderItem(self.VALUE_COLUMN, self.name_col)
        self.count_col = QTableWidgetItem(_('Count'))
        self.table.setHorizontalHeaderItem(1, self.count_col)
        self.was_col = QTableWidgetItem(_('Was'))
        self.table.setHorizontalHeaderItem(2, self.was_col)
        self.link_col = QTableWidgetItem(_('Link'))
        self.table.setHorizontalHeaderItem(self.LINK_COLUMN, self.link_col)
        self.link_col = QTableWidgetItem(_('Notes'))
        self.table.setHorizontalHeaderItem(4, self.link_col)

        self.table.setRowCount(len(tags))
        for row,tag in enumerate(tags):
            item = NameTableWidgetItem(self.sorter)
            is_deleted = self.all_tags[tag]['is_deleted']
            item.set_is_deleted(is_deleted)
            _id = self.all_tags[tag]['key']
            item.setData(Qt.ItemDataRole.UserRole, _id)
            item.set_initial_text(tag)
            if _id in self.to_rename:
                item.setText(self.to_rename[_id])
            else:
                item.setText(tag)
            if self.is_enumerated and str(item.text()) not in self.enum_permitted_values:
                item.setBackground(QColor('#FF2400'))
                item.setToolTip(
                    '<p>' +
                    _("This is not one of this column's permitted values ({0})"
                      ).format(', '.join(self.enum_permitted_values)) + '</p>')
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self.VALUE_COLUMN, item)
            if select_item is None:
                if ttm_is_first_letter:
                    if primary_startswith(tag, tag_to_match):
                        select_item = item
                elif tag == tag_to_match:
                    select_item = item
            item = CountTableWidgetItem(self.all_tags[tag]['count'])
            # only the name column can be selected
            item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
            self.table.setItem(row, 1, item)

            item = QTableWidgetItem()
            item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
            if _id in self.to_rename or _id in self.to_delete:
                item.setData(Qt.ItemDataRole.DisplayRole, tag)
            self.table.setItem(row, 2, item)

            item = QTableWidgetItem()
            if self.link_map is None:
                item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                item.setText(_('no links available'))
            else:
                if is_deleted:
                    item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                    item.setIcon(QIcon.ic('trash.png'))
                else:
                    item.setFlags(item.flags() | (Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
                    item.setIcon(QIcon())
                item.setText(self.link_map.get(tag, ''))
            self.table.setItem(row, self.LINK_COLUMN, item)

            if self.category is not None:
                from calibre.gui2.ui import get_gui
                nw = NotesItemWidget(get_gui().current_db, self.category, _id)
                self.table.setCellWidget(row, 4, nw)

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
        self.table.blockSignals(False)

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

    def save_geometry(self):
        gprefs['general_category_editor_row_height'] = self.table.verticalHeader().defaultSectionSize()
        gprefs['tag_list_editor_table_widths'] = self.table_column_widths
        super().save_geometry(gprefs, 'tag_list_editor_dialog_geometry')

    def start_editing(self, on_row):
        current_column = self.table.currentItem().column()
        # We don't support editing multiple link rows at the same time. Use
        # the current cell.
        if current_column != self.VALUE_COLUMN:
            self.table.setCurrentItem(self.table.item(on_row, current_column))
        items = self.table.selectedItems()
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        for item in items:
            if item.row() != on_row:
                item.set_placeholder(_('Editing...'))
            else:
                self.text_before_editing = item.text()
        self.table.blockSignals(False)

    def stop_editing(self, on_row):
        # This works because the link field doesn't support editing on multiple
        # lines, so the on_row check will always be false.
        items = self.table.selectedItems()
        self.table.blockSignals(True)
        for item in items:
            if item.row() != on_row and item.is_placeholder:
                item.reset_placeholder()
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

    def finish_editing(self, edited_item):
        if edited_item.column() != self.VALUE_COLUMN:
            # Nothing to do for link fields
            return
        if not edited_item.text():
            error_dialog(self, _('Item is blank'), _(
                'An item cannot be set to nothing. Delete it instead.'), show=True)
            self.table.blockSignals(True)
            edited_item.setText(self.text_before_editing)
            self.table.blockSignals(False)
            return
        new_text = str(edited_item.text())
        if self.is_enumerated and new_text not in self.enum_permitted_values:
            error_dialog(self, _('Item is not a permitted value'), '<p>' + _(
                "This column has a fixed set of permitted values. The entered "
                "text must be one of ({0}).").format(', '.join(self.enum_permitted_values)) +
                '</p>', show=True)
            self.table.blockSignals(True)
            edited_item.setText(self.text_before_editing)
            self.table.blockSignals(False)
            return

        items = self.table.selectedItems()
        self.table.blockSignals(True)
        for item in items:
            id_ = int(item.data(Qt.ItemDataRole.UserRole))
            self.to_rename[id_] = new_text
            orig = self.table.item(item.row(), 2)
            item.setText(new_text)
            orig.setData(Qt.ItemDataRole.DisplayRole, item.initial_text())
        self.table.blockSignals(False)

    def undo_edit(self):
        col_zero_items = (self.table.item(item.row(), self.VALUE_COLUMN) for item in self.table.selectedItems())
        if not col_zero_items:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of available items.')).exec()
            return

        if not confirm(
            _('Do you really want to undo your changes?'),
            'tag_list_editor_undo'):
            return
        self.table.blockSignals(True)
        for col_zero_item in col_zero_items:
            col_zero_item.setText(col_zero_item.initial_text())
            col_zero_item.set_is_deleted(False)
            self.to_delete.discard(int(col_zero_item.data(Qt.ItemDataRole.UserRole)))
            self.to_rename.pop(int(col_zero_item.data(Qt.ItemDataRole.UserRole)), None)
            row = col_zero_item.row()
            self.table.item(row, 2).setData(Qt.ItemDataRole.DisplayRole, '')
            item = self.table.item(row, self.LINK_COLUMN)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable)
            item.setIcon(QIcon())
        self.table.blockSignals(False)

    def selection_changed(self):
        if self.table.currentIndex().isValid():
            col = self.table.currentIndex().column()
            self.table.blockSignals(True)
            if col == self.NOTES_COLUMN:
                self.table.setCurrentIndex(self.table.currentIndex())
            else:
                for itm in (item for item in self.table.selectedItems() if item.column() != col):
                    itm.setSelected(False)
            self.table.blockSignals(False)

    def check_for_deleted_items(self, show_error=False):
        for col_zero_item in (self.table.item(item.row(), self.VALUE_COLUMN) for item in self.table.selectedItems()):
            if col_zero_item.is_deleted:
                if show_error:
                    error_dialog(self, _('Selection contains deleted items'),
                                '<p>'+_('The selection contains deleted items. You '
                                        'must undelete them before editing.')+'<br>',
                                show=True)
                return True
        return False

    def rename_tag(self):
        if self.table.currentColumn() != self.VALUE_COLUMN:
            return
        item = self.table.item(self.table.currentRow(), self.VALUE_COLUMN)
        self._rename_tag(item)

    def _rename_tag(self, item):
        if item is None:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of available items.')).exec()
            return
        if self.check_for_deleted_items():
            if not question_dialog(self, _('Undelete items?'),
                   '<p>'+_('Items must be undeleted to continue. Do you want '
                           'to do this?')+'<br>'):
                return
        self.table.blockSignals(True)
        for col_zero_item in (self.table.item(item.row(), self.VALUE_COLUMN) for item in self.table.selectedItems()):
            # undelete any deleted items
            if col_zero_item.is_deleted:
                col_zero_item.set_is_deleted(False)
                self.to_delete.discard(int(col_zero_item.data(Qt.ItemDataRole.UserRole)))
                orig = self.table.item(col_zero_item.row(), 2)
                orig.setData(Qt.ItemDataRole.DisplayRole, '')
        self.table.blockSignals(False)
        self.table.editItem(item)

    def delete_pressed(self):
        if self.table.currentColumn() == self.VALUE_COLUMN:
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
        if self.table.currentItem().column() != self.VALUE_COLUMN:
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
        self.table.blockSignals(True)
        for item in deletes:
            id_ = int(item.data(Qt.ItemDataRole.UserRole))
            self.to_delete.add(id_)
            item.set_is_deleted(True)
            row = item.row()
            orig = self.table.item(row, 2)
            orig.setData(Qt.ItemDataRole.DisplayRole, item.initial_text())
            link = self.table.item(row, self.LINK_COLUMN)
            link.setFlags(link.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
            link.setIcon(QIcon.ic('trash.png'))
        self.table.blockSignals(False)
        if row >= self.table.rowCount():
            row = self.table.rowCount() - 1
        if row >= 0:
            self.table.scrollToItem(self.table.item(row, self.VALUE_COLUMN))

    def record_sort(self, section):
        # Note what sort was done so we can redo it when the table is rebuilt
        sort_name = self.sort_names[section]
        sort_order_attr = sort_name + '_order'
        setattr(self, sort_order_attr, 1 - getattr(self, sort_order_attr))
        self.last_sorted_by = sort_name

    def accepted(self):
        # We don't bother with cleaning out the deleted links because the db
        # interface ignores links for values that don't exist. The caller must
        # process deletes and renames first so the names are correct.
        self.links = {self.table.item(r, self.VALUE_COLUMN).text():self.table.item(r, self.LINK_COLUMN).text()
                      for r in range(self.table.rowCount())}
        self.save_geometry()

    def rejected(self):
        self.save_geometry()
