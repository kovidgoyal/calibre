#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Browsing book collection by tags.
'''
from PyQt4.Qt import QStandardItemModel, Qt, QTreeView, QStandardItem, \
                     QFont, SIGNAL, QSize, QIcon, QPoint, QPixmap
from calibre.gui2 import config

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

    def clear(self):
        self.model().clear_state()

    def recount(self, *args):
        ci = self.currentIndex()
        if not ci.isValid():
            ci = self.indexAt(QPoint(10, 10))
        self.model().refresh()
        if ci.isValid():
            self.scrollTo(ci, QTreeView.PositionAtTop)

class CategoryItem(QStandardItem):

    def __init__(self, category, display_text, tags, icon, font, icon_map):
        self.category = category
        self.tags = tags
        QStandardItem.__init__(self, icon, display_text)
        self.setFont(font)
        self.setSelectable(False)
        self.setSizeHint(QSize(100, 40))
        self.setEditable(False)
        for tag in tags:
            self.appendRow(TagItem(tag, icon_map))

class TagItem(QStandardItem):

    def __init__(self, tag, icon_map):
        self.icon_map = icon_map
        self.tag = tag
        QStandardItem.__init__(self, tag.as_string())
        self.set_icon()
        self.setEditable(False)
        self.setSelectable(False)

    def toggle(self):
        self.tag.state = (self.tag.state + 1)%3
        self.set_icon()

    def set_icon(self):
        self.setIcon(self.icon_map[self.tag.state])


class TagsModel(QStandardItemModel):

    categories = [_('Authors'), _('Series'), _('Formats'), _('Publishers'), _('News'), _('Tags')]
    row_map    = ['author', 'series', 'format', 'publisher', 'news', 'tag']

    def __init__(self, db):
        self.cmap = tuple(map(QIcon, [I('user_profile.svg'),
                I('series.svg'), I('book.svg'), I('publisher.png'),
                I('news.svg'), I('tags.svg')]))
        p = QPixmap(30, 30)
        p.fill(Qt.transparent)
        self.icon_map = [QIcon(p), QIcon(I('plus.svg')),
                QIcon(I('minus.svg'))]
        QStandardItemModel.__init__(self)
        self.db = db
        self.ignore_next_search = 0
        self._data = {}
        self.bold_font = QFont()
        self.bold_font.setBold(True)
        self.refresh()
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
        self.clear()
        root = self.invisibleRootItem()
        for r, category in enumerate(self.row_map):
            tags = self._data.get(category, [])
            root.appendRow(CategoryItem(category, self.categories[r],
                self._data[category], self.cmap[r], self.bold_font, self.icon_map))
        #self.reset()

    def reset_all_states(self):
        changed_indices = []
        for category in self._data.values():
            Category = self.find_category(category)
            for tag in category:
                if tag.state != 0:
                    tag.state = 0
                    if Category is not None:
                        Tag = self.find_tag(tag, Category)
                        if Tag is not None:
                            changed_indices.append(Tag.index())
        for idx in changed_indices:
            if idx.isValid():
                self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                        idx, idx)

    def clear_state(self):
        for category in self._data.values():
            for tag in category:
                tag.state = 0
        self.reset_all_states()

    def find_category(self, name):
        root = self.invisibleRootItem()
        for i in range(root.rowCount()):
            child = root.child(i)
            if getattr(child, 'category', None) == name:
                return child

    def find_tag(self, tag, category):
        for i in range(category.rowCount()):
            child = category.child(i)
            if getattr(child, 'tag', None) == tag:
                return child


    def reinit(self, *args, **kwargs):
        if self.ignore_next_search == 0:
            self.reset_all_states()
        else:
            self.ignore_next_search -= 1


    def toggle(self, index):
        if index.parent().isValid():
            category = self.row_map[index.parent().row()]
            tag = self._data[category][index.row()]
            self.invisibleRootItem().child(index.parent().row()).child(index.row()).toggle()
            self.ignore_next_search = 2
            self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'), index, index)
            return True
        return False

    def tokens(self):
        ans = []
        for key in self.row_map:
            for tag in self._data[key]:
                category = key if key != 'news' else 'tag'
                if tag.state > 0:
                    prefix = ' not ' if tag.state == 2 else ''
                    ans.append('%s%s:"%s"'%(prefix, category, tag))
        return ans


