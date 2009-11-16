#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Browsing book collection by tags.
'''

from itertools import izip

from PyQt4.Qt import Qt, QTreeView, \
                     QFont, SIGNAL, QSize, QIcon, QPoint, \
                     QAbstractItemModel, QVariant, QModelIndex
from calibre.gui2 import config, NONE

class TagsView(QTreeView):

    def __init__(self, *args):
        QTreeView.__init__(self, *args)
        self.setUniformRowHeights(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(30, 30))

    def set_database(self, db, match_all, popularity):
        self._model = TagsModel(db, parent=self)
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

    def clear(self):
        self.model().clear_state()

    def recount(self, *args):
        ci = self.currentIndex()
        if not ci.isValid():
            ci = self.indexAt(QPoint(10, 10))
        try:
            self.model().refresh()
        except: #Database connection could be closed if an integrity check is happening
            pass
        if ci.isValid():
            self.scrollTo(ci, QTreeView.PositionAtTop)

class TagTreeItem(object):

    CATEGORY = 0
    TAG      = 1
    ROOT     = 2

    def __init__(self, data=None, tag=None, category_icon=None, icon_map=None, parent=None):
        self.parent = parent
        self.children = []
        if self.parent is not None:
            self.parent.append(self)
        if data is None:
            self.type = self.ROOT
        else:
            self.type = self.TAG if category_icon is None else self.CATEGORY
        if self.type == self.CATEGORY:
            self.name, self.icon = map(QVariant, (data, category_icon))
            self.py_name = data
            self.bold_font = QFont()
            self.bold_font.setBold(True)
            self.bold_font = QVariant(self.bold_font)
        elif self.type == self.TAG:
            self.tag, self.icon_map = data, list(map(QVariant, icon_map))

    def __str__(self):
        if self.type == self.ROOT:
            return 'ROOT'
        if self.type == self.CATEGORY:
            return 'CATEGORY:'+self.name+':%d'%len(self.children)
        return 'TAG:'+self.tag.name

    def row(self):
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0

    def append(self, child):
        child.parent = self
        self.children.append(child)

    def data(self, role):
        if self.type == self.TAG:
            return self.tag_data(role)
        if self.type == self.CATEGORY:
            return self.category_data(role)
        return NONE

    def category_data(self, role):
        if role == Qt.DisplayRole:
            return self.name
        if role == Qt.DecorationRole:
            return self.icon
        if role == Qt.FontRole:
            return self.bold_font
        return NONE

    def tag_data(self, role):
        if role == Qt.DisplayRole:
            return QVariant('[%d] %s'%(self.tag.count, self.tag.name))
        if role == Qt.DecorationRole:
            return self.icon_map[self.tag.state]
        return NONE

    def toggle(self):
        if self.type == self.TAG:
            self.tag.state = (self.tag.state + 1)%3

class TagsModel(QAbstractItemModel):
    categories = [_('Authors'), _('Series'), _('Formats'), _('Publishers'), _('News'), _('Tags')]
    row_map    = ['author', 'series', 'format', 'publisher', 'news', 'tag']

    def __init__(self, db, parent=None):
        QAbstractItemModel.__init__(self, parent)
        self.cmap = tuple(map(QIcon, [I('user_profile.svg'),
                I('series.svg'), I('book.svg'), I('publisher.png'),
                I('news.svg'), I('tags.svg')]))
        self.icon_map = [QIcon(), QIcon(I('plus.svg')),
                QIcon(I('minus.svg'))]
        self.db = db
        self.ignore_next_search = 0
        self.root_item = TagTreeItem()
        data = self.db.get_categories(config['sort_by_popularity'])
        for i, r in enumerate(self.row_map):
            c = TagTreeItem(parent=self.root_item,
                    data=self.categories[i], category_icon=self.cmap[i])
            for tag in data[r]:
                t = TagTreeItem(parent=c, data=tag, icon_map=self.icon_map)

        self.db.add_listener(self.database_changed)
        self.connect(self, SIGNAL('need_refresh()'), self.refresh,
                Qt.QueuedConnection)

    def database_changed(self, event, ids):
        self.emit(SIGNAL('need_refresh()'))

    def refresh(self):
        data = self.db.get_categories(config['sort_by_popularity'])
        for i, r in enumerate(self.row_map):
            category = self.root_item.children[i]
            names = [t.tag.name for t in category.children]
            states = [t.tag.state for t in category.children]
            state_map = dict(izip(names, states))
            category_index = self.index(i, 0, QModelIndex())
            if len(category.children) > 0:
                self.beginRemoveRows(category_index, 0,
                        len(category.children)-1)
                category.children = []
                self.endRemoveRows()
            if len(data[r]) > 0:
                self.beginInsertRows(category_index, 0, len(data[r])-1)
                for tag in data[r]:
                    tag.state = state_map.get(tag.name, 0)
                    t = TagTreeItem(parent=category, data=tag, icon_map=self.icon_map)
                self.endInsertRows()

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if not index.isValid():
            return NONE
        item = index.internalPointer()
        return item.data(role)

    def headerData(self, *args):
        return NONE

    def flags(self, *args):
        return Qt.ItemIsEnabled|Qt.ItemIsSelectable


    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        try:
            child_item = parent_item.children[row]
        except IndexError:
            return QModelIndex()

        ans = self.createIndex(row, column, child_item)
        return ans

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        child_item = index.internalPointer()
        parent_item = child_item.parent

        if parent_item is self.root_item or parent_item is None:
            return QModelIndex()

        ans = self.createIndex(parent_item.row(), 0, parent_item)
        return ans

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        return len(parent_item.children)

    def reset_all_states(self):
        for i in xrange(self.rowCount(QModelIndex())):
            category_index = self.index(i, 0, QModelIndex())
            category_item = category_index.internalPointer()
            for j in xrange(self.rowCount(category_index)):
                tag_index = self.index(j, 0, category_index)
                tag_item = tag_index.internalPointer()
                tag = tag_item.tag
                if tag.state != 0:
                    tag.state = 0
                    self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                            tag_index, tag_index)

    def clear_state(self):
        self.reset_all_states()

    def reinit(self, *args, **kwargs):
        if self.ignore_next_search == 0:
            self.reset_all_states()
        else:
            self.ignore_next_search -= 1

    def toggle(self, index):
        if not index.isValid(): return False
        item = index.internalPointer()
        if item.type == TagTreeItem.TAG:
            item.toggle()
            self.ignore_next_search = 2
            self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'), index, index)
            return True
        return False

    def tokens(self):
        ans = []
        for i, key in enumerate(self.row_map):
            category_item = self.root_item.children[i]
            for tag_item in category_item.children:
                tag = tag_item.tag
                category = key if key != 'news' else 'tag'
                if tag.state > 0:
                    prefix = ' not ' if tag.state == 2 else ''
                    ans.append('%s%s:"%s"'%(prefix, category, tag.name))
        return ans


