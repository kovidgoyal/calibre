#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt4.Qt import Qt, QDialog, QTableWidgetItem, QAbstractItemView

from calibre.ebooks.metadata import author_to_author_sort
from calibre.gui2.dialogs.sort_field_dialog_ui import Ui_SortFieldDialog

class tableItem(QTableWidgetItem):
    def __ge__(self, other):
        return unicode(self.text()).lower() >= unicode(other.text()).lower()

    def __lt__(self, other):
        return unicode(self.text()).lower() < unicode(other.text()).lower()

class SortFieldDialog(QDialog, Ui_SortFieldDialog):

    def __init__(self, parent, db, id_to_select):
        QDialog.__init__(self, parent)
        Ui_SortFieldDialog.__init__(self)
        self.setupUi(self)

        self.buttonBox.accepted.connect(self.accepted)
        self.table.cellChanged.connect(self.cell_changed)

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
                select_item = aut

        if select_item is not None:
            self.table.setCurrentItem(select_item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.AscendingOrder)

    def accepted(self):
        print 'accepted!'
        self.result = []
        for row in range(0,self.table.rowCount()):
            id   = self.table.item(row, 0).data(Qt.UserRole).toInt()[0]
            aut  = unicode(self.table.item(row, 0).text())
            sort = unicode(self.table.item(row, 1).text())
            print id, aut, sort
            orig_aut,orig_sort = self.authors[id]
            if orig_aut != aut or orig_sort != sort:
                self.result.append((id, orig_aut, aut, sort))

    def cell_changed(self, row, col):
        if col == 0:
            aut  = unicode(self.table.item(row, 0).text())
            c = self.table.item(row, 1)
            if c is not None:
                c.setText(author_to_author_sort(aut))
