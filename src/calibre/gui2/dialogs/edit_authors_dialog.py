#!/usr/bin/env python


__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from contextlib import contextmanager
from functools import partial
from qt.core import (
    QAbstractItemView, QAction, QApplication, QDialog, QDialogButtonBox, QFrame,
    QIcon, QLabel, QMenu, QStyledItemDelegate, Qt, QTableWidgetItem, QTimer,
)

from calibre.ebooks.metadata import author_to_author_sort, string_to_authors
from calibre.gui2 import error_dialog, gprefs
from calibre.gui2.dialogs.edit_authors_dialog_ui import Ui_EditAuthorsDialog
from calibre.gui2.dialogs.tag_list_editor import NotesUtilities, NotesTableWidgetItem
from calibre.utils.config import prefs
from calibre.utils.config_base import tweaks
from calibre.utils.icu import (
    contains, lower as icu_lower, primary_contains, primary_startswith, sort_key,
    upper as icu_upper,
)

QT_HIDDEN_CLEAR_ACTION = '_q_qlineeditclearaction'


class TableItem(QTableWidgetItem):

    def __init__(self, txt, skey=None):
        QTableWidgetItem.__init__(self, txt)
        self.sort_key = sort_key(str(txt)) if skey is None else skey

    def setText(self, txt):
        self.sort_key = sort_key(str(txt))
        QTableWidgetItem.setText(self, txt)

    def set_sort_key(self):
        self.sort_key = sort_key(str(self.text()))

    def __ge__(self, other):
        return self.sort_key >= other.sort_key

    def __lt__(self, other):
        return self.sort_key < other.sort_key


AUTHOR_COLUMN = 0
AUTHOR_SORT_COLUMN = 1
LINK_COLUMN = 2
NOTES_COLUMN = 3


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

        from calibre.gui2.widgets import EnLineEdit
        editor = EnLineEdit(parent)
        editor.setClearButtonEnabled(True)
        return editor


