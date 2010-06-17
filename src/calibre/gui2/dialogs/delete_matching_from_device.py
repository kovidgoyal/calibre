#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt4.Qt import Qt, QDialog, QTableWidgetItem, QAbstractItemView, QIcon

from calibre.ebooks.metadata import authors_to_string
from calibre.gui2.dialogs.delete_matching_from_device_ui import Ui_DeleteMatchingFromDeviceDialog

class tableItem(QTableWidgetItem):

    def __init__(self, text):
        QTableWidgetItem.__init__(self, text)
        self.setFlags(Qt.ItemIsEnabled)

    def __ge__(self, other):
        return unicode(self.text()).lower() >= unicode(other.text()).lower()

    def __lt__(self, other):
        return unicode(self.text()).lower() < unicode(other.text()).lower()

class DeleteMatchingFromDeviceDialog(QDialog, Ui_DeleteMatchingFromDeviceDialog):

    def __init__(self, parent, items):
        QDialog.__init__(self, parent)
        Ui_DeleteMatchingFromDeviceDialog.__init__(self)
        self.setupUi(self)

        self.buttonBox.accepted.connect(self.accepted)
        self.table.cellClicked.connect(self.cell_clicked)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['', _('Location'), _('Title'),
                                              _('Author'), _('Format')])
        del_icon = QIcon(I('list_remove.svg'))
        rows = 0
        for card in items:
            rows += len(items[card][1])
        self.table.setRowCount(rows)
        row = 0
        for card in items:
            (model,books) = items[card]
            for (id,book) in books:
                item = QTableWidgetItem(del_icon, '')
                item.setData(Qt.UserRole, (model, id, book.path))
                self.table.setItem(row, 0, item)
                self.table.setItem(row, 1, tableItem(card))
                self.table.setItem(row, 2, tableItem(book.title))
                self.table.setItem(row, 3, tableItem(authors_to_string(book.authors)))
                self.table.setItem(row, 4, tableItem(book.path.rpartition('.')[2]))
                row += 1
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(2, Qt.AscendingOrder)

    def accepted(self):
        self.result = []
        for row in range(self.table.rowCount()):
            (model, id, path) = self.table.item(row, 0).data(Qt.UserRole).toPyObject()
            path = unicode(path)
            self.result.append((model, id, path))
        return

    def cell_clicked(self, row, col):
        if col == 0:
            self.table.removeRow(row)