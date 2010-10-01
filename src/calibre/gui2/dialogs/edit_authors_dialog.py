#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt4.Qt import Qt, QDialog, QTableWidgetItem, QAbstractItemView

from calibre.ebooks.metadata import author_to_author_sort
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.edit_authors_dialog_ui import Ui_EditAuthorsDialog

class tableItem(QTableWidgetItem):
    def __ge__(self, other):
        return unicode(self.text()).lower() >= unicode(other.text()).lower()

    def __lt__(self, other):
        return unicode(self.text()).lower() < unicode(other.text()).lower()

class EditAuthorsDialog(QDialog, Ui_EditAuthorsDialog):

    def __init__(self, parent, db, id_to_select):
        QDialog.__init__(self, parent)
        Ui_EditAuthorsDialog.__init__(self)
        self.setupUi(self)
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.buttonBox.accepted.connect(self.accepted)

        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([_('Author'), _('Author sort')])

        self.authors = {}
        auts = db.get_authors_with_ids()
        self.table.setRowCount(len(auts))
        select_item = None
        for row, (id, author, sort) in enumerate(auts):
            author = author.replace('|', ',')
            self.authors[id] = (author, sort)
            aut = tableItem(author)
            aut.setData(Qt.UserRole, id)
            sort = tableItem(sort)
            self.table.setItem(row, 0, aut)
            self.table.setItem(row, 1, sort)
            if id == id_to_select:
                select_item = sort
        self.table.resizeColumnsToContents()

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

        # set up author sort calc button
        self.recalc_author_sort.clicked.connect(self.do_recalc_author_sort)

        if select_item is not None:
            self.table.setCurrentItem(select_item)
            self.table.editItem(select_item)
        else:
            self.table.setCurrentCell(0, 0)

    def do_sort_by_author(self):
        self.author_order = 1 if self.author_order == 0 else 0
        self.table.sortByColumn(0, self.author_order)
        self.sort_by_author.setChecked(True)
        self.sort_by_author_sort.setChecked(False)

    def do_sort_by_author_sort(self):
        self.author_sort_order = 1 if self.author_sort_order == 0 else 0
        self.table.sortByColumn(1, self.author_sort_order)
        self.sort_by_author.setChecked(False)
        self.sort_by_author_sort.setChecked(True)

    def accepted(self):
        self.result = []
        for row in range(0,self.table.rowCount()):
            id   = self.table.item(row, 0).data(Qt.UserRole).toInt()[0]
            aut  = unicode(self.table.item(row, 0).text()).strip()
            sort = unicode(self.table.item(row, 1).text()).strip()
            orig_aut,orig_sort = self.authors[id]
            if orig_aut != aut or orig_sort != sort:
                self.result.append((id, orig_aut, aut, sort))

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
            item  = self.table.item(row, 1)
        self.table.setCurrentItem(item)
        self.table.scrollToItem(item)
