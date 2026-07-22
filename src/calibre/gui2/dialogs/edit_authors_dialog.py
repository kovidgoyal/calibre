#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

from contextlib import contextmanager
from functools import partial

from qt.core import (
    QAbstractItemView,
    QAction,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QIcon,
    QLabel,
    QMenu,
    QStyledItemDelegate,
    Qt,
    QTableWidgetItem,
    QTimer,
)

from calibre.ebooks.metadata import author_to_author_sort, string_to_authors
from calibre.gui2 import error_dialog, gprefs
from calibre.gui2.dialogs.edit_authors_dialog_ui import Ui_EditAuthorsDialog
from calibre.gui2.dialogs.tag_list_editor import NotesTableWidgetItem, NotesUtilities
from calibre.utils.config import prefs
from calibre.utils.config_base import tweaks
from calibre.utils.icu import contains, primary_contains, primary_startswith, sort_key
from calibre.utils.icu import lower as icu_lower
from calibre.utils.icu import upper as icu_upper
from calibre.utils.localization import _

QT_HIDDEN_CLEAR_ACTION = '_q_qlineeditclearaction'


class TableItem(QTableWidgetItem):
    def __init__(self, txt, skey=None):
        QTableWidgetItem.__init__(self, txt)
        self.sort_key = sort_key(str(txt)) if skey is None else skey

    def setText(self, atext):
        self.sort_key = sort_key(str(atext))
        QTableWidgetItem.setText(self, atext)

    def set_sort_key(self):
        self.sort_key = sort_key(str(self.text()))

    def __ge__(self, other):
        return self.sort_key >= other.sort_key

    def __lt__(self, other):
        return self.sort_key < other.sort_key


class CountTableItem(QTableWidgetItem):
    def __init__(self, val):
        QTableWidgetItem.__init__(self, str(val))
        self.val = val
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setFlags(Qt.ItemFlag.ItemIsEnabled)

    def setText(self, atext):
        self.atext = atext
        QTableWidgetItem.setText(self, str(atext))

    def set_sort_key(self):
        pass

    def __ge__(self, other):
        return self.val >= other.val

    def __lt__(self, other):
        return self.val < other.val


AUTHOR_COLUMN = 0
AUTHOR_SORT_COLUMN = 1
COUNTS_COLUMN = 2
LINK_COLUMN = 3
NOTES_COLUMN = 4


class EditColumnDelegate(QStyledItemDelegate):
    def __init__(self, completion_data, table, notes_utilities, item_id_getter):
        super().__init__(table)
        self.table = table
        self.completion_data = completion_data
        self.notes_utilities = notes_utilities
        self.item_id_getter = item_id_getter

    def createEditor(self, parent, option, index):
        if index.column() == AUTHOR_COLUMN:
            if self.completion_data:
                from calibre.gui2.complete2 import EditWithComplete

                editor = EditWithComplete(parent)
                editor.set_separator(None)
                editor.update_items_cache(self.completion_data)
                return editor
        if index.column() == NOTES_COLUMN:
            self.notes_utilities.edit_note(self.table.itemFromIndex(index))
            return None
        if index.column() == COUNTS_COLUMN:
            return None
        from calibre.gui2.widgets import EnLineEdit

        editor = EnLineEdit(parent)
        editor.setClearButtonEnabled(True)
        return editor


