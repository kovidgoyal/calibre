#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt4.Qt import Qt, QDialog, QTableWidgetItem, QAbstractItemView

from calibre import strftime
from calibre.ebooks.metadata import authors_to_string, authors_to_sort_string, \
                                    title_sort
from calibre.gui2.dialogs.delete_matching_from_device_ui import \
                                            Ui_DeleteMatchingFromDeviceDialog
from calibre.utils.date import UNDEFINED_DATE

class tableItem(QTableWidgetItem):

    def __init__(self, text):
        QTableWidgetItem.__init__(self, text)
        self.setFlags(Qt.ItemIsEnabled)
        self.sort = text.lower()

    def __ge__(self, other):
        return self.sort >= other.sort

    def __lt__(self, other):
        return self.sort < other.sort

class centeredTableItem(tableItem):

    def __init__(self, text):
        tableItem.__init__(self, text)
        self.setTextAlignment(Qt.AlignCenter)

class titleTableItem(tableItem):

    def __init__(self, text):
        tableItem.__init__(self, text)
        self.sort = title_sort(text.lower())

class authorTableItem(tableItem):

    def __init__(self, book):
        tableItem.__init__(self, authors_to_string(book.authors))
        if book.author_sort is not None:
            self.sort = book.author_sort.lower()
        else:
            self.sort = authors_to_sort_string(book.authors).lower()

class dateTableItem(tableItem):

    def __init__(self, date):
        if date is not None:
            tableItem.__init__(self, strftime('%x', date))
            self.sort = date
        else:
            tableItem.__init__(self, '')
            self.sort = UNDEFINED_DATE


class DeleteMatchingFromDeviceDialog(QDialog, Ui_DeleteMatchingFromDeviceDialog):

    def __init__(self, parent, items):
        QDialog.__init__(self, parent)
        Ui_DeleteMatchingFromDeviceDialog.__init__(self)
        self.setupUi(self)

        self.explanation.setText('<p>'+_('All checked books will be '
                                   '<b>permanently deleted</b> from your '
                                   'device. Please verify the list.')+'</p>')
        self.buttonBox.accepted.connect(self.accepted)
        self.buttonBox.rejected.connect(self.rejected)
        self.table.cellClicked.connect(self.cell_clicked)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
                                    ['', _('Location'), _('Title'), _('Author'),
                                      _('Date'), _('Format'), _('Path')])
        rows = 0
        for card in items:
            rows += len(items[card][1])
        self.table.setRowCount(rows)
        row = 0
        for card in items:
            (model,books) = items[card]
            for (id,book) in books:
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
                item.setCheckState(Qt.Checked)
                item.setData(Qt.UserRole, (model, id, book.path))
                self.table.setItem(row, 0, item)
                self.table.setItem(row, 1, tableItem(card))
                self.table.setItem(row, 2, titleTableItem(book.title))
                self.table.setItem(row, 3, authorTableItem(book))
                self.table.setItem(row, 4, dateTableItem(book.datetime))
                self.table.setItem(row, 5, centeredTableItem(book.path.rpartition('.')[2]))
                self.table.setItem(row, 6, tableItem(book.path))
                row += 1
        self.table.setCurrentCell(0, 1)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(2, Qt.AscendingOrder)
        self.table.setCurrentCell(0, 1)

    def cell_clicked(self, row, col):
        if col == 0:
            self.table.setCurrentCell(row, 1)

    def accepted(self):
        self.result = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() == Qt.Unchecked:
                continue
            (model, id, path) = self.table.item(row, 0).data(Qt.UserRole).toPyObject()
            path = unicode(path)
            self.result.append((model, id, path))
        return

