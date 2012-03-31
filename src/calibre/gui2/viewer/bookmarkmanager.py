from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'

import cPickle, os

from PyQt4.Qt import Qt, QDialog, QAbstractTableModel, QVariant, SIGNAL, \
    QModelIndex, QInputDialog, QLineEdit, QFileDialog

from calibre.gui2.viewer.bookmarkmanager_ui import Ui_BookmarkManager
from calibre.gui2 import NONE

class BookmarkManager(QDialog, Ui_BookmarkManager):
    def __init__(self, parent, bookmarks):
        QDialog.__init__(self, parent)

        self.setupUi(self)

        self.bookmarks = bookmarks[:]
        self.set_bookmarks()

        self.connect(self.button_revert, SIGNAL('clicked()'), self.set_bookmarks)
        self.connect(self.button_delete, SIGNAL('clicked()'), self.delete_bookmark)
        self.connect(self.button_edit, SIGNAL('clicked()'), self.edit_bookmark)
        self.connect(self.button_export, SIGNAL('clicked()'), self.export_bookmarks)
        self.connect(self.button_import, SIGNAL('clicked()'), self.import_bookmarks)

    def set_bookmarks(self, bookmarks=None):
        if bookmarks == None:
            bookmarks = self.bookmarks[:]
        self._model = BookmarkTableModel(self, bookmarks)
        self.bookmarks_table.setModel(self._model)
        self.bookmarks_table.resizeColumnsToContents()

    def delete_bookmark(self):
        indexes = self.bookmarks_table.selectionModel().selectedIndexes()
        if indexes != []:
            self._model.remove_row(indexes[0].row())

    def edit_bookmark(self):
        indexes = self.bookmarks_table.selectionModel().selectedIndexes()
        if indexes != []:
            title, ok = QInputDialog.getText(self, _('Edit bookmark'), _('New title for bookmark:'), QLineEdit.Normal, self._model.data(indexes[0], Qt.DisplayRole).toString())
            title = QVariant(unicode(title).strip())
            if ok and title:
                self._model.setData(indexes[0], title, Qt.EditRole)

    def get_bookmarks(self):
        return self._model.bookmarks

    def export_bookmarks(self):
        filename = QFileDialog.getSaveFileName(self, _("Export Bookmarks"),
                '%s%suntitled.pickle' % (os.getcwdu(), os.sep),
                _("Saved Bookmarks (*.pickle)"))
        if filename == '':
            return

        with open(filename, 'w') as fileobj:
            cPickle.dump(self._model.bookmarks, fileobj)

    def import_bookmarks(self):
        filename = QFileDialog.getOpenFileName(self, _("Import Bookmarks"), '%s' % os.getcwdu(), _("Pickled Bookmarks (*.pickle)"))
        if filename == '':
            return

        imported = None
        with open(filename, 'r') as fileobj:
            imported = cPickle.load(fileobj)

        if imported != None:
            bad = False
            try:
                for bm in imported:
                    if len(bm) != 2:
                        bad = True
                        break
            except:
                pass

            if not bad:
                bookmarks = self._model.bookmarks[:]
                for bm in imported:
                    if bm not in bookmarks and bm['title'] != 'calibre_current_page_bookmark':
                        bookmarks.append(bm)
                self.set_bookmarks(bookmarks)


class BookmarkTableModel(QAbstractTableModel):
    headers = [_("Name")]

    def __init__(self, parent, bookmarks):
        QAbstractTableModel.__init__(self, parent)

        self.bookmarks = bookmarks[:]

    def rowCount(self, parent):
        if parent and parent.isValid():
            return 0
        return len(self.bookmarks)

    def columnCount(self, parent):
        if parent and parent.isValid():
            return 0
        return len(self.headers)

    def data(self, index, role):
        if role in (Qt.DisplayRole, Qt.EditRole):
            ans = self.bookmarks[index.row()]['title']
            return NONE if ans is None else QVariant(ans)
        return NONE

    def setData(self, index, value, role):
        if role == Qt.EditRole:
            bm = self.bookmarks[index.row()]
            bm['title'] = unicode(value.toString()).strip()
            self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), index, index)
            return True
        return False

    def flags(self, index):
        flags = QAbstractTableModel.flags(self, index)
        flags |= Qt.ItemIsEditable
        return flags

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        if orientation == Qt.Horizontal:
            return QVariant(self.headers[section])
        else:
            return QVariant(section+1)

    def remove_row(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        del self.bookmarks[row]
        self.endRemoveRows()

