__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'


from PyQt4.Qt import Qt, QDialog, QAbstractTableModel, QVariant, SIGNAL, \
    QModelIndex, QInputDialog, QLineEdit

from calibre.gui2.viewer.bookmarkmanager_ui import Ui_BookmarkManager
from calibre.gui2 import NONE, qstring_to_unicode

class BookmarkManager(QDialog, Ui_BookmarkManager):
    def __init__(self, parent, bookmarks):
        QDialog.__init__(self, parent)
        
        self.setupUi(self)
        
        self.bookmarks = bookmarks[:]
        self.set_bookmarks()
        
        self.connect(self.button_revert, SIGNAL('clicked()'), self.set_bookmarks)
        self.connect(self.button_delete, SIGNAL('clicked()'), self.delete_bookmark)
        self.connect(self.button_edit, SIGNAL('clicked()'), self.edit_bookmark)
        
    def set_bookmarks(self):
        self._model = BookmarkTableModel(self, self.bookmarks)
        self.bookmarks_table.setModel(self._model)
        
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
            ans = self.bookmarks[index.row()][0]
            return NONE if ans is None else QVariant(ans)
        return NONE
    
    def setData(self, index, value, role):
        if role == Qt.EditRole:
            self.bookmarks[index.row()] = (qstring_to_unicode(value.toString()).strip(), self.bookmarks[index.row()][1])
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

