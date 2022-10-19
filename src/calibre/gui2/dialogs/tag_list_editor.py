#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>


from functools import partial

from qt.core import (Qt, QDialog, QTableWidgetItem, QIcon, QSize, QAbstractItemView,
                      QDialogButtonBox, QItemDelegate, QApplication,
                      pyqtSignal, QAction, QFrame, QLabel, QTimer, QMenu, QColor)

from calibre.gui2.actions.show_quickview import get_quickview_action_plugin
from calibre.gui2.complete2 import EditWithComplete
from calibre.gui2.dialogs.tag_list_editor_ui import Ui_TagListEditor
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.widgets import EnLineEdit
from calibre.gui2 import question_dialog, error_dialog, gprefs
from calibre.utils.config import prefs
from calibre.utils.icu import contains, primary_contains, primary_startswith, capitalize
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

    def __init__(self, table):
        QItemDelegate.__init__(self)
        self.table = table
        self.completion_data = None

    def set_completion_data(self, data):
        self.completion_data = data

    def createEditor(self, parent, option, index):
        self.editing_started.emit(index.row())
        if index.column() == 0:
            self.item = self.table.itemFromIndex(index)
            if self.item.is_deleted:
                return None
            if self.completion_data:
                editor = EditWithComplete(parent)
                editor.set_separator(None)
                editor.update_items_cache(self.completion_data)
            else:
                editor = EnLineEdit(parent)
            return editor
        return None

    def destroyEditor(self, editor, index):
        self.editing_finished.emit(index.row())
        QItemDelegate.destroyEditor(self, editor, index)