class EditAuthorsDialog(QDialog, Ui_EditAuthorsDialog):

    def __init__(self, parent, db, id_to_select, select_sort, select_link,
                 find_aut_func, is_first_letter=False):
        QDialog.__init__(self, parent)
        Ui_EditAuthorsDialog.__init__(self)
        self.setupUi(self)

        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        try:
            self.table_column_widths = \
                        gprefs.get('manage_authors_table_widths', None)
            self.restore_geometry(gprefs, 'manage_authors_dialog_geometry')
        except Exception:
            pass

        self.notes_utilities = NotesUtilities(self.table, "authors",
                  lambda item: int(self.table.item(item.row(), AUTHOR_COLUMN).data(Qt.ItemDataRole.UserRole)))

        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText(_('&OK'))
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText(_('&Cancel'))
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
        if self.table.columnWidth(2) < 200:
            self.table.setColumnWidth(2, 200)

        # set up the cellChanged signal only after the table is filled
        self.ignore_cell_changed = False
        self.table.cellChanged.connect(self.cell_changed)

        self.recalc_author_sort.clicked.connect(self.do_recalc_author_sort)
        self.auth_sort_to_author.clicked.connect(self.do_auth_sort_to_author)

        # Capture clicks on the horizontal header to sort the table columns
        hh = self.table.horizontalHeader()
        hh.sectionResized.connect(self.table_column_resized)
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self.do_sort)
        hh.setSortIndicatorShown(True)

        vh = self.table.verticalHeader()
        vh.setDefaultSectionSize(gprefs.get('general_category_editor_row_height', vh.defaultSectionSize()))
        vh.sectionResized.connect(self.row_height_changed)

        # set up the search & filter boxes
        self.find_box.initialize('manage_authors_search')
        le = self.find_box.lineEdit()
        ac = le.findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
        if ac is not None:
            ac.triggered.connect(self.clear_find)
        le.returnPressed.connect(self.do_find)
        self.find_box.editTextChanged.connect(self.find_text_changed)
        self.find_button.clicked.connect(self.do_find)
        self.find_button.setDefault(True)

        self.filter_box.initialize('manage_authors_filter')
        le = self.filter_box.lineEdit()
        ac = le.findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
        if ac is not None:
            ac.triggered.connect(self.clear_filter)
        self.filter_box.lineEdit().returnPressed.connect(self.do_filter)
        self.filter_button.clicked.connect(self.do_filter)

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
        self.not_found_label_timer.timeout.connect(
                self.not_found_label_timer_event, type=Qt.ConnectionType.QueuedConnection)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        # Fetch the data
        self.authors = {}
        self.original_authors = {}
        auts = db.new_api.author_data()
        self.completion_data = []
        for id_, v in auts.items():
            name = v['name']
            name = name.replace('|', ',')
            self.completion_data.append(name)
            self.authors[id_] = {'name': name, 'sort': v['sort'], 'link': v['link']}
            self.original_authors[id_] = {'name': name, 'sort': v['sort'],
                                          'link': v['link']}

        if prefs['use_primary_find_in_search']:
            self.string_contains = primary_contains
        else:
            self.string_contains = contains

        self.last_sorted_by = 'sort'
        self.author_order = 1
        self.author_sort_order = 0
        self.link_order = 1
        self.notes_order = 1
        self.table.setItemDelegate(EditColumnDelegate(self.completion_data, self.table,
                                                      self.notes_utilities, self.get_item_id))
        self.show_table(id_to_select, select_sort, select_link, is_first_letter)

    def edit_cell(self):
        if self.table.currentIndex().isValid():
            self.table.editItem(self.table.currentItem())

    def get_item_id(self, item):
        return int(self.table.item(item.row(), AUTHOR_COLUMN).data(Qt.ItemDataRole.UserRole))

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

    def do_filter(self):
        self.show_table(None, None, None, False)

    def show_table(self, id_to_select, select_sort, select_link, is_first_letter):
        auts_to_show = {t[0] for t in self.find_aut_func(self.selection_to_apply())}
        filter_text = icu_lower(str(self.filter_box.text()))
        if filter_text:
            auts_to_show = {id_ for id_ in auts_to_show
                if self.string_contains(filter_text, icu_lower(self.authors[id_]['name']))}

        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(4)

        self.table.setRowCount(len(auts_to_show))
        row = 0
        from calibre.gui2.ui import get_gui
        all_items_that_have_notes = get_gui().current_db.new_api.get_all_items_that_have_notes('authors')
        for id_, v in self.authors.items():
            if id_ not in auts_to_show:
                continue
            name, sort, link = (v['name'], v['sort'], v['link'])
            name = name.replace('|', ',')

            name_item = TableItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, id_)
            sort_item = TableItem(sort)
            link_item = TableItem(link)

            self.table.setItem(row, AUTHOR_COLUMN, name_item)
            self.table.setItem(row, AUTHOR_SORT_COLUMN, sort_item)
            self.table.setItem(row, LINK_COLUMN, link_item)
            note_item = NotesTableWidgetItem()
            self.table.setItem(row, NOTES_COLUMN, note_item)

            self.set_icon(name_item, id_)
            self.set_icon(sort_item, id_)
            self.set_icon(link_item, id_)
            self.notes_utilities.set_icon(note_item, id_, id_ in all_items_that_have_notes)
            row += 1

        self.table.setHorizontalHeaderLabels([_('Author'), _('Author sort'), _('Link'), _('Notes')])

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
            for row in range(0, len(auts_to_show)):
                if is_first_letter:
                    item_txt = str(self.table.item(row, AUTHOR_SORT_COLUMN).text() if use_as
                                                else self.table.item(row, AUTHOR_COLUMN).text())
                    if primary_startswith(item_txt, id_to_select):
                        select_item = self.table.item(row, AUTHOR_SORT_COLUMN if use_as else 0)
                        break
                elif id_to_select == self.table.item(row, AUTHOR_COLUMN).data(Qt.ItemDataRole.UserRole):
                    if select_sort:
                        select_item = self.table.item(row, AUTHOR_SORT_COLUMN)
                    elif select_link:
                        select_item = self.table.item(row, LINK_COLUMN)
                    else:
                        select_item = (self.table.item(row, AUTHOR_SORT_COLUMN) if use_as
                                        else self.table.item(row, AUTHOR_COLUMN))
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
        self.table.verticalHeader().blockSignals(True)
        self.table.verticalHeader().setDefaultSectionSize(new)
        self.table.verticalHeader().blockSignals(False)

    def save_state(self):
        self.table_column_widths = []
        for c in range(0, self.table.columnCount()):
            self.table_column_widths.append(self.table.columnWidth(c))
        gprefs['general_category_editor_row_height'] = self.table.verticalHeader().sectionSize(0)
        gprefs['manage_authors_table_widths'] = self.table_column_widths
        self.save_geometry(gprefs, 'manage_authors_dialog_geometry')

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
        self.save_state()

    def get_column_name(self, column):
        return ('name', 'sort', 'link', 'notes')[column]

    def item_is_modified(self, item, id_):
        sub = self.get_column_name(item.column())
        if sub == 'notes':
            return self.notes_utilities.is_note_modified(id_)
        return item.text() != self.original_authors[id_][sub]

    def show_context_menu(self, point):
        self.context_item = self.table.itemAt(point)
        if self.context_item is None:
            return
        case_menu = QMenu(_('Change case'))
        case_menu.setIcon(QIcon.cached_icon('font_size_larger.png'))
        action_upper_case = case_menu.addAction(_('Upper case'))
        action_lower_case = case_menu.addAction(_('Lower case'))
        action_swap_case = case_menu.addAction(_('Swap case'))
        action_title_case = case_menu.addAction(_('Title case'))
        action_capitalize = case_menu.addAction(_('Capitalize'))

        action_upper_case.triggered.connect(self.upper_case)
        action_lower_case.triggered.connect(self.lower_case)
        action_swap_case.triggered.connect(self.swap_case)
        action_title_case.triggered.connect(self.title_case)
        action_capitalize.triggered.connect(self.capitalize)

        m = self.au_context_menu = QMenu(self)
        idx = self.table.indexAt(point)
        id_ = int(self.table.item(idx.row(), AUTHOR_COLUMN).data(Qt.ItemDataRole.UserRole))
        sub = self.get_column_name(idx.column())
        if sub == 'notes':
            self.notes_utilities.context_menu(m, self.context_item,
                                              self.table.item(idx.row(), AUTHOR_COLUMN).text())
        else:
            ca = m.addAction(QIcon.cached_icon('edit-copy.png'), _('Copy'))
            ca.triggered.connect(self.copy_to_clipboard)
            ca = m.addAction(QIcon.cached_icon('edit-paste.png'), _('Paste'))
            ca.triggered.connect(self.paste_from_clipboard)

            ca = m.addAction(QIcon.cached_icon('edit-undo.png'), _('Undo'))
            ca.triggered.connect(partial(self.undo_cell,
                                         old_value=self.original_authors[id_].get(sub)))
            ca.setEnabled(self.context_item is not None and self.item_is_modified(self.context_item, id_))

            ca = m.addAction(QIcon.cached_icon('edit_input.png'), _('Edit'))
            ca.triggered.connect(partial(self.table.editItem, self.context_item))

            if sub != 'link':
                m.addSeparator()
                if self.context_item is not None and sub == 'name':
                    ca = m.addAction(_('Copy to author sort'))
                    ca.triggered.connect(self.copy_au_to_aus)
                    m.addSeparator()
                    ca = m.addAction(QIcon.cached_icon('lt.png'), _("Show books by author in book list"))
                    ca.triggered.connect(self.search_in_book_list)
                else:
                    ca = m.addAction(_('Copy to author'))
                    ca.triggered.connect(self.copy_aus_to_au)
                m.addSeparator()
                m.addMenu(case_menu)
        m.exec(self.table.viewport().mapToGlobal(point))

    def undo_cell(self, old_value):
        if self.context_item.column() == 3:
            self.notes_utilities.undo_note_edit(self.context_item)
        else:
            self.context_item.setText(old_value)

    def search_in_book_list(self):
        from calibre.gui2.ui import get_gui
        row = self.context_item.row()
        get_gui().search.set_search_string('authors:="%s"' %
                           str(self.table.item(row, AUTHOR_COLUMN).text()).replace(r'"', r'\"'))

    def copy_to_clipboard(self):
        cb = QApplication.clipboard()
        cb.setText(str(self.context_item.text()))

    def paste_from_clipboard(self):
        cb = QApplication.clipboard()
        self.context_item.setText(cb.text())

    def upper_case(self):
        self.context_item.setText(icu_upper(str(self.context_item.text())))

    def lower_case(self):
        self.context_item.setText(icu_lower(str(self.context_item.text())))

    def swap_case(self):
        self.context_item.setText(str(self.context_item.text()).swapcase())

    def title_case(self):
        from calibre.utils.titlecase import titlecase
        self.context_item.setText(titlecase(str(self.context_item.text())))

    def capitalize(self):
        from calibre.utils.icu import capitalize
        self.context_item.setText(capitalize(str(self.context_item.text())))

    def copy_aus_to_au(self):
        row = self.context_item.row()
        dest = self.table.item(row, AUTHOR_COLUMN)
        dest.setText(self.context_item.text())

    def copy_au_to_aus(self):
        row = self.context_item.row()
        dest = self.table.item(row, AUTHOR_SORT_COLUMN)
        dest.setText(self.context_item.text())

    def not_found_label_timer_event(self):
        self.not_found_label.setVisible(False)

    def clear_find(self):
        self.find_box.setText('')
        self.start_find_pos = -1
        self.do_find()

    def find_text_changed(self):
        self.start_find_pos = -1

    def do_find(self):
        self.not_found_label.setVisible(False)
        # For some reason the button box keeps stealing the RETURN shortcut.
        # Steal it back
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setDefault(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setAutoDefault(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setDefault(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setAutoDefault(False)

        st = icu_lower(str(self.find_box.currentText()))
        if not st:
            return
        for _ in range(0, self.table.rowCount()*2):
            self.start_find_pos = (self.start_find_pos + 1) % (self.table.rowCount()*2)
            r = (self.start_find_pos//2) % self.table.rowCount()
            c = self.start_find_pos % 2
            item = self.table.item(r, c)
            text = icu_lower(str(item.text()))
            if st in text:
                self.table.setCurrentItem(item)
                self.table.setFocus(Qt.FocusReason.OtherFocusReason)
                return
        # Nothing found. Pop up the little dialog for 1.5 seconds
        self.not_found_label.setVisible(True)
        self.not_found_label_timer.start(1500)

    def do_sort(self, section):
        (self.do_sort_by_author, self.do_sort_by_author_sort, self.do_sort_by_link, self.do_sort_by_notes)[section]()

    def do_sort_by_author(self):
        self.last_sorted_by = 'author'
        self.author_order = 1 - self.author_order
        self.table.sortByColumn(0, Qt.SortOrder(self.author_order))

    def do_sort_by_author_sort(self):
        self.last_sorted_by = 'sort'
        self.author_sort_order = 1 - self.author_sort_order
        self.table.sortByColumn(1, Qt.SortOrder(self.author_sort_order))

    def do_sort_by_link(self):
        self.last_sorted_by = 'link'
        self.link_order = 1 - self.link_order
        self.table.sortByColumn(2, Qt.SortOrder(self.link_order))

    def do_sort_by_notes(self):
        self.last_sorted_by = 'notes'
        self.notes_order = 1 - self.notes_order
        self.table.sortByColumn(3, Qt.SortOrder(self.notes_order))

    def accepted(self):
        self.save_state()
        self.result = []
        for id_, v in self.authors.items():
            orig = self.original_authors[id_]
            if orig != v:
                self.result.append((id_, orig['name'], v['name'], v['sort'], v['link']))

    def rejected(self):
        self.notes_utilities.restore_all_notes()
        self.save_state()

    def do_recalc_author_sort(self):
        with self.no_cell_changed():
            for row in range(0,self.table.rowCount()):
                item_aut = self.table.item(row, AUTHOR_COLUMN)
                id_ = int(item_aut.data(Qt.ItemDataRole.UserRole))
                aut  = str(item_aut.text()).strip()
                item_aus = self.table.item(row, AUTHOR_SORT_COLUMN)
                # Sometimes trailing commas are left by changing between copy algs
                aus = str(author_to_author_sort(aut)).rstrip(',')
                item_aus.setText(aus)
                self.authors[id_]['sort'] = aus
                self.set_icon(item_aus, id_)
            self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def do_auth_sort_to_author(self):
        with self.no_cell_changed():
            for row in range(0,self.table.rowCount()):
                aus  = str(self.table.item(row, AUTHOR_SORT_COLUMN).text()).strip()
                item_aut = self.table.item(row, AUTHOR_COLUMN)
                id_ = int(item_aut.data(Qt.ItemDataRole.UserRole))
                item_aut.setText(aus)
                self.authors[id_]['name'] = aus
                self.set_icon(item_aut, id_)
            self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_icon(self, item, id_):
        if item.column() == NOTES_COLUMN:
            raise ValueError('got set_icon on notes column')
        modified = self.item_is_modified(item, id_)
        item.setIcon(QIcon.cached_icon('modified.png') if modified
                     else QIcon.cached_icon())

    def cell_changed(self, row, col):
        if self.ignore_cell_changed:
            return
        with self.no_cell_changed():
            id_ = int(self.table.item(row, AUTHOR_COLUMN).data(Qt.ItemDataRole.UserRole))
            if col == AUTHOR_COLUMN:
                item = self.table.item(row, AUTHOR_COLUMN)
                aut  = str(item.text()).strip()
                aut_list = string_to_authors(aut)
                if len(aut_list) != 1:
                    error_dialog(self.parent(), _('Invalid author name'),
                            _('You cannot change an author to multiple authors.')).exec()
                    aut = ' % '.join(aut_list)
                    self.table.item(row, AUTHOR_COLUMN).setText(aut)
                item.set_sort_key()
                self.authors[id_]['name'] = aut
                self.set_icon(item, id_)
                c = self.table.item(row, AUTHOR_SORT_COLUMN)
                txt = author_to_author_sort(aut)
                self.authors[id_]['sort'] = txt
                c.setText(txt)  # This triggers another cellChanged event
                item = c
            else:
                item  = self.table.item(row, col)
                name = self.get_column_name(col)
                if name != 'notes':
                    item.set_sort_key()
                    self.set_icon(item, id_)
                    self.authors[id_][self.get_column_name(col)] = str(item.text())
        self.table.setCurrentItem(item)
        self.table.scrollToItem(item)
