#!/usr/bin/env python2
from __future__ import absolute_import, division, print_function, unicode_literals

__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt5.Qt import (Qt, QDialog, QTableWidgetItem, QAbstractItemView, QIcon,
                  QDialogButtonBox, QFrame, QLabel, QTimer, QMenu, QApplication,
                  QByteArray, QItemDelegate, QAction)

from calibre.ebooks.metadata import author_to_author_sort, string_to_authors
from calibre.gui2 import error_dialog, gprefs
from calibre.gui2.dialogs.edit_authors_dialog_ui import Ui_EditAuthorsDialog
from calibre.utils.config import prefs
from calibre.utils.icu import  sort_key, primary_contains, contains
from polyglot.builtins import unicode_type

QT_HIDDEN_CLEAR_ACTION = '_q_qlineeditclearaction'

class tableItem(QTableWidgetItem):

    def __ge__(self, other):
        return sort_key(unicode_type(self.text())) >= sort_key(unicode_type(other.text()))

    def __lt__(self, other):
        return sort_key(unicode_type(self.text())) < sort_key(unicode_type(other.text()))


class EditColumnDelegate(QItemDelegate):

    def __init__(self, completion_data):
        QItemDelegate.__init__(self)
        self.completion_data = completion_data

    def createEditor(self, parent, option, index):
        if index.column() == 0:
            if self.completion_data:
                from calibre.gui2.complete2 import EditWithComplete
                editor = EditWithComplete(parent)
                editor.set_separator(None)
                editor.update_items_cache(self.completion_data)
            else:
                from calibre.gui2.widgets import EnLineEdit
                editor = EnLineEdit(parent)
            return editor
        return QItemDelegate.createEditor(self, parent, option, index)


