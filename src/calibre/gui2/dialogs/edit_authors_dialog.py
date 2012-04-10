#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt4.Qt import (Qt, QDialog, QTableWidgetItem, QAbstractItemView, QIcon,
                  QDialogButtonBox, QFrame, QLabel, QTimer, QMenu, QApplication,
                  QByteArray)

from calibre.ebooks.metadata import author_to_author_sort
from calibre.gui2 import error_dialog, gprefs
from calibre.gui2.dialogs.edit_authors_dialog_ui import Ui_EditAuthorsDialog
from calibre.utils.icu import sort_key

class tableItem(QTableWidgetItem):
    def __ge__(self, other):
        return sort_key(unicode(self.text())) >= sort_key(unicode(other.text()))

    def __lt__(self, other):
        return sort_key(unicode(self.text())) < sort_key(unicode(other.text()))

class EditAuthorsDialog(QDialog, Ui_EditAuthorsDialog):

    def __init__(self, parent, db, id_to_select, select_sort, select_link):
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
            geom = gprefs.get('manage_authors_dialog_geometry', bytearray(''))
            self.restoreGeometry(QByteArray(geom))
        except:
            pass

        self.buttonBox.accepted.connect(self.accepted)

        # Set up the column headings
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setColumnCount(3)
        self.down_arrow_icon = QIcon(I('arrow-down.png'))
        self.up_arrow_icon = QIcon(I('arrow-up.png'))
        self.blank_icon = QIcon(I('blank.png'))
        self.auth_col = QTableWidgetItem(_('Author'))
        self.table.setHorizontalHeaderItem(0, self.auth_col)
        self.auth_col.setIcon(self.blank_icon)
        self.aus_col = QTableWidgetItem(_('Author sort'))
        self.table.setHorizontalHeaderItem(1, self.aus_col)
        self.aus_col.setIcon(self.up_arrow_icon)
        self.aul_col = QTableWidgetItem(_('Link'))
        self.table.setHorizontalHeaderItem(2, self.aul_col)
        self.aus_col.setIcon(self.blank_icon)

        # Add the data
        self.authors = {}
        auts = db.get_authors_with_ids()
        self.table.setRowCount(len(auts))
        select_item = None
        for row, (id, author, sort, link) in enumerate(auts):
            author = author.replace('|', ',')
            self.authors[id] = (author, sort, link)
            aut = tableItem(author)
            aut.setData(Qt.UserRole, id)
            sort = tableItem(sort)
            link = tableItem(link)
            self.table.setItem(row, 0, aut)
            self.table.setItem(row, 1, sort)
            self.table.setItem(row, 2, link)
            if id == id_to_select:
                if select_sort:
                    select_item = sort
                elif select_link:
                    select_item = link
                else:
                    select_item = aut
        self.table.resizeColumnsToContents()
        if self.table.columnWidth(2) < 200:
            self.table.setColumnWidth(2, 200)

        # set up the cellChanged signal only after the table is filled
        self.table.cellChanged.connect(self.cell_changed)

        # set up sort buttons
        self.sort_by_author.setCheckable(True)
        self.sort_by_author.setChecked(False)
        self.sort_by_author.clicked.connect(self.do_sort_by_author)
        self.author_order = 1

        self.table.sortByColumn(1, Qt.AscendingOrder)
        self.sort_by_author_sort.clicked.connect(self.do_sort_by_author_sort)
        self.sort_by_author_sort.setCheckable(True)
        self.sort_by_author_sort.setChecked(True)
        self.author_sort_order = 1

        self.recalc_author_sort.clicked.connect(self.do_recalc_author_sort)
        self.auth_sort_to_author.clicked.connect(self.do_auth_sort_to_author)

        # Position on the desired item
        if select_item is not None:
            self.table.setCurrentItem(select_item)
            self.table.editItem(select_item)
            self.start_find_pos = select_item.row() * 2 + select_item.column()
        else:
            self.table.setCurrentCell(0, 0)
            self.start_find_pos = -1

        # set up the search box
        self.find_box.initialize('manage_authors_search')
        self.find_box.lineEdit().returnPressed.connect(self.do_find)
        self.find_box.editTextChanged.connect(self.find_text_changed)
        self.find_button.clicked.connect(self.do_find)

        l = QLabel(self.table)
        self.not_found_label = l
        l.setFrameStyle(QFrame.StyledPanel)
        l.setAutoFillBackground(True)
        l.setText(_('No matches found'))
        l.setAlignment(Qt.AlignVCenter)
        l.resize(l.sizeHint())
        l.move(10,20)
        l.setVisible(False)
        self.not_found_label.move(40, 40)
        self.not_found_label_timer = QTimer()
        self.not_found_label_timer.setSingleShot(True)
        self.not_found_label_timer.timeout.connect(
                self.not_found_label_timer_event, type=Qt.QueuedConnection)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested .connect(self.show_context_menu)

    def save_state(self):
        self.table_column_widths = []
        for c in range(0, self.table.columnCount()):
            self.table_column_widths.append(self.table.columnWidth(c))
        gprefs['manage_authors_table_widths'] = self.table_column_widths
        gprefs['manage_authors_dialog_geometry'] = bytearray(self.saveGeometry())

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
            w /= self.table.columnCount()
            for c in range(0, self.table.columnCount()):
                self.table.setColumnWidth(c, w)
        self.save_state()

    def show_context_menu(self, point):
        self.context_item = self.table.itemAt(point)
        case_menu = QMenu(_('Change Case'))
        action_upper_case = case_menu.addAction(_('Upper Case'))
        action_lower_case = case_menu.addAction(_('Lower Case'))
        action_swap_case = case_menu.addAction(_('Swap Case'))
        action_title_case = case_menu.addAction(_('Title Case'))
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
        else:
            ca = m.addAction(_('Copy to author'))
            ca.triggered.connect(self.copy_aus_to_au)
        m.addSeparator()
        m.addMenu(case_menu)
        m.exec_(self.table.mapToGlobal(point))

    def copy_to_clipboard(self):
        cb = QApplication.clipboard()
        cb.setText(unicode(self.context_item.text()))

    def paste_from_clipboard(self):
        cb = QApplication.clipboard()
        self.context_item.setText(cb.text())

    def upper_case(self):
        self.context_item.setText(icu_upper(unicode(self.context_item.text())))

    def lower_case(self):
        self.context_item.setText(icu_lower(unicode(self.context_item.text())))

    def swap_case(self):
        self.context_item.setText(unicode(self.context_item.text()).swapcase())

    def title_case(self):
        from calibre.utils.titlecase import titlecase
        self.context_item.setText(titlecase(unicode(self.context_item.text())))

    def capitalize(self):
        from calibre.utils.icu import capitalize
        self.context_item.setText(capitalize(unicode(self.context_item.text())))

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
        st = icu_lower(unicode(self.find_box.currentText()))

        for i in range(0, self.table.rowCount()*2):
            self.start_find_pos = (self.start_find_pos + 1) % (self.table.rowCount()*2)
            r = (self.start_find_pos/2)%self.table.rowCount()
            c = self.start_find_pos % 2
            item = self.table.item(r, c)
            text = icu_lower(unicode(item.text()))
            if st in text:
                self.table.setCurrentItem(item)
                self.table.setFocus(True)
                return
        # Nothing found. Pop up the little dialog for 1.5 seconds
        self.not_found_label.setVisible(True)
        self.not_found_label_timer.start(1500)

    def do_sort_by_author(self):
        self.author_order = 1 if self.author_order == 0 else 0
        self.table.sortByColumn(0, self.author_order)
        self.sort_by_author.setChecked(True)
        self.sort_by_author_sort.setChecked(False)
        self.auth_col.setIcon(self.down_arrow_icon if self.author_order
                                                    else self.up_arrow_icon)
        self.aus_col.setIcon(self.blank_icon)

    def do_sort_by_author_sort(self):
        self.author_sort_order = 1 if self.author_sort_order == 0 else 0
        self.table.sortByColumn(1, self.author_sort_order)
        self.sort_by_author.setChecked(False)
        self.sort_by_author_sort.setChecked(True)
        self.aus_col.setIcon(self.down_arrow_icon if self.author_sort_order
                                                    else self.up_arrow_icon)
        self.auth_col.setIcon(self.blank_icon)

    def accepted(self):
        self.save_state()
        self.result = []
        for row in range(0,self.table.rowCount()):
            id   = self.table.item(row, 0).data(Qt.UserRole).toInt()[0]
            aut  = unicode(self.table.item(row, 0).text()).strip()
            sort = unicode(self.table.item(row, 1).text()).strip()
            link = unicode(self.table.item(row, 2).text()).strip()
            orig_aut,orig_sort,orig_link = self.authors[id]
            if orig_aut != aut or orig_sort != sort or orig_link != link:
                self.result.append((id, orig_aut, aut, sort, link))

    def do_recalc_author_sort(self):
        self.table.cellChanged.disconnect()
        for row in range(0,self.table.rowCount()):
            item = self.table.item(row, 0)
            aut  = unicode(item.text()).strip()
            c = self.table.item(row, 1)
            # Sometimes trailing commas are left by changing between copy algs
            c.setText(author_to_author_sort(aut).rstrip(','))
        self.table.setFocus(Qt.OtherFocusReason)
        self.table.cellChanged.connect(self.cell_changed)

    def do_auth_sort_to_author(self):
        self.table.cellChanged.disconnect()
        for row in range(0,self.table.rowCount()):
            item = self.table.item(row, 1)
            aus  = unicode(item.text()).strip()
            c = self.table.item(row, 0)
            # Sometimes trailing commas are left by changing between copy algs
            c.setText(aus)
        self.table.setFocus(Qt.OtherFocusReason)
        self.table.cellChanged.connect(self.cell_changed)

    def cell_changed(self, row, col):
        if col == 0:
            item = self.table.item(row, 0)
            aut  = unicode(item.text()).strip()
            amper = aut.find('&')
            if amper >= 0:
                error_dialog(self.parent(), _('Invalid author name'),
                        _('Author names cannot contain & characters.')).exec_()
                aut = aut.replace('&', '%')
                self.table.item(row, 0).setText(aut)
            c = self.table.item(row, 1)
            c.setText(author_to_author_sort(aut))
            item = c
        else:
            item  = self.table.item(row, col)
        self.table.setCurrentItem(item)
        self.table.scrollToItem(item)
