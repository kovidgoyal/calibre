#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Browsing book collection by tags.
'''
from PyQt4.Qt import QAbstractItemModel, Qt, QVariant, QTreeView, QModelIndex, \
                     QFont, SIGNAL, QSize, QColor, QIcon
from calibre.gui2 import config
NONE = QVariant()

class TagsView(QTreeView):
    
    def __init__(self, *args):
        QTreeView.__init__(self, *args)
        self.setUniformRowHeights(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(30, 30))
    
    def set_database(self, db, match_all, popularity):
        self._model = TagsModel(db)
        self.popularity = popularity
        self.match_all = match_all
        self.setModel(self._model)
        self.connect(self, SIGNAL('clicked(QModelIndex)'), self.toggle)
        self.popularity.setChecked(config['sort_by_popularity'])
        self.connect(self.popularity, SIGNAL('stateChanged(int)'), self.sort_changed)
        
    def sort_changed(self, state):
        config.set('sort_by_popularity', state == Qt.Checked)
        self.model().refresh()
        
    def toggle(self, index):
        if self._model.toggle(index):
            self.emit(SIGNAL('tags_marked(PyQt_PyObject, PyQt_PyObject)'), 
                      self._model.tokens(), self.match_all.isChecked())

class TagsModel(QAbstractItemModel):
    
    categories = [_('Authors'), _('Series'), _('Formats'), _('Publishers'), _('Tags')]
    row_map    = {0: 'author', 1:'series', 2:'format', 3:'publisher', 4:'tag'} 
    
    def __init__(self, db):
        QAbstractItemModel.__init__(self)
        self.db = db
        self.ignore_next_search = False
        self._data = {}
        self.refresh()
        self.bold_font = QFont()
        self.bold_font.setBold(True)
        self.bold_font = QVariant(self.bold_font)
        self.status_map = [QColor(200,200,200, 0), QIcon(':/images/plus.svg'), QIcon(':/images/minus.svg')]
        self.status_map = list(map(QVariant, self.status_map))
        self.cmap = [QIcon(':/images/user_profile.svg'), QIcon(':/images/series.svg'), QIcon(':/images/book.svg'), QIcon(':/images/publisher.png'), QIcon(':/images/tags.svg')]
        self.cmap = list(map(QVariant, self.cmap))
        self.db.add_listener(self.database_changed)
    
    def database_changed(self, event, ids):
        self.refresh()
    
    def refresh(self):
        old_data = self._data
        self._data = self.db.get_categories(config['sort_by_popularity'])
        for key in old_data.keys():
            for tag in old_data[key]:
                try:
                    index = self._data[key].index(tag)
                    if index > -1:
                        self._data[key][index].state = tag.state
                except:
                    continue
        self.reset()
        
    def reinit(self, *args, **kwargs):
        if not self.ignore_next_search:
            for category in self._data.values():
                for tag in category:
                    tag.state = 0
            self.reset()
        self.ignore_next_search = False
        
    def toggle(self, index):
        if index.parent().isValid():
            category = self.row_map[index.parent().row()]
            tag = self._data[category][index.row()]
            tag.state = (tag.state + 1)%3
            self.ignore_next_search = True
            self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'), index, index)
            return True
        return False
    
    def tokens(self):
        ans = []
        for key in self.row_map.values():
            for tag in self._data[key]:
                if tag.state > 0:
                    if tag.state == 2:
                        tag = '!'+tag
                    ans.append((key, tag))
        return ans
    
    def index(self, row, col, parent=QModelIndex()):
        if parent.isValid():
            if parent.parent().isValid(): # parent is a tag
                return QModelIndex()
            try:
                category = self.row_map[parent.row()]
            except KeyError:
                return QModelIndex()
            if col == 0 and row < len(self._data[category]):
                return self.createIndex(row, col, parent.row())
            return QModelIndex()
        if col == 0 and row < len(self.categories):
            return self.createIndex(row, col, -1)
        return QModelIndex()
    
    def parent(self, index):
        if not index.isValid() or index.internalId() < 0:
            return QModelIndex()
        return self.createIndex(index.internalId(), 0, -1)
    
    def rowCount(self, parent):
        if not parent or not parent.isValid():
            return len(self.categories)
        if not parent.parent().isValid():
            return len(self._data[self.row_map[parent.row()]])
        return 0
        
    def columnCount(self, parent):
        return 1
    
    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled
        
    def category_data(self, index, role):
        if role == Qt.DisplayRole:
            row = index.row()
            return QVariant(self.categories[row])
        if role == Qt.FontRole:
            return self.bold_font
        if role == Qt.SizeHintRole:
            return QVariant(QSize(100, 40))
        if role == Qt.DecorationRole:
            return self.cmap[index.row()]
        return NONE
    
    def tag_data(self, index, role):
        category = self.row_map[index.parent().row()]
        if role == Qt.DisplayRole:
            return QVariant(self._data[category][index.row()].as_string())
        if role == Qt.DecorationRole:
            return self.status_map[self._data[category][index.row()].state]
        return NONE
        
    
    def data(self, index, role):
        if not index.parent().isValid():
            return self.category_data(index, role)
        if not index.parent().parent().isValid():
            return self.tag_data(index, role)
        return NONE