class EditAuthorsDialog(QDialog, Ui_EditAuthorsDialog):

    def __init__(self, parent, db, id_to_select, select_sort, select_link, find_aut_func):
        QDialog.__init__(self, parent)
        Ui_EditAuthorsDialog.__init__(self)
        self.setupUi(self)

        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        try:
            self.table_column_widths = \
                        gprefs.get('manage_authors_table_widths', None)
            geom = gprefs.get('manage_authors_dialog_geometry', None)
            if geom:
                QApplication.instance().safe_restore_geometry(self, QByteArray(geom))
        except Exception:
            pass

        self.buttonBox.button(QDialogButtonBox.Ok).setText(_('&OK'))
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(_('&Cancel'))
        self.buttonBox.accepted.connect(self.accepted)
        self.apply_vl_checkbox.stateChanged.connect(self.use_vl_changed)

        # Set up the heading for sorting
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        self.find_aut_func = find_aut_func
        self.table.resizeColumnsToContents()
        if self.table.columnWidth(2) < 200:
            self.table.setColumnWidth(2, 200)

        # set up the cellChanged signal only after the table is filled
        self.table.cellChanged.connect(self.cell_changed)

        self.recalc_author_sort.clicked.connect(self.do_recalc_author_sort)
        self.auth_sort_to_author.clicked.connect(self.do_auth_sort_to_author)

        # Capture clicks on the horizontal header to sort the table columns
        hh = self.table.horizontalHeader()
        hh.sectionResized.connect(self.table_column_resized)
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self.do_sort)
        hh.setSortIndicatorShown(True)

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
        l.setFrameStyle(QFrame.StyledPanel)
        l.setAutoFillBackground(True)
        l.setText(_('No matches found'))
        l.setAlignment(Qt.AlignVCenter)
        l.resize(l.sizeHint())
        l.move(10, 2)
        l.setVisible(False)
        self.not_found_label_timer = QTimer()
        self.not_found_label_timer.setSingleShot(True)
        self.not_found_label_timer.timeout.connect(
                self.not_found_label_timer_event, type=Qt.QueuedConnection)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
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

        self.edited_icon = QIcon(I('modified.png'))
        if prefs['use_primary_find_in_search']:
            self.string_contains = primary_contains
        else:
            self.string_contains = contains

        self.last_sorted_by = 'sort'
        self.author_order = 1
        self.author_sort_order = 0
        self.link_order = 1
        self.show_table(id_to_select, select_sort, select_link)

    def use_vl_changed(self, x):
        self.show_table(None, None, None)

    def clear_filter(self):
        self.filter_box.setText('')
        self.show_table(None, None, None)

    def do_filter(self):
        self.show_table(None, None, None)

    def show_table(self, id_to_select, select_sort, select_link):
        filter_text = icu_lower(unicode_type(self.filter_box.text()))
        auts_to_show = []
        for t in self.find_aut_func(use_virtual_library = self.apply_vl_checkbox.isChecked()):
            if self.string_contains(filter_text, icu_lower(t[1])):
                auts_to_show.append(t[0])
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(3)

        self.table.setRowCount(len(auts_to_show))
        select_item = None
        row = 0
        for id_, v in self.authors.items():
            if id_ not in auts_to_show:
                continue
            name, sort, link = (v['name'], v['sort'], v['link'])
            orig = self.original_authors[id_]
            name = name.replace('|', ',')

            name_item = tableItem(name)
            name_item.setData(Qt.UserRole, id_)
            if name != orig['name']:
                name_item.setIcon(self.edited_icon)
            sort_item = tableItem(sort)
            if sort != orig['sort']:
                sort_item.setIcon(self.edited_icon)
            link_item = tableItem(link)
            if link != orig['link']:
                link_item.setIcon(self.edited_icon)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, sort_item)
            self.table.setItem(row, 2, link_item)

            if id_to_select and id_to_select in (id_, name):
                if select_sort:
                    select_item = sort_item
                elif select_link:
                    select_item = link_item
                else:
                    select_item = name_item
            row += 1

        self.table.setItemDelegate(EditColumnDelegate(self.completion_data))
        self.table.setHorizontalHeaderLabels([_('Author'), _('Author sort'), _('Link')])

        if self.last_sorted_by == 'sort':
            self.author_sort_order = 1 - self.author_sort_order
            self.do_sort_by_author_sort()
        elif self.last_sorted_by == 'author':
            self.author_order = 1 - self.author_order
            self.do_sort_by_author()
        else:
            self.link_order = 1 - self.link_order
            self.do_sort_by_link()

        # Position on the desired item
        if select_item is not None:
            self.table.setCurrentItem(select_item)
            self.table.editItem(select_item)
            self.start_find_pos = select_item.row() * 2 + select_item.column()
        else:
            self.table.setCurrentCell(0, 0)
            self.start_find_pos = -1
        self.table.blockSignals(False)

    def save_state(self):
        self.table_column_widths = []
        for c in range(0, self.table.columnCount()):
            self.table_column_widths.append(self.table.columnWidth(c))
        gprefs['manage_authors_table_widths'] = self.table_column_widths
        gprefs['manage_authors_dialog_geometry'] = bytearray(self.saveGeometry())

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

    def show_context_menu(self, point):
        self.context_item = self.table.itemAt(point)
        case_menu = QMenu(_('Change case'))
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

        m = self.au_context_menu = QMenu()
        ca = m.addAction(_('Copy'))
        ca.triggered.connect(self.copy_to_clipboard)
        ca = m.addAction(_('Paste'))
        ca.triggered.connect(self.paste_from_clipboard)
        m.addSeparator()

        if self.context_item is not None and self.context_item.column() == 0:
            ca = m.addAction(_('Copy to author sort'))
            ca.triggered.connect(self.copy_au_to_aus)
            m.addSeparator()
            ca = m.addAction(_("Show books by author in book list"))
            ca.triggered.connect(self.search_in_book_list)
        else:
            ca = m.addAction(_('Copy to author'))
            ca.triggered.connect(self.copy_aus_to_au)
        m.addSeparator()
        m.addMenu(case_menu)
        m.exec_(self.table.mapToGlobal(point))

    def search_in_book_list(self):
        from calibre.gui2.ui import get_gui
        row = self.context_item.row()
        get_gui().search.set_search_string(self.table.item(row, 0).text())

    def copy_to_clipboard(self):
        cb = QApplication.clipboard()
        cb.setText(unicode_type(self.context_item.text()))

    def paste_from_clipboard(self):
        cb = QApplication.clipboard()
        self.context_item.setText(cb.text())

    def upper_case(self):
        self.context_item.setText(icu_upper(unicode_type(self.context_item.text())))

    def lower_case(self):
        self.context_item.setText(icu_lower(unicode_type(self.context_item.text())))

    def swap_case(self):
        self.context_item.setText(unicode_type(self.context_item.text()).swapcase())

    def title_case(self):
        from calibre.utils.titlecase import titlecase
        self.context_item.setText(titlecase(unicode_type(self.context_item.text())))

    def capitalize(self):
        from calibre.utils.icu import capitalize
        self.context_item.setText(capitalize(unicode_type(self.context_item.text())))

    def copy_aus_to_au(self):
        row = self.context_item.row()
        dest = self.table.item(row, 0)
        dest.setText(self.context_item.text())

    def copy_au_to_aus(self):
        row = self.context_item.row()
        dest = self.table.item(row, 1)
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
        self.buttonBox.button(QDialogButtonBox.Ok).setDefault(False)
        self.buttonBox.button(QDialogButtonBox.Ok).setAutoDefault(False)
        self.buttonBox.button(QDialogButtonBox.Cancel).setDefault(False)
        self.buttonBox.button(QDialogButtonBox.Cancel).setAutoDefault(False)

        st = icu_lower(unicode_type(self.find_box.currentText()))
        if not st:
            return
        for _ in range(0, self.table.rowCount()*2):
            self.start_find_pos = (self.start_find_pos + 1) % (self.table.rowCount()*2)
            r = (self.start_find_pos//2) % self.table.rowCount()
            c = self.start_find_pos % 2
            item = self.table.item(r, c)
            text = icu_lower(unicode_type(item.text()))
            if st in text:
                self.table.setCurrentItem(item)
                self.table.setFocus(True)
                return
        # Nothing found. Pop up the little dialog for 1.5 seconds
        self.not_found_label.setVisible(True)
        self.not_found_label_timer.start(1500)

    def do_sort(self, section):
        (self.do_sort_by_author, self.do_sort_by_author_sort, self.do_sort_by_link)[section]()

    def do_sort_by_author(self):
        self.last_sorted_by = 'author'
        self.author_order = 1 - self.author_order
        self.table.sortByColumn(0, self.author_order)

    def do_sort_by_author_sort(self):
        self.last_sorted_by = 'sort'
        self.author_sort_order = 1 - self.author_sort_order
        self.table.sortByColumn(1, self.author_sort_order)

    def do_sort_by_link(self):
        self.last_sorted_by = 'link'
        self.link_order = 1 - self.link_order
        self.table.sortByColumn(2, self.link_order)

    def accepted(self):
        self.save_state()
        self.result = []
        for id_, v in self.authors.items():
            orig = self.original_authors[id_]
            if orig != v:
                self.result.append((id_, orig['name'], v['name'], v['sort'], v['link']))

    def do_recalc_author_sort(self):
        self.table.cellChanged.disconnect()
        for row in range(0,self.table.rowCount()):
            item = self.table.item(row, 0)
            aut  = unicode_type(item.text()).strip()
            c = self.table.item(row, 1)
            # Sometimes trailing commas are left by changing between copy algs
            c.setText(author_to_author_sort(aut).rstrip(','))
        self.table.setFocus(Qt.OtherFocusReason)
        self.table.cellChanged.connect(self.cell_changed)

    def do_auth_sort_to_author(self):
        self.table.cellChanged.disconnect()
        for row in range(0,self.table.rowCount()):
            item = self.table.item(row, 1)
            aus  = unicode_type(item.text()).strip()
            c = self.table.item(row, 0)
            # Sometimes trailing commas are left by changing between copy algs
            c.setText(aus)
        self.table.setFocus(Qt.OtherFocusReason)
        self.table.cellChanged.connect(self.cell_changed)

    def cell_changed(self, row, col):
        id_ = int(self.table.item(row, 0).data(Qt.UserRole))
        if col == 0:
            item = self.table.item(row, 0)
            item.setIcon(self.edited_icon)
            aut  = unicode_type(item.text()).strip()
            aut_list = string_to_authors(aut)
            if len(aut_list) != 1:
                error_dialog(self.parent(), _('Invalid author name'),
                        _('You cannot change an author to multiple authors.')).exec_()
                aut = ' % '.join(aut_list)
                self.table.item(row, 0).setText(aut)
            self.authors[id_]['name'] = aut
            c = self.table.item(row, 1)
            txt = author_to_author_sort(aut)
            c.setText(txt)
            self.authors[id_]['sort'] = txt
            item = c
        else:
            item  = self.table.item(row, col)
            item.setIcon(self.edited_icon)
            if col == 1:
                self.authors[id_]['sort'] = unicode_type(item.text())
            else:
                self.authors[id_]['link'] = unicode_type(item.text())
        self.table.setCurrentItem(item)
        self.table.scrollToItem(item)