class EditAuthorsDialog(QDialog, Ui_EditAuthorsDialog):
    def __init__(self, parent, db, id_to_select, select_sort, select_link, find_aut_func, is_first_letter=False):
        QDialog.__init__(self, parent)
        Ui_EditAuthorsDialog.__init__(self)
        self.setupUi(self)

        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags() & (~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        try:
            self.table_column_widths = gprefs.get('manage_authors_table_widths', None)
            self.restore_geometry(gprefs, 'manage_authors_dialog_geometry')
        except Exception:
            pass

        self.notes_utilities = NotesUtilities(self.table, 'authors', self.get_item_id)

        ok_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        ok_button.setText(_('&OK'))
        cancel_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel)
        assert cancel_button is not None
        cancel_button.setText(_('&Cancel'))
        self.buttonBox.accepted.connect(self.accepted)
        self.buttonBox.rejected.connect(self.rejected)
        self.show_button_layout.setSpacing(0)
        self.show_button_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_all_checkbox.setContentsMargins(0, 0, 0, 0)
        self.apply_all_checkbox.setChecked(True)
        self.apply_vl_checkbox.setContentsMargins(0, 0, 0, 0)
        self.apply_vl_checkbox.toggled.connect(self.use_vl_changed)
        self.apply_selection_checkbox.setContentsMargins(0, 0, 0, 0)
        self.apply_selection_checkbox.toggled.connect(self.apply_selection_box_changed)
        self.edit_current_cell.clicked.connect(self.edit_cell)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.find_aut_func = find_aut_func
        self.table.resizeColumnsToContents()
        if self.table.columnWidth(LINK_COLUMN) < 200:
            self.table.setColumnWidth(LINK_COLUMN, 200)

        # set up the cellChanged signal only after the table is filled
        self.ignore_cell_changed = False
        self.table.cellChanged.connect(self.cell_changed)

        self.recalc_author_sort.clicked.connect(self.do_recalc_author_sort)
        self.auth_sort_to_author.clicked.connect(self.do_auth_sort_to_author)

        # Capture clicks on the horizontal header to sort the table columns
        hh = self.table.horizontalHeader()
        assert hh is not None
        hh.sectionResized.connect(self.table_column_resized)
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self.do_sort)
        hh.setSortIndicatorShown(True)

        vh = self.table.verticalHeader()
        assert vh is not None
        vh.setDefaultSectionSize(gprefs.get('general_category_editor_row_height', vh.defaultSectionSize()))
        vh.sectionResized.connect(self.row_height_changed)

        # set up the search & filter boxes
        self.find_box.initialize('manage_authors_search')
        le = self.find_box.lineEdit()
        assert le is not None
        ac = le.findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
        if ac is not None:
            ac.triggered.connect(self.clear_find)
        le.returnPressed.connect(partial(self.do_find, inverted=False))
        self.find_box.editTextChanged.connect(self.find_text_changed)
        self.find_button.clicked.connect(partial(self.do_find, inverted=False))
        self.find_button.setDefault(True)
        self.find_inverted_button.clicked.connect(partial(self.do_find, inverted=True))

        self.filter_box.initialize('manage_authors_filter')
        le = self.filter_box.lineEdit()
        assert le is not None
        ac = le.findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
        if ac is not None:
            ac.triggered.connect(self.clear_filter)
        le.returnPressed.connect(partial(self.do_filter, inverted=False))
        self.filter_button.clicked.connect(partial(self.do_filter, inverted=False))
        self.filter_inverted_button.clicked.connect(partial(self.do_filter, inverted=True))

        self.not_found_label = l = QLabel(self.table)
        l.setFrameStyle(QFrame.Shape.StyledPanel)
        l.setAutoFillBackground(True)
        l.setText(_('No matches found'))
        l.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        l.resize(l.sizeHint())
        l.move(10, 2)
        l.setVisible(False)
        self.not_found_label_timer = QTimer()
        self.not_found_label_timer.setSingleShot(True)
        self.not_found_label_timer.timeout.connect(self.not_found_label_timer_event, type=Qt.ConnectionType.QueuedConnection)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        self.inverted_filter = False

        # Fetch the data
        self.authors = {}
        self.original_authors = {}
        auts = db.new_api.author_data()
        self.completion_data = []
        counts = db.new_api.get_usage_count_by_id('authors')
        for id_, v in auts.items():
            name = v['name']
            name = name.replace('|', ',')
            self.completion_data.append(name)
            vals = {'name': name, 'sort': v['sort'], 'link': v['link'], 'count': counts.get(id_, 0)}
            self.authors[id_] = vals
            self.original_authors[id_] = vals.copy()

        if prefs['use_primary_find_in_search']:
            self.string_contains = primary_contains
        else:
            self.string_contains = contains

        self.last_sorted_by = 'sort'
        self.author_order = 1
        self.author_sort_order = 0
        self.link_order = 1
        self.notes_order = 1
        self.count_order = 1
        self.table.setItemDelegate(EditColumnDelegate(self.completion_data, self.table, self.notes_utilities, self.get_item_id))
        self.show_table(id_to_select, select_sort, select_link, is_first_letter)

    def edit_cell(self):
        if self.table.currentIndex().isValid():
            self.table.editItem(self.table.currentItem())

    def get_item_id(self, item):
        col_item = self.table.item(item.row(), AUTHOR_COLUMN)
        assert col_item is not None
        return int(col_item.data(Qt.ItemDataRole.UserRole))

    @contextmanager
    def no_cell_changed(self):
        orig = self.ignore_cell_changed
        self.ignore_cell_changed = True
        try:
            yield
        finally:
            self.ignore_cell_changed = orig

    def use_vl_changed(self, x):
        self.show_table(None, None, None, False)

    def apply_selection_box_changed(self, x):
        self.show_table(None, None, None, False)

    def selection_to_apply(self):
        if self.apply_selection_checkbox.isChecked():
            return 'selection'
        if self.apply_vl_checkbox.isChecked():
            return 'virtual_library'
        return None

    def clear_filter(self):
        self.filter_box.setText('')
        self.show_table(None, None, None, False)

    def do_filter(self, inverted):
        self.inverted_filter = inverted
        self.show_table(None, None, None, False)

    def show_table(self, id_to_select, select_sort, select_link, is_first_letter):
        auts_to_show = {t[0] for t in self.find_aut_func(self.selection_to_apply())}
        filter_text = icu_lower(str(self.filter_box.text()))
        if filter_text:
            auts_to_show = {id_ for id_ in auts_to_show if self.string_contains(filter_text, icu_lower(self.authors[id_]['name'])) != self.inverted_filter}

        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(5)

        self.table.setRowCount(len(auts_to_show))
        row = 0
        from calibre.gui2.ui import get_gui

        all_items_that_have_notes = get_gui(fail_if_absent=True).current_db.new_api.get_all_items_that_have_notes('authors')
        for id_, v in self.authors.items():
            if id_ not in auts_to_show:
                continue
            name, sort, link, count = (v['name'], v['sort'], v['link'], v['count'])
            name = name.replace('|', ',')

            name_item = TableItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, id_)
            sort_item = TableItem(sort)
            link_item = TableItem(link)
            count_item = CountTableItem(count)

            self.table.setItem(row, AUTHOR_COLUMN, name_item)
            self.table.setItem(row, AUTHOR_SORT_COLUMN, sort_item)
            self.table.setItem(row, LINK_COLUMN, link_item)
            note_item = NotesTableWidgetItem()
            self.table.setItem(row, NOTES_COLUMN, note_item)
            self.table.setItem(row, COUNTS_COLUMN, count_item)

            self.set_icon(name_item, id_)
            self.set_icon(sort_item, id_)
            self.set_icon(link_item, id_)
            self.notes_utilities.set_icon(note_item, id_, id_ in all_items_that_have_notes)
            row += 1

        headers = {  # this depends on the dict being ordered, which is true from python 3.7
            _('Author'): _('Name of the author'),
            _('Author sort'): _('Value used to sort this author'),
            _('Count'): _('Count of books with this author'),
            _('Link'): _('Link (URL) for this author'),
            _('Notes'): _('Whether this author has a note attached. The icon changes if the note was created or edited'),
        }
        self.table.setHorizontalHeaderLabels(headers.keys())
        for i, tt in enumerate(headers.values()):
            header_item = self.table.horizontalHeaderItem(i)
            assert header_item is not None
            header_item.setToolTip(tt)

        if self.last_sorted_by == 'sort':
            self.author_sort_order = 1 - self.author_sort_order
            self.do_sort_by_author_sort()
        elif self.last_sorted_by == 'author':
            self.author_order = 1 - self.author_order
            self.do_sort_by_author()
        elif self.last_sorted_by == 'link':
            self.link_order = 1 - self.link_order
            self.do_sort_by_link()
        else:
            self.notes_order = 1 - self.notes_order
            self.do_sort_by_notes()

        # Position on the desired item
        select_item = None
        if id_to_select:
            use_as = tweaks['categories_use_field_for_author_name'] == 'author_sort'
            for row in range(len(auts_to_show)):
                _row_au_item = self.table.item(row, AUTHOR_COLUMN)
                assert _row_au_item is not None
                _row_aus_item = self.table.item(row, AUTHOR_SORT_COLUMN)
                assert _row_aus_item is not None
                if is_first_letter:
                    item_txt = str(_row_aus_item.text() if use_as else _row_au_item.text())
                    if primary_startswith(item_txt, id_to_select):
                        select_item = self.table.item(row, AUTHOR_SORT_COLUMN if use_as else 0)
                        break
                elif id_to_select == _row_au_item.data(Qt.ItemDataRole.UserRole):
                    if select_sort:
                        select_item = self.table.item(row, AUTHOR_SORT_COLUMN)
                    elif select_link:
                        select_item = self.table.item(row, LINK_COLUMN)
                    else:
                        select_item = self.table.item(row, AUTHOR_SORT_COLUMN) if use_as else self.table.item(row, AUTHOR_COLUMN)
                    break
        if select_item:
            self.table.setCurrentItem(select_item)
            self.table.setFocus(Qt.FocusReason.OtherFocusReason)
            if select_sort or select_link:
                self.table.editItem(select_item)
            self.start_find_pos = select_item.row() * 2 + select_item.column()
        else:
            self.table.setCurrentCell(0, 0)
            self.find_box.setFocus()
            self.start_find_pos = -1
        self.table.blockSignals(False)
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def row_height_changed(self, row, old, new):
        vh = self.table.verticalHeader()
        assert vh is not None
        vh.blockSignals(True)
        vh.setDefaultSectionSize(new)
        vh.blockSignals(False)

    def save_state(self):
        self.table_column_widths = []
        for c in range(self.table.columnCount()):
            self.table_column_widths.append(self.table.columnWidth(c))
        vh = self.table.verticalHeader()
        assert vh is not None
        gprefs['general_category_editor_row_height'] = vh.sectionSize(0)
        gprefs['manage_authors_table_widths'] = self.table_column_widths
        self.save_geometry(gprefs, 'manage_authors_dialog_geometry')

    def table_column_resized(self, col, old, new):
        self.table_column_widths = []
        for c in range(self.table.columnCount()):
            self.table_column_widths.append(self.table.columnWidth(c))

    def resizeEvent(self, a0=None):
        QDialog.resizeEvent(self, a0)
        if self.table_column_widths is not None:
            for c, w in enumerate(self.table_column_widths):
                self.table.setColumnWidth(c, w)
        else:
            # the vertical scroll bar might not be rendered, so might not yet
            # have a width. Assume 25. Not a problem because user-changed column
            # widths will be remembered
            vh = self.table.verticalHeader()
            assert vh is not None
            w = self.table.width() - 25 - vh.width()
            w //= self.table.columnCount()
            for c in range(self.table.columnCount()):
                self.table.setColumnWidth(c, w)
        self.save_state()

    def get_column_name(self, column):
        return ('name', 'sort', 'count', 'link', 'notes')[column]

    def item_is_modified(self, item, id_):
        sub = self.get_column_name(item.column())
        if sub == 'notes':
            return self.notes_utilities.is_note_modified(id_)
        return item.text() != self.original_authors[id_][sub]

    def show_context_menu(self, point):
        self.context_item = self.table.itemAt(point)
        if self.context_item is None or self.context_item.column() == COUNTS_COLUMN:
            return
        case_menu = QMenu(_('Change case'))
        case_menu.setIcon(QIcon.cached_icon('font_size_larger.png'))
        action_upper_case = case_menu.addAction(_('Upper case'))
        action_lower_case = case_menu.addAction(_('Lower case'))
        action_swap_case = case_menu.addAction(_('Swap case'))
        action_title_case = case_menu.addAction(_('Title case'))
        action_capitalize = case_menu.addAction(_('Capitalize'))
        assert action_upper_case is not None
        assert action_lower_case is not None
        assert action_swap_case is not None
        assert action_title_case is not None
        assert action_capitalize is not None

        action_upper_case.triggered.connect(self.upper_case)
        action_lower_case.triggered.connect(self.lower_case)
        action_swap_case.triggered.connect(self.swap_case)
        action_title_case.triggered.connect(self.title_case)
        action_capitalize.triggered.connect(self.capitalize)

        m = self.au_context_menu = QMenu(self)
        idx = self.table.indexAt(point)
        au_col_item = self.table.item(idx.row(), AUTHOR_COLUMN)
        assert au_col_item is not None
        id_ = int(au_col_item.data(Qt.ItemDataRole.UserRole))
        sub = self.get_column_name(idx.column())
        if sub == 'notes':
            self.notes_utilities.context_menu(m, self.context_item, au_col_item.text())
        else:
            ca = m.addAction(QIcon.cached_icon('edit-copy.png'), _('Copy'))
            assert ca is not None
            ca.triggered.connect(self.copy_to_clipboard)
            ca = m.addAction(QIcon.cached_icon('edit-paste.png'), _('Paste'))
            assert ca is not None
            ca.triggered.connect(self.paste_from_clipboard)

            ca = m.addAction(QIcon.cached_icon('edit-undo.png'), _('Undo'))
            assert ca is not None
            ca.triggered.connect(partial(self.undo_cell, old_value=self.original_authors[id_].get(sub)))
            ca.setEnabled(self.context_item is not None and self.item_is_modified(self.context_item, id_))

            ca = m.addAction(QIcon.cached_icon('edit_input.png'), _('Edit'))
            assert ca is not None
            ca.triggered.connect(partial(self.table.editItem, self.context_item))

            if sub != 'link':
                m.addSeparator()
                if self.context_item is not None and sub == 'name':
                    ca = m.addAction(_('Copy to author sort'))
                    assert ca is not None
                    ca.triggered.connect(self.copy_au_to_aus)
                    m.addSeparator()
                    ca = m.addAction(QIcon.cached_icon('lt.png'), _('Show books by author in book list'))
                    assert ca is not None
                    ca.triggered.connect(self.search_in_book_list)
                else:
                    ca = m.addAction(_('Copy to author'))
                    assert ca is not None
                    ca.triggered.connect(self.copy_aus_to_au)
                    ca = m.addAction(_('Recalculate sort from author'))
                    assert ca is not None
                    ca.triggered.connect(self.do_recalc_one_author_sort)
                m.addSeparator()
                m.addMenu(case_menu)
        viewport = self.table.viewport()
        assert viewport is not None
        m.exec(viewport.mapToGlobal(point))

    def undo_cell(self, old_value):
        context_item = self.context_item
        assert context_item is not None
        if context_item.column() == NOTES_COLUMN:
            self.notes_utilities.undo_note_edit(context_item)
        else:
            context_item.setText(old_value)

    def search_in_book_list(self):
        from calibre.gui2.ui import get_gui

        context_item = self.context_item
        assert context_item is not None
        row = context_item.row()
        au_item = self.table.item(row, AUTHOR_COLUMN)
        assert au_item is not None
        get_gui(fail_if_absent=True).search.set_search_string('authors:="{}"'.format(str(au_item.text()).replace(r'"', r'\"')))

    def copy_to_clipboard(self):
        context_item = self.context_item
        assert context_item is not None
        cb = QApplication.clipboard()
        assert cb is not None
        cb.setText(str(context_item.text()))

    def paste_from_clipboard(self):
        context_item = self.context_item
        assert context_item is not None
        cb = QApplication.clipboard()
        assert cb is not None
        context_item.setText(cb.text())

    def upper_case(self):
        context_item = self.context_item
        assert context_item is not None
        context_item.setText(icu_upper(str(context_item.text())))

    def lower_case(self):
        context_item = self.context_item
        assert context_item is not None
        context_item.setText(icu_lower(str(context_item.text())))

    def swap_case(self):
        context_item = self.context_item
        assert context_item is not None
        context_item.setText(str(context_item.text()).swapcase())

    def title_case(self):
        from calibre.utils.titlecase import titlecase

        context_item = self.context_item
        assert context_item is not None
        context_item.setText(titlecase(str(context_item.text())))

    def capitalize(self):
        from calibre.utils.icu import capitalize

        context_item = self.context_item
        assert context_item is not None
        context_item.setText(capitalize(str(context_item.text())))

    def copy_aus_to_au(self):
        context_item = self.context_item
        assert context_item is not None
        row = context_item.row()
        dest = self.table.item(row, AUTHOR_COLUMN)
        assert dest is not None
        dest.setText(context_item.text())

    def copy_au_to_aus(self):
        context_item = self.context_item
        assert context_item is not None
        row = context_item.row()
        dest = self.table.item(row, AUTHOR_SORT_COLUMN)
        assert dest is not None
        dest.setText(context_item.text())

    def not_found_label_timer_event(self):
        self.not_found_label.setVisible(False)

    def clear_find(self):
        self.find_box.setText('')
        self.start_find_pos = -1
        self.do_find()

    def find_text_changed(self):
        self.start_find_pos = -1

    def do_find(self, inverted=False):
        self.not_found_label.setVisible(False)
        # For some reason the button box keeps stealing the RETURN shortcut.
        # Steal it back
        ok_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        ok_button.setDefault(False)
        ok_button.setAutoDefault(False)
        cancel_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel)
        assert cancel_button is not None
        cancel_button.setDefault(False)
        cancel_button.setAutoDefault(False)

        st = icu_lower(str(self.find_box.currentText()))
        if not st:
            return
        for _x in range(self.table.rowCount() * 2):
            self.start_find_pos = (self.start_find_pos + 1) % (self.table.rowCount() * 2)
            r = (self.start_find_pos // 2) % self.table.rowCount()
            c = self.start_find_pos % 2
            item = self.table.item(r, c)
            assert item is not None
            text = icu_lower(str(item.text()))
            if (st in text) != inverted:
                self.table.setCurrentItem(item)
                self.table.setFocus(Qt.FocusReason.OtherFocusReason)
                return
        # Nothing found. Pop up the little dialog for 1.5 seconds
        self.not_found_label.setVisible(True)
        self.not_found_label_timer.start(1500)

    def do_sort(self, section):
        (
            self.do_sort_by_author,
            self.do_sort_by_author_sort,
            self.do_sort_by_count,
            self.do_sort_by_link,
            self.do_sort_by_notes,
        )[section]()

    def do_sort_by_author(self):
        self.last_sorted_by = 'author'
        self.author_order = 1 - self.author_order
        self.table.sortByColumn(AUTHOR_COLUMN, Qt.SortOrder(self.author_order))

    def do_sort_by_author_sort(self):
        self.last_sorted_by = 'sort'
        self.author_sort_order = 1 - self.author_sort_order
        self.table.sortByColumn(AUTHOR_SORT_COLUMN, Qt.SortOrder(self.author_sort_order))

    def do_sort_by_count(self):
        self.last_sorted_by = 'count'
        self.count_order = 1 - self.count_order
        self.table.sortByColumn(COUNTS_COLUMN, Qt.SortOrder(self.count_order))

    def do_sort_by_link(self):
        self.last_sorted_by = 'link'
        self.link_order = 1 - self.link_order
        self.table.sortByColumn(LINK_COLUMN, Qt.SortOrder(self.link_order))

    def do_sort_by_notes(self):
        self.last_sorted_by = 'notes'
        self.notes_order = 1 - self.notes_order
        self.table.sortByColumn(NOTES_COLUMN, Qt.SortOrder(self.notes_order))

    result_val: list[tuple[int, str, str, str, str]] = []

    def accepted(self):
        self.save_state()
        self.result_val = []
        for id_, v in self.authors.items():
            orig = self.original_authors[id_]
            if orig != v:
                self.result_val.append((id_, orig['name'], v['name'], v['sort'], v['link']))

    def rejected(self):
        self.notes_utilities.restore_all_notes()
        self.save_state()

    def do_recalc_author_sort(self):
        with self.no_cell_changed():
            for row in range(self.table.rowCount()):
                item_aut = self.table.item(row, AUTHOR_COLUMN)
                assert item_aut is not None
                id_ = int(item_aut.data(Qt.ItemDataRole.UserRole))
                aut = str(item_aut.text()).strip()
                item_aus = self.table.item(row, AUTHOR_SORT_COLUMN)
                assert item_aus is not None
                # Sometimes trailing commas are left by changing between copy algs
                aus = str(author_to_author_sort(aut)).rstrip(',')
                item_aus.setText(aus)
                self.authors[id_]['sort'] = aus
                self.set_icon(item_aus, id_)
            self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def do_recalc_one_author_sort(self):
        context_item = self.context_item
        assert context_item is not None
        row = context_item.row()
        au_item = self.table.item(row, AUTHOR_COLUMN)
        assert au_item is not None
        aut = str(au_item.text()).strip()
        dest = self.table.item(row, AUTHOR_SORT_COLUMN)
        assert dest is not None
        dest.setText(str(author_to_author_sort(aut)).rstrip(','))

    def do_auth_sort_to_author(self):
        with self.no_cell_changed():
            for row in range(self.table.rowCount()):
                aus_item = self.table.item(row, AUTHOR_SORT_COLUMN)
                assert aus_item is not None
                aus = str(aus_item.text()).strip()
                item_aut = self.table.item(row, AUTHOR_COLUMN)
                assert item_aut is not None
                id_ = int(item_aut.data(Qt.ItemDataRole.UserRole))
                item_aut.setText(aus)
                self.authors[id_]['name'] = aus
                self.set_icon(item_aut, id_)
            self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_icon(self, item, id_):
        if item.column() == NOTES_COLUMN:
            raise ValueError('got set_icon on notes column')
        modified = self.item_is_modified(item, id_)
        item.setIcon(QIcon.cached_icon('modified.png') if modified else QIcon())

    def cell_changed(self, row, col):
        if self.ignore_cell_changed:
            return
        with self.no_cell_changed():
            _au_item = self.table.item(row, AUTHOR_COLUMN)
            assert _au_item is not None
            id_ = int(_au_item.data(Qt.ItemDataRole.UserRole))
            if col == AUTHOR_COLUMN:
                assert isinstance(_au_item, TableItem)
                item = _au_item
                aut = str(item.text()).strip()
                aut_list = string_to_authors(aut)
                if len(aut_list) != 1:
                    error_dialog(self.parent(), _('Invalid author name'), _('You cannot change an author to multiple authors.')).exec()
                    aut = ' % '.join(aut_list)
                    _au_item.setText(aut)
                item.set_sort_key()
                self.authors[id_]['name'] = aut
                self.set_icon(item, id_)
                c = self.table.item(row, AUTHOR_SORT_COLUMN)
                assert c is not None
                txt = author_to_author_sort(aut)
                self.authors[id_]['sort'] = txt
                c.setText(txt)  # This triggers another cellChanged event
                item = c
            else:
                item = self.table.item(row, col)
                assert item is not None
                name = self.get_column_name(col)
                if name != 'notes':
                    assert isinstance(item, TableItem)
                    item.set_sort_key()
                    self.set_icon(item, id_)
                    self.authors[id_][self.get_column_name(col)] = str(item.text())
        self.table.setCurrentItem(item)
        self.table.scrollToItem(item)