class TagListEditor(QDialog, Ui_TagListEditor):

    def __init__(self, window, cat_name, tag_to_match, get_book_ids, sorter,
                 ttm_is_first_letter=False, category=None, fm=None):
        QDialog.__init__(self, window)
        Ui_TagListEditor.__init__(self)
        self.setupUi(self)
        self.verticalLayout_2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search_box.setMinimumContentsLength(25)

        # Put the category name into the title bar
        t = self.windowTitle()
        self.category_name = cat_name
        self.category = category
        self.setWindowTitle(t + ' (' + cat_name + ')')
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        # Get saved geometry info
        try:
            self.table_column_widths = \
                        gprefs.get('tag_list_editor_table_widths', None)
        except:
            pass

        # initialization
        self.to_rename = {}
        self.to_delete = set()
        self.all_tags = {}
        self.original_names = {}

        self.ordered_tags = []
        self.sorter = sorter
        self.get_book_ids = get_book_ids
        self.text_before_editing = ''

        # Capture clicks on the horizontal header to sort the table columns
        hh = self.table.horizontalHeader()
        hh.sectionResized.connect(self.table_column_resized)
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self.do_sort)
        hh.setSortIndicatorShown(True)

        self.last_sorted_by = 'name'
        self.name_order = 0
        self.count_order = 1
        self.was_order = 1

        self.edit_delegate = EditColumnDelegate(self.table)
        self.edit_delegate.editing_finished.connect(self.stop_editing)
        self.edit_delegate.editing_started.connect(self.start_editing)
        self.table.setItemDelegateForColumn(0, self.edit_delegate)

        if prefs['case_sensitive']:
            self.string_contains = contains
        else:
            self.string_contains = self.case_insensitive_compare

        self.delete_button.clicked.connect(self.delete_tags)
        self.table.delete_pressed.connect(self.delete_pressed)
        self.rename_button.clicked.connect(self.rename_tag)
        self.undo_button.clicked.connect(self.undo_edit)
        self.table.itemDoubleClicked.connect(self._rename_tag)
        self.table.itemChanged.connect(self.finish_editing)

        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText(_('&OK'))
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText(_('&Cancel'))
        self.buttonBox.accepted.connect(self.accepted)

        self.search_box.initialize('tag_list_search_box_' + cat_name)
        le = self.search_box.lineEdit()
        ac = le.findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
        if ac is not None:
            ac.triggered.connect(self.clear_search)
        self.search_box.textChanged.connect(self.search_text_changed)
        self.search_button.clicked.connect(self.do_search)
        self.search_button.setDefault(True)
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

        self.filter_box.initialize('tag_list_filter_box_' + cat_name)
        le = self.filter_box.lineEdit()
        ac = le.findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
        if ac is not None:
            ac.triggered.connect(self.clear_filter)
        le.returnPressed.connect(self.do_filter)
        self.filter_button.clicked.connect(self.do_filter)

        self.apply_vl_checkbox.clicked.connect(self.vl_box_changed)

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)

        self.restore_geometry(gprefs, 'tag_list_editor_dialog_geometry')
        self.is_enumerated = False
        if fm:
            if fm['datatype'] == 'enumeration':
                self.is_enumerated = True
                self.enum_permitted_values = fm.get('display', {}).get('enum_values', None)
        # Add the data
        self.search_item_row = -1
        self.fill_in_table(None, tag_to_match, ttm_is_first_letter)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def sizeHint(self):
        return super().sizeHint() + QSize(150, 100)

    def show_context_menu(self, point):
        idx = self.table.indexAt(point)
        if idx.column() != 0:
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
            if self.string_contains(find_text, self.table.item(r, 0).text()):
                self.table.setCurrentItem(self.table.item(r, 0))
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

    def fill_in_table(self, tags, tag_to_match, ttm_is_first_letter):
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
        self.table.clear()
        self.table.setColumnCount(3)
        self.name_col = QTableWidgetItem(self.category_name)
        self.table.setHorizontalHeaderItem(0, self.name_col)
        self.count_col = QTableWidgetItem(_('Count'))
        self.table.setHorizontalHeaderItem(1, self.count_col)
        self.was_col = QTableWidgetItem(_('Was'))
        self.table.setHorizontalHeaderItem(2, self.was_col)

        self.table.setRowCount(len(tags))
        for row,tag in enumerate(tags):
            item = NameTableWidgetItem(self.sorter)
            item.set_is_deleted(self.all_tags[tag]['is_deleted'])
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
            self.table.setItem(row, 0, item)
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

        if self.last_sorted_by == 'name':
            self.table.sortByColumn(0, Qt.SortOrder(self.name_order))
        elif self.last_sorted_by == 'count':
            self.table.sortByColumn(1, Qt.SortOrder(self.count_order))
        else:
            self.table.sortByColumn(2, Qt.SortOrder(self.was_order))

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

    def table_column_resized(self, col, old, new):
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
        gprefs['tag_list_editor_table_widths'] = self.table_column_widths
        super().save_geometry(gprefs, 'tag_list_editor_dialog_geometry')

    def start_editing(self, on_row):
        items = self.table.selectedItems()
        self.table.blockSignals(True)
        for item in items:
            if item.row() != on_row:
                item.set_placeholder(_('Editing...'))
            else:
                self.text_before_editing = item.text()
        self.table.blockSignals(False)

    def stop_editing(self, on_row):
        items = self.table.selectedItems()
        self.table.blockSignals(True)
        for item in items:
            if item.row() != on_row and item.is_placeholder:
                item.reset_placeholder()
        self.table.blockSignals(False)

    def finish_editing(self, edited_item):
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
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of available items.')).exec()
            return

        if not confirm(
            _('Do you really want to undo your changes?'),
            'tag_list_editor_undo'):
            return
        self.table.blockSignals(True)
        for idx in indexes:
            row = idx.row()
            item = self.table.item(row, 0)
            item.setText(item.initial_text())
            item.set_is_deleted(False)
            self.to_delete.discard(int(item.data(Qt.ItemDataRole.UserRole)))
            self.to_rename.pop(int(item.data(Qt.ItemDataRole.UserRole)), None)
            self.table.item(row, 2).setData(Qt.ItemDataRole.DisplayRole, '')
        self.table.blockSignals(False)

    def rename_tag(self):
        item = self.table.item(self.table.currentRow(), 0)
        self._rename_tag(item)

    def _rename_tag(self, item):
        if item is None:
            error_dialog(self, _('No item selected'),
                         _('You must select one item from the list of available items.')).exec()
            return
        for col_zero_item in self.table.selectedItems():
            if col_zero_item.is_deleted:
                if not question_dialog(self, _('Undelete items?'),
                       '<p>'+_('Items must be undeleted to continue. Do you want '
                               'to do this?')+'<br>'):
                    return
        self.table.blockSignals(True)
        for col_zero_item in self.table.selectedItems():
            # undelete any deleted items
            if col_zero_item.is_deleted:
                col_zero_item.set_is_deleted(False)
                self.to_delete.discard(int(col_zero_item.data(Qt.ItemDataRole.UserRole)))
                orig = self.table.item(col_zero_item.row(), 2)
                orig.setData(Qt.ItemDataRole.DisplayRole, '')
        self.table.blockSignals(False)
        self.table.editItem(item)

    def delete_pressed(self):
        if self.table.currentColumn() == 0:
            self.delete_tags()

    def delete_tags(self):
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
            orig = self.table.item(item.row(), 2)
            orig.setData(Qt.ItemDataRole.DisplayRole, item.initial_text())
        self.table.blockSignals(False)
        if row >= self.table.rowCount():
            row = self.table.rowCount() - 1
        if row >= 0:
            self.table.scrollToItem(self.table.item(row, 0))

    def do_sort(self, section):
        (self.do_sort_by_name, self.do_sort_by_count, self.do_sort_by_was)[section]()

    def do_sort_by_name(self):
        self.name_order = 1 - self.name_order
        self.last_sorted_by = 'name'
        self.table.sortByColumn(0, Qt.SortOrder(self.name_order))

    def do_sort_by_count(self):
        self.count_order = 1 - self.count_order
        self.last_sorted_by = 'count'
        self.table.sortByColumn(1, Qt.SortOrder(self.count_order))

    def do_sort_by_was(self):
        self.was_order = 1 - self.was_order
        self.last_sorted_by = 'count'
        self.table.sortByColumn(2, Qt.SortOrder(self.was_order))

    def accepted(self):
        self.save_geometry()
