#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Browsing book collection by tags.
'''

from itertools import izip
from functools import partial

from PyQt4.Qt import Qt, QTreeView, QApplication, pyqtSignal, QFont, QSize, \
                     QIcon, QPoint, QVBoxLayout, QHBoxLayout, QComboBox,\
                     QAbstractItemModel, QVariant, QModelIndex, QMenu, \
                     QPushButton, QWidget, QItemDelegate, QString

from calibre.ebooks.metadata import title_sort
from calibre.gui2 import config, NONE
from calibre.library.field_metadata import TagsIcons, category_icon_map
from calibre.library.database2 import Tag
from calibre.utils.config import tweaks
from calibre.utils.icu import sort_key, upper, lower
from calibre.utils.search_query_parser import saved_searches
from calibre.utils.formatter import eval_formatter
from calibre.gui2 import error_dialog, warning_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.tag_categories import TagCategories
from calibre.gui2.dialogs.tag_list_editor import TagListEditor
from calibre.gui2.dialogs.edit_authors_dialog import EditAuthorsDialog
from calibre.gui2.widgets import HistoryLineEdit

class TagDelegate(QItemDelegate): # {{{

    def paint(self, painter, option, index):
        item = index.internalPointer()
        if item.type != TagTreeItem.TAG:
            QItemDelegate.paint(self, painter, option, index)
            return
        r = option.rect
        model = self.parent().model()
        icon = model.data(index, Qt.DecorationRole).toPyObject()
        painter.save()
        if item.tag.state != 0 or not config['show_avg_rating'] or \
                item.tag.avg_rating is None:
            icon.paint(painter, r, Qt.AlignLeft)
        else:
            painter.setOpacity(0.3)
            icon.paint(painter, r, Qt.AlignLeft)
            painter.setOpacity(1)
            rating = item.tag.avg_rating
            painter.setClipRect(r.left(), r.bottom()-int(r.height()*(rating/5.0)),
                    r.width(), r.height())
            icon.paint(painter, r, Qt.AlignLeft)
            painter.setClipRect(r)

        # Paint the text
        if item.boxed:
            painter.drawRoundedRect(r.adjusted(1,1,-1,-1), 5, 5)
        r.setLeft(r.left()+r.height()+3)
        painter.drawText(r, Qt.AlignLeft|Qt.AlignVCenter,
                        model.data(index, Qt.DisplayRole).toString())
        painter.restore()

    # }}}

class TagsView(QTreeView): # {{{

    refresh_required    = pyqtSignal()
    tags_marked         = pyqtSignal(object)
    user_category_edit  = pyqtSignal(object)
    tag_list_edit       = pyqtSignal(object, object)
    saved_search_edit   = pyqtSignal(object)
    author_sort_edit    = pyqtSignal(object, object)
    tag_item_renamed    = pyqtSignal()
    search_item_renamed = pyqtSignal()
    drag_drop_finished  = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent=None)
        self.tag_match = None
        self.disable_recounting = False
        self.setUniformRowHeights(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(30, 30))
        self.setTabKeyNavigation(True)
        self.setAlternatingRowColors(True)
        self.setAnimated(True)
        self.setHeaderHidden(True)
        self.setItemDelegate(TagDelegate(self))
        self.made_connections = False
        self.setAcceptDrops(True)
        self.setDragDropMode(self.DropOnly)
        self.setDropIndicatorShown(True)
        self.setAutoExpandDelay(500)
        self.pane_is_visible = False

    def set_pane_is_visible(self, to_what):
        pv = self.pane_is_visible
        self.pane_is_visible = to_what
        if to_what and not pv:
            self.recount()

    def set_database(self, db, tag_match, sort_by):
        self.hidden_categories = config['tag_browser_hidden_categories']
        self._model = TagsModel(db, parent=self,
                                hidden_categories=self.hidden_categories,
                                search_restriction=None,
                                drag_drop_finished=self.drag_drop_finished)
        self.pane_is_visible = True # because TagsModel.init did a recount
        self.sort_by = sort_by
        self.tag_match = tag_match
        self.db = db
        self.search_restriction = None
        self.setModel(self._model)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        pop = config['sort_tags_by']
        self.sort_by.setCurrentIndex(self.db.CATEGORY_SORTS.index(pop))
        if not self.made_connections:
            self.clicked.connect(self.toggle)
            self.customContextMenuRequested.connect(self.show_context_menu)
            self.refresh_required.connect(self.recount, type=Qt.QueuedConnection)
            self.sort_by.currentIndexChanged.connect(self.sort_changed)
            self.made_connections = True
        self.refresh_signal_processed = True
        db.add_listener(self.database_changed)

    def database_changed(self, event, ids):
        if self.refresh_signal_processed:
            self.refresh_signal_processed = False
            self.refresh_required.emit()

    @property
    def match_all(self):
        return self.tag_match and self.tag_match.currentIndex() > 0

    def sort_changed(self, pop):
        config.set('sort_tags_by', self.db.CATEGORY_SORTS[pop])
        self.recount()

    def set_search_restriction(self, s):
        if s:
            self.search_restriction = s
        else:
            self.search_restriction = None
        self.set_new_model()

    def mouseReleaseEvent(self, event):
        # Swallow everything except leftButton so context menus work correctly
        if event.button() == Qt.LeftButton:
            QTreeView.mouseReleaseEvent(self, event)

    def mouseDoubleClickEvent(self, event):
        # swallow these to avoid toggling and editing at the same time
        pass

    @property
    def search_string(self):
        tokens = self._model.tokens()
        joiner = ' and ' if self.match_all else ' or '
        return joiner.join(tokens)

    def toggle(self, index):
        modifiers = int(QApplication.keyboardModifiers())
        exclusive = modifiers not in (Qt.CTRL, Qt.SHIFT)
        if self._model.toggle(index, exclusive):
            self.tags_marked.emit(self.search_string)

    def conditional_clear(self, search_string):
        if search_string != self.search_string:
            self.clear()

    def context_menu_handler(self, action=None, category=None,
                             key=None, index=None):
        if not action:
            return
        try:
            if action == 'edit_item':
                self.edit(index)
                return
            if action == 'open_editor':
                self.tag_list_edit.emit(category, key)
                return
            if action == 'manage_categories':
                self.user_category_edit.emit(category)
                return
            if action == 'manage_searches':
                self.saved_search_edit.emit(category)
                return
            if action == 'edit_author_sort':
                self.author_sort_edit.emit(self, index)
                return
            if action == 'hide':
                self.hidden_categories.add(category)
            elif action == 'show':
                self.hidden_categories.discard(category)
            elif action == 'defaults':
                self.hidden_categories.clear()
            config.set('tag_browser_hidden_categories', self.hidden_categories)
            self.set_new_model()
        except:
            return

    def show_context_menu(self, point):
        index = self.indexAt(point)
        self.context_menu = QMenu(self)

        if index.isValid():
            item = index.internalPointer()
            tag_name = ''

            if item.type == TagTreeItem.TAG:
                tag_item = item
                tag_name = item.tag.name
                tag_id = item.tag.id
                item = item.parent

            if item.type == TagTreeItem.CATEGORY:
                category = unicode(item.name.toString())
                key = item.category_key
                # Verify that we are working with a field that we know something about
                if key not in self.db.field_metadata:
                    return True

                # If the user right-clicked on an editable item, then offer
                # the possibility of renaming that item
                if tag_name and \
                        (key in ['authors', 'tags', 'series', 'publisher', 'search'] or \
                        self.db.field_metadata[key]['is_custom'] and \
                        self.db.field_metadata[key]['datatype'] != 'rating'):
                    self.context_menu.addAction(_('Rename \'%s\'')%tag_name,
                            partial(self.context_menu_handler, action='edit_item',
                                    category=tag_item, index=index))
                    if key == 'authors':
                        self.context_menu.addAction(_('Edit sort for \'%s\'')%tag_name,
                                partial(self.context_menu_handler,
                                        action='edit_author_sort', index=tag_id))
                    self.context_menu.addSeparator()
                # Hide/Show/Restore categories
                self.context_menu.addAction(_('Hide category %s') % category,
                    partial(self.context_menu_handler, action='hide', category=category))
                if self.hidden_categories:
                    m = self.context_menu.addMenu(_('Show category'))
                    for col in sorted(self.hidden_categories, key=sort_key):
                        m.addAction(col,
                            partial(self.context_menu_handler, action='show', category=col))

                # Offer specific editors for tags/series/publishers/saved searches
                self.context_menu.addSeparator()
                if key in ['tags', 'publisher', 'series'] or \
                            self.db.field_metadata[key]['is_custom']:
                    self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='open_editor',
                                    category=tag_name, key=key))
                elif key == 'authors':
                    self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='edit_author_sort'))
                elif key == 'search':
                    self.context_menu.addAction(_('Manage Saved Searches'),
                        partial(self.context_menu_handler, action='manage_searches',
                                category=tag_name))

                # Always show the user categories editor
                self.context_menu.addSeparator()
                if category in self.db.prefs.get('user_categories', {}).keys():
                    self.context_menu.addAction(_('Manage User Categories'),
                            partial(self.context_menu_handler, action='manage_categories',
                                    category=category))
                else:
                    self.context_menu.addAction(_('Manage User Categories'),
                            partial(self.context_menu_handler, action='manage_categories',
                                    category=None))

        if self.hidden_categories:
            if not self.context_menu.isEmpty():
                self.context_menu.addSeparator()
            self.context_menu.addAction(_('Show all categories'),
                        partial(self.context_menu_handler, action='defaults'))

        if not self.context_menu.isEmpty():
            self.context_menu.popup(self.mapToGlobal(point))
        return True

    def dragMoveEvent(self, event):
        QTreeView.dragMoveEvent(self, event)
        self.setDropIndicatorShown(False)
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        item = index.internalPointer()
        flags = self._model.flags(index)
        if item.type == TagTreeItem.TAG and flags & Qt.ItemIsDropEnabled:
            self.setDropIndicatorShown(True)
        else:
            if item.type == TagTreeItem.CATEGORY:
                fm_dest = self.db.metadata_for_field(item.category_key)
                if fm_dest['kind'] == 'user':
                    md = event.mimeData()
                    fm_src = self.db.metadata_for_field(md.column_name)
                    if md.column_name in ['authors', 'publisher', 'series'] or \
                            (fm_src['is_custom'] and
                             fm_src['datatype'] in ['series', 'text'] and
                             not fm_src['is_multiple']):
                        self.setDropIndicatorShown(True)

    def clear(self):
        if self.model():
            self.model().clear_state()

    def is_visible(self, idx):
        item = idx.internalPointer()
        if getattr(item, 'type', None) == TagTreeItem.TAG:
            idx = idx.parent()
        return self.isExpanded(idx)

    def recount(self, *args):
        if self.disable_recounting or not self.pane_is_visible:
            return
        self.refresh_signal_processed = True
        ci = self.currentIndex()
        if not ci.isValid():
            ci = self.indexAt(QPoint(10, 10))
        path = self.model().path_for_index(ci) if self.is_visible(ci) else None
        try:
            if not self.model().refresh(): # categories changed!
                self.set_new_model()
                path = None
        except: #Database connection could be closed if an integrity check is happening
            pass
        if path:
            idx = self.model().index_for_path(path)
            if idx.isValid():
                self.setCurrentIndex(idx)
                self.scrollTo(idx, QTreeView.PositionAtCenter)

    # If the number of user categories changed,  if custom columns have come or
    # gone, or if columns have been hidden or restored, we must rebuild the
    # model. Reason: it is much easier than reconstructing the browser tree.
    def set_new_model(self, filter_categories_by = None):
        try:
            self._model = TagsModel(self.db, parent=self,
                                    hidden_categories=self.hidden_categories,
                                    search_restriction=self.search_restriction,
                                    drag_drop_finished=self.drag_drop_finished,
                                    filter_categories_by=filter_categories_by)
            self.setModel(self._model)
        except:
            # The DB must be gone. Set the model to None and hope that someone
            # will call set_database later. I don't know if this in fact works
            self._model = None
            self.setModel(None)
    # }}}

class TagTreeItem(object): # {{{

    CATEGORY = 0
    TAG      = 1
    ROOT     = 2

    def __init__(self, data=None, category_icon=None, icon_map=None,
                 parent=None, tooltip=None, category_key=None):
        self.parent = parent
        self.children = []
        self.boxed = False
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
            self.category_key = category_key
        elif self.type == self.TAG:
            icon_map[0] = data.icon
            self.tag, self.icon_state_map = data, list(map(QVariant, icon_map))
        self.tooltip = tooltip

    def __str__(self):
        if self.type == self.ROOT:
            return 'ROOT'
        if self.type == self.CATEGORY:
            return 'CATEGORY:'+str(QVariant.toString(self.name))+':%d'%len(self.children)
        return 'TAG:'+self.tag.name

    def row(self):
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0

    def append(self, child):
        child.parent = self
        self.children.append(child)

    def data(self, role):
        if role == Qt.UserRole:
            return self
        if self.type == self.TAG:
            return self.tag_data(role)
        if self.type == self.CATEGORY:
            return self.category_data(role)
        return NONE

    def category_data(self, role):
        if role == Qt.DisplayRole:
            return QVariant(self.py_name + ' [%d]'%len(self.child_tags()))
        if role == Qt.DecorationRole:
            return self.icon
        if role == Qt.FontRole:
            return self.bold_font
        if role == Qt.ToolTipRole and self.tooltip is not None:
            return QVariant(self.tooltip)
        return NONE

    def tag_data(self, role):
        tag = self.tag
        if tag.category == 'authors' and \
                tweaks['categories_use_field_for_author_name'] == 'author_sort':
            name = tag.sort
            tt_author = True
        else:
            name = tag.name
            tt_author = False
        if role == Qt.DisplayRole:
            if tag.count == 0:
                return QVariant('%s'%(name))
            else:
                return QVariant('[%d] %s'%(tag.count, name))
        if role == Qt.EditRole:
            return QVariant(tag.name)
        if role == Qt.DecorationRole:
            return self.icon_state_map[tag.state]
        if role == Qt.ToolTipRole:
            if tt_author:
                if tag.tooltip is not None:
                    return QVariant('(%s) %s'%(tag.name, tag.tooltip))
                else:
                    return QVariant(tag.name)
            if tag.tooltip is not None:
                return QVariant(tag.tooltip)
        return NONE

    def toggle(self):
        if self.type == self.TAG:
            self.tag.state = (self.tag.state + 1)%3

    def child_tags(self):
        res = []
        for t in self.children:
            if t.type == TagTreeItem.CATEGORY:
                for c in t.children:
                    res.append(c)
            else:
                res.append(t)
        return res
    # }}}

class TagsModel(QAbstractItemModel): # {{{

    def __init__(self, db, parent, hidden_categories=None,
            search_restriction=None, drag_drop_finished=None,
            filter_categories_by=None):
        QAbstractItemModel.__init__(self, parent)

        # must do this here because 'QPixmap: Must construct a QApplication
        # before a QPaintDevice'. The ':' in front avoids polluting either the
        # user-defined categories (':' at end) or columns namespaces (no ':').
        iconmap = {}
        for key in category_icon_map:
            iconmap[key] = QIcon(I(category_icon_map[key]))
        self.category_icon_map = TagsIcons(iconmap)

        self.categories_with_ratings = ['authors', 'series', 'publisher', 'tags']
        self.drag_drop_finished = drag_drop_finished

        self.icon_state_map = [None, QIcon(I('plus.png')), QIcon(I('minus.png'))]
        self.db = db
        self.tags_view = parent
        self.hidden_categories = hidden_categories
        self.search_restriction = search_restriction
        self.row_map = []
        self.filter_categories_by = filter_categories_by

        # get_node_tree cannot return None here, because row_map is empty
        data = self.get_node_tree(config['sort_tags_by'])
        self.root_item = TagTreeItem()
        for i, r in enumerate(self.row_map):
            if self.hidden_categories and self.categories[i] in self.hidden_categories:
                continue
            if self.db.field_metadata[r]['kind'] != 'user':
                tt = _('The lookup/search name is "{0}"').format(r)
            else:
                tt = ''
            TagTreeItem(parent=self.root_item,
                    data=self.categories[i],
                    category_icon=self.category_icon_map[r],
                    tooltip=tt, category_key=r)
        self.refresh(data=data)

    def mimeTypes(self):
        return ["application/calibre+from_library"]

    def dropMimeData(self, md, action, row, column, parent):
        if not md.hasFormat("application/calibre+from_library") or \
                action != Qt.CopyAction:
            return False
        idx = parent
        if idx.isValid():
            node = self.data(idx, Qt.UserRole)
            if node.type == TagTreeItem.TAG:
                fm = self.db.metadata_for_field(node.tag.category)
                if node.tag.category in \
                    ('tags', 'series', 'authors', 'rating', 'publisher') or \
                    (fm['is_custom'] and \
                        fm['datatype'] in ['text', 'rating', 'series']):
                    mime = 'application/calibre+from_library'
                    ids = list(map(int, str(md.data(mime)).split()))
                    self.handle_drop(node, ids)
                    return True
            elif node.type == TagTreeItem.CATEGORY:
                fm_dest = self.db.metadata_for_field(node.category_key)
                if fm_dest['kind'] == 'user':
                    fm_src = self.db.metadata_for_field(md.column_name)
                    if md.column_name in ['authors', 'publisher', 'series'] or \
                            (fm_src['is_custom'] and
                             fm_src['datatype'] in ['series', 'text'] and
                             not fm_src['is_multiple']):
                        mime = 'application/calibre+from_library'
                        ids = list(map(int, str(md.data(mime)).split()))
                        self.handle_user_category_drop(node, ids, md.column_name)
                        return True
        return False

    def handle_user_category_drop(self, on_node, ids, column):
        categories = self.db.prefs.get('user_categories', {})
        category = categories.get(on_node.category_key[:-1], None)
        if category is None:
            return
        fm_src = self.db.metadata_for_field(column)
        for id in ids:
            vmap = {}
            label = fm_src['label']
            if not fm_src['is_custom']:
                if label == 'authors':
                    items = self.db.get_authors_with_ids()
                    items = [(i[0], i[1].replace('|', ',')) for i in items]
                    value = self.db.authors(id, index_is_id=True)
                    value = [v.replace('|', ',') for v in value.split(',')]
                elif label == 'publisher':
                    items = self.db.get_publishers_with_ids()
                    value = self.db.publisher(id, index_is_id=True)
                elif label == 'series':
                    items = self.db.get_series_with_ids()
                    value = self.db.series(id, index_is_id=True)
            else:
                items = self.db.get_custom_items_with_ids(label=label)
                value = self.db.get_custom(id, label=label, index_is_id=True)
            if value is None:
                return
            if not isinstance(value, list):
                value = [value]
            for v in items:
                vmap[v[1]] = v[0]
            for val in value:
                for (v, c, id) in category:
                    if v == val and c == column:
                        break
                else:
                    category.append([val, column, vmap[val]])
            categories[on_node.category_key[:-1]] = category
            self.db.prefs.set('user_categories', categories)
            self.drag_drop_finished.emit(None, True)

    def handle_drop(self, on_node, ids):
        #print 'Dropped ids:', ids, on_node.tag
        key = on_node.tag.category
        if (key == 'authors' and len(ids) >= 5):
            if not confirm('<p>'+_('Changing the authors for several books can '
                           'take a while. Are you sure?')
                        +'</p>', 'tag_browser_drop_authors', self.parent()):
                return
        elif len(ids) > 15:
            if not confirm('<p>'+_('Changing the metadata for that many books '
                           'can take a while. Are you sure?')
                        +'</p>', 'tag_browser_many_changes', self.parent()):
                return

        fm = self.db.metadata_for_field(key)
        is_multiple = fm['is_multiple']
        val = on_node.tag.name
        for id in ids:
            mi = self.db.get_metadata(id, index_is_id=True)

            # Prepare to ignore the author, unless it is changed. Title is
            # always ignored -- see the call to set_metadata
            set_authors = False

            # Author_sort cannot change explicitly. Changing the author might
            # change it.
            mi.author_sort = None # Never will change by itself.

            if key == 'authors':
                mi.authors = [val]
                set_authors=True
            elif fm['datatype'] == 'rating':
                mi.set(key, len(val) * 2)
            elif fm['is_custom'] and fm['datatype'] == 'series':
                mi.set(key, val, extra=1.0)
            elif is_multiple:
                new_val = mi.get(key, [])
                if val in new_val:
                    # Fortunately, only one field can change, so the continue
                    # won't break anything
                    continue
                new_val.append(val)
                mi.set(key, new_val)
            else:
                mi.set(key, val)
            self.db.set_metadata(id, mi, set_title=False,
                                 set_authors=set_authors, commit=False)
        self.db.commit()
        self.drag_drop_finished.emit(ids, False)

    def set_search_restriction(self, s):
        self.search_restriction = s

    def get_node_tree(self, sort):
        old_row_map = self.row_map[:]
        self.row_map = []
        self.categories = []

        # Reconstruct the user categories, putting them into metadata
        self.db.field_metadata.remove_dynamic_categories()
        tb_cats = self.db.field_metadata
        for user_cat in sorted(self.db.prefs.get('user_categories', {}).keys(),
                               key=sort_key):
            cat_name = user_cat+':' # add the ':' to avoid name collision
            tb_cats.add_user_category(label=cat_name, name=user_cat)
        if len(saved_searches().names()):
            tb_cats.add_search_category(label='search', name=_('Searches'))

        # Now get the categories
        if self.search_restriction:
            data = self.db.get_categories(sort=sort,
                        icon_map=self.category_icon_map,
                        ids=self.db.search('', return_matches=True))
        else:
            data = self.db.get_categories(sort=sort, icon_map=self.category_icon_map)

        if self.filter_categories_by:
            for category in data.keys():
                data[category] = [t for t in data[category]
                        if lower(t.name).find(self.filter_categories_by) >= 0]

        tb_categories = self.db.field_metadata
        for category in tb_categories:
            if category in data: # The search category can come and go
                self.row_map.append(category)
                self.categories.append(tb_categories[category]['name'])
        if len(old_row_map) != 0 and len(old_row_map) != len(self.row_map):
            # A category has been added or removed. We must force a rebuild of
            # the model
            return None
        return data

    def refresh(self, data=None):
        sort_by = config['sort_tags_by']
        if data is None:
            data = self.get_node_tree(sort_by) # get category data
        if data is None:
            return False
        row_index = -1
        empty_tag = Tag('')
        collapse = tweaks['categories_collapse_more_than']
        collapse_model = tweaks['categories_collapse_model']
        if sort_by == 'name':
            collapse_template = tweaks['categories_collapsed_name_template']
        elif sort_by == 'rating':
            collapse_model = 'partition'
            collapse_template = tweaks['categories_collapsed_rating_template']
        else:
            collapse_model = 'partition'
            collapse_template = tweaks['categories_collapsed_popularity_template']
        collapse_letter = None

        for i, r in enumerate(self.row_map):
            if self.hidden_categories and self.categories[i] in self.hidden_categories:
                continue
            row_index += 1
            category = self.root_item.children[row_index]
            names = []
            states = []
            children = category.child_tags()
            states = [t.tag.state for t in children]
            names = [t.tag.name for names in children]
            state_map = dict(izip(names, states))
            category_index = self.index(row_index, 0, QModelIndex())
            category_node = category_index.internalPointer()
            if len(category.children) > 0:
                self.beginRemoveRows(category_index, 0,
                        len(category.children)-1)
                category.children = []
                self.endRemoveRows()
            cat_len = len(data[r])
            if cat_len <= 0:
                continue

            self.beginInsertRows(category_index, 0, len(data[r])-1)
            clear_rating = True if r not in self.categories_with_ratings and \
                                not self.db.field_metadata[r]['is_custom'] and \
                                not self.db.field_metadata[r]['kind'] == 'user' \
                            else False
            for idx,tag in enumerate(data[r]):
                if clear_rating:
                    tag.avg_rating = None
                tag.state = state_map.get(tag.name, 0)

                if collapse > 0 and cat_len > collapse:
                    if collapse_model == 'partition':
                        if (idx % collapse) == 0:
                            d = {'first': tag}
                            if cat_len > idx + collapse:
                                d['last'] = data[r][idx+collapse-1]
                            else:
                                d['last'] = empty_tag
                            name = eval_formatter.safe_format(collapse_template,
                                                              d, 'TAG_VIEW', None)
                            sub_cat = TagTreeItem(parent=category,
                                     data = name, tooltip = None,
                                     category_icon = category_node.icon,
                                     category_key=category_node.category_key)
                    else:
                        if upper(tag.sort[0]) != collapse_letter:
                            collapse_letter = upper(tag.name[0])
                            sub_cat = TagTreeItem(parent=category,
                                     data = collapse_letter,
                                     category_icon = category_node.icon,
                                     tooltip = None,
                                     category_key=category_node.category_key)
                    t = TagTreeItem(parent=sub_cat, data=tag,
                                        icon_map=self.icon_state_map)
                else:
                    t = TagTreeItem(parent=category, data=tag, icon_map=self.icon_state_map)
            self.endInsertRows()
        return True

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if not index.isValid():
            return NONE
        item = index.internalPointer()
        return item.data(role)

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return NONE
        # set up to reposition at the same item. We can do this except if
        # working with the last item and that item is deleted, in which case
        # we position at the parent label
        path = index.model().path_for_index(index)
        val = unicode(value.toString())
        if not val:
            error_dialog(self.tags_view, _('Item is blank'),
                        _('An item cannot be set to nothing. Delete it instead.')).exec_()
            return False
        item = index.internalPointer()
        key = item.parent.category_key
        # make certain we know about the item's category
        if key not in self.db.field_metadata:
            return False
        if key == 'authors':
            if val.find('&') >= 0:
                error_dialog(self.tags_view, _('Invalid author name'),
                        _('Author names cannot contain & characters.')).exec_()
                return False
        if key == 'search':
            if val in saved_searches().names():
                error_dialog(self.tags_view, _('Duplicate search name'),
                    _('The saved search name %s is already used.')%val).exec_()
                return False
            saved_searches().rename(unicode(item.data(role).toString()), val)
            item.tag.name = val
            self.tags_view.search_item_renamed.emit() # Does a refresh
        else:
            if key == 'series':
                self.db.rename_series(item.tag.id, val)
            elif key == 'publisher':
                self.db.rename_publisher(item.tag.id, val)
            elif key == 'tags':
                self.db.rename_tag(item.tag.id, val)
            elif key == 'authors':
                self.db.rename_author(item.tag.id, val)
            elif self.db.field_metadata[key]['is_custom']:
                self.db.rename_custom_item(item.tag.id, val,
                                    label=self.db.field_metadata[key]['label'])
            self.tags_view.tag_item_renamed.emit()
            item.tag.name = val
            self.refresh() # Should work, because no categories can have disappeared
        if path:
            idx = self.index_for_path(path)
            if idx.isValid():
                self.tags_view.setCurrentIndex(idx)
                self.tags_view.scrollTo(idx, QTreeView.PositionAtCenter)
        return True

    def headerData(self, *args):
        return NONE

    def flags(self, index, *args):
        ans = Qt.ItemIsEnabled|Qt.ItemIsSelectable|Qt.ItemIsEditable
        if index.isValid():
            node = self.data(index, Qt.UserRole)
            if node.type == TagTreeItem.TAG:
                fm = self.db.metadata_for_field(node.tag.category)
                if node.tag.category in \
                    ('tags', 'series', 'authors', 'rating', 'publisher') or \
                    (fm['is_custom'] and \
                        fm['datatype'] in ['text', 'rating', 'series']):
                    ans |= Qt.ItemIsDropEnabled
            else:
                ans |= Qt.ItemIsDropEnabled
        return ans

    def supportedDropActions(self):
        return Qt.CopyAction

    def path_for_index(self, index):
        ans = []
        while index.isValid():
            ans.append(index.row())
            index = self.parent(index)
        ans.reverse()
        return ans

    def index_for_path(self, path):
        parent = QModelIndex()
        for i in path:
            parent = self.index(i, 0, parent)
            if not parent.isValid():
                return QModelIndex()
        return parent

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
        parent_item = getattr(child_item, 'parent', None)

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

    def reset_all_states(self, except_=None):
        update_list = []
        def process_tag(tag_index, tag_item):
            tag = tag_item.tag
            if tag is except_:
                self.dataChanged.emit(tag_index, tag_index)
                return
            if tag.state != 0 or tag in update_list:
                tag.state = 0
                update_list.append(tag)
                self.dataChanged.emit(tag_index, tag_index)

        def process_level(category_index):
            for j in xrange(self.rowCount(category_index)):
                tag_index = self.index(j, 0, category_index)
                tag_item = tag_index.internalPointer()
                if tag_item.type == TagTreeItem.CATEGORY:
                    process_level(tag_index)
                else:
                    process_tag(tag_index, tag_item)

        for i in xrange(self.rowCount(QModelIndex())):
            process_level(self.index(i, 0, QModelIndex()))

    def clear_state(self):
        self.reset_all_states()

    def toggle(self, index, exclusive):
        if not index.isValid(): return False
        item = index.internalPointer()
        if item.type == TagTreeItem.TAG:
            item.toggle()
            if exclusive:
                self.reset_all_states(except_=item.tag)
            self.dataChanged.emit(index, index)
            return True
        return False

    def tokens(self):
        ans = []
        tags_seen = set()
        row_index = -1

        for i, key in enumerate(self.row_map):
            if self.hidden_categories and self.categories[i] in self.hidden_categories:
                continue
            row_index += 1
            if key.endswith(':'): # User category, so skip it. The tag will be marked in its real category
                continue
            category_item = self.root_item.children[row_index]
            for tag_item in category_item.child_tags():
                tag = tag_item.tag
                if tag.state > 0:
                    prefix = ' not ' if tag.state == 2 else ''
                    category = key if key != 'news' else 'tag'
                    if tag.name and tag.name[0] == u'\u2605': # char is a star. Assume rating
                        ans.append('%s%s:%s'%(prefix, category, len(tag.name)))
                    else:
                        if category == 'tags':
                            if tag.name in tags_seen:
                                continue
                            tags_seen.add(tag.name)
                        ans.append('%s%s:"=%s"'%(prefix, category, tag.name))
        return ans

    def find_node(self, key, txt, start_index):
        if not txt:
            return None
        txt = lower(txt)
        if start_index is None or not start_index.isValid():
            start_index = QModelIndex()
        self.node_found = None

        def process_tag(depth, tag_index, tag_item, start_path):
            path = self.path_for_index(tag_index)
            if depth < len(start_path) and path[depth] <= start_path[depth]:
                return False
            tag = tag_item.tag
            if tag is None:
                return False
            if lower(tag.name).find(txt) >= 0:
                self.node_found = tag_index
                return True
            return False

        def process_level(depth, category_index, start_path):
            path = self.path_for_index(category_index)
            if depth < len(start_path):
                if path[depth] < start_path[depth]:
                    return False
                if path[depth] > start_path[depth]:
                    start_path = path
            if key and category_index.internalPointer().category_key != key:
                return False
            for j in xrange(self.rowCount(category_index)):
                tag_index = self.index(j, 0, category_index)
                tag_item = tag_index.internalPointer()
                if tag_item.type == TagTreeItem.CATEGORY:
                    if process_level(depth+1, tag_index, start_path):
                        return True
                else:
                    if process_tag(depth+1, tag_index, tag_item, start_path):
                        return True
            return False

        for i in xrange(self.rowCount(QModelIndex())):
            if process_level(0, self.index(i, 0, QModelIndex()),
                                  self.path_for_index(start_index)):
                break
        return self.node_found

    def show_item_at_index(self, idx, box=False):
        if idx.isValid():
            tag_item = idx.internalPointer()
            self.tags_view.setCurrentIndex(idx)
            self.tags_view.scrollTo(idx, QTreeView.PositionAtCenter)
            if box:
                tag_item.boxed = True
                self.dataChanged.emit(idx, idx)

    def clear_boxed(self):
        def process_tag(tag_index, tag_item):
            if tag_item.boxed:
                tag_item.boxed = False
                self.dataChanged.emit(tag_index, tag_index)

        def process_level(category_index):
            for j in xrange(self.rowCount(category_index)):
                tag_index = self.index(j, 0, category_index)
                tag_item = tag_index.internalPointer()
                if tag_item.type == TagTreeItem.CATEGORY:
                    process_level(tag_index)
                else:
                    process_tag(tag_index, tag_item)

        for i in xrange(self.rowCount(QModelIndex())):
            process_level(self.index(i, 0, QModelIndex()))

    def get_filter_categories_by(self):
        return self.filter_categories_by

    # }}}

class TagBrowserMixin(object): # {{{

    def __init__(self, db):
        self.library_view.model().count_changed_signal.connect(self.tags_view.recount)
        self.tags_view.set_database(self.library_view.model().db,
                self.tag_match, self.sort_by)
        self.tags_view.tags_marked.connect(self.search.set_search_string)
        self.tags_view.tag_list_edit.connect(self.do_tags_list_edit)
        self.tags_view.user_category_edit.connect(self.do_user_categories_edit)
        self.tags_view.saved_search_edit.connect(self.do_saved_search_edit)
        self.tags_view.author_sort_edit.connect(self.do_author_sort_edit)
        self.tags_view.tag_item_renamed.connect(self.do_tag_item_renamed)
        self.tags_view.search_item_renamed.connect(self.saved_searches_changed)
        self.tags_view.drag_drop_finished.connect(self.drag_drop_finished)
        self.edit_categories.clicked.connect(lambda x:
                self.do_user_categories_edit())

    def do_user_categories_edit(self, on_category=None):
        d = TagCategories(self, self.library_view.model().db, on_category)
        d.exec_()
        if d.result() == d.Accepted:
            self.tags_view.set_new_model()
            self.tags_view.recount()

    def do_tags_list_edit(self, tag, category):
        db=self.library_view.model().db
        if category == 'tags':
            result = db.get_tags_with_ids()
            key = sort_key
        elif category == 'series':
            result = db.get_series_with_ids()
            key = lambda x:sort_key(title_sort(x))
        elif category == 'publisher':
            result = db.get_publishers_with_ids()
            key = sort_key
        else: # should be a custom field
            cc_label = None
            if category in db.field_metadata:
                cc_label = db.field_metadata[category]['label']
                result = db.get_custom_items_with_ids(label=cc_label)
            else:
                result = []
            key = sort_key

        d = TagListEditor(self, tag_to_match=tag, data=result, key=key)
        d.exec_()
        if d.result() == d.Accepted:
            to_rename = d.to_rename # dict of new text to old id
            to_delete = d.to_delete # list of ids
            rename_func = None
            if category == 'tags':
                rename_func = db.rename_tag
                delete_func = db.delete_tag_using_id
            elif category == 'series':
                rename_func = db.rename_series
                delete_func = db.delete_series_using_id
            elif category == 'publisher':
                rename_func = db.rename_publisher
                delete_func = db.delete_publisher_using_id
            else:
                rename_func = partial(db.rename_custom_item, label=cc_label)
                delete_func = partial(db.delete_custom_item_using_id, label=cc_label)
            if rename_func:
                for item in to_delete:
                    delete_func(item)
                for text in to_rename:
                        for old_id in to_rename[text]:
                            rename_func(old_id, new_name=unicode(text))

            # Clean up the library view
            self.do_tag_item_renamed()
            self.tags_view.set_new_model() # does a refresh for free

    def do_tag_item_renamed(self):
        # Clean up library view and search
        # get information to redo the selection
        rows = [r.row() for r in \
                self.library_view.selectionModel().selectedRows()]
        m = self.library_view.model()
        ids = [m.id(r) for r in rows]

        m.refresh(reset=False)
        m.research()
        self.library_view.select_rows(ids)
        # refreshing the tags view happens at the emit()/call() site

    def do_author_sort_edit(self, parent, id):
        db = self.library_view.model().db
        editor = EditAuthorsDialog(parent, db, id)
        d = editor.exec_()
        if d:
            for (id, old_author, new_author, new_sort) in editor.result:
                if old_author != new_author:
                    # The id might change if the new author already exists
                    id = db.rename_author(id, new_author)
                db.set_sort_field_for_author(id, unicode(new_sort),
                                             commit=False, notify=False)
            db.commit()
            self.library_view.model().refresh()
            self.tags_view.recount()

    def drag_drop_finished(self, ids, is_category):
        if is_category:
            self.tags_view.recount()
        else:
            self.library_view.model().refresh_ids(ids)

# }}}

class TagBrowserWidget(QWidget): # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.parent = parent
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0,0,0,0)

        search_layout = QHBoxLayout()
        self._layout.addLayout(search_layout)
        self.item_search = HistoryLineEdit(parent)
        try:
            self.item_search.lineEdit().setPlaceholderText(_('Find item in tag browser'))
        except:
            # Using Qt < 4.7
            pass
        self.item_search.setToolTip(_(
        'Search for items. This is a "contains" search; items containing the\n'
        'text anywhere in the name will be found. You can limit the search\n'
        'to particular categories using syntax similar to search. For example,\n'
        'tags:foo will find foo in any tag, but not in authors etc. Entering\n'
        '*foo will filter all categories at once, showing only those items\n'
        'containing the text "foo"'))
        search_layout.addWidget(self.item_search)
        self.search_button = QPushButton()
        self.search_button.setText(_('Find!'))
        self.search_button.setToolTip(_('Find the first/next matching item'))
        self.search_button.setFixedWidth(40)
        search_layout.addWidget(self.search_button)
        self.current_position = None
        self.search_button.clicked.connect(self.find)
        self.item_search.initialize('tag_browser_search')
        self.item_search.lineEdit().returnPressed.connect(self.do_find)
        self.item_search.lineEdit().textEdited.connect(self.find_text_changed)
        self.item_search.activated[QString].connect(self.do_find)
        self.item_search.completer().setCaseSensitivity(Qt.CaseSensitive)

        parent.tags_view = TagsView(parent)
        self.tags_view = parent.tags_view
        self._layout.addWidget(parent.tags_view)

        parent.sort_by = QComboBox(parent)
        # Must be in the same order as db2.CATEGORY_SORTS
        for x in (_('Sort by name'), _('Sort by popularity'),
                  _('Sort by average rating')):
            parent.sort_by.addItem(x)
        parent.sort_by.setToolTip(
                _('Set the sort order for entries in the Tag Browser'))
        parent.sort_by.setStatusTip(parent.sort_by.toolTip())
        parent.sort_by.setCurrentIndex(0)
        self._layout.addWidget(parent.sort_by)

        parent.tag_match = QComboBox(parent)
        for x in (_('Match any'), _('Match all')):
            parent.tag_match.addItem(x)
        parent.tag_match.setCurrentIndex(0)
        self._layout.addWidget(parent.tag_match)
        parent.tag_match.setToolTip(
                _('When selecting multiple entries in the Tag Browser '
                    'match any or all of them'))
        parent.tag_match.setStatusTip(parent.tag_match.toolTip())

        parent.edit_categories = QPushButton(_('Manage &user categories'), parent)
        self._layout.addWidget(parent.edit_categories)
        parent.edit_categories.setToolTip(
                _('Add your own categories to the Tag Browser'))
        parent.edit_categories.setStatusTip(parent.edit_categories.toolTip())

    def set_pane_is_visible(self, to_what):
        self.tags_view.set_pane_is_visible(to_what)

    def find_text_changed(self, str):
        self.current_position = None

    def do_find(self, str=None):
        self.current_position = None
        self.find()

    def find(self):
        model = self.tags_view.model()
        model.clear_boxed()
        txt = unicode(self.item_search.currentText()).strip()

        if txt.startswith('*'):
            self.tags_view.set_new_model(filter_categories_by=txt[1:])
            self.current_position = None
            return
        if model.get_filter_categories_by():
            self.tags_view.set_new_model(filter_categories_by=None)
            self.current_position = None
            model = self.tags_view.model()

        if not txt:
            return

        self.item_search.blockSignals(True)
        self.item_search.lineEdit().blockSignals(True)
        self.search_button.setFocus(True)
        idx = self.item_search.findText(txt, Qt.MatchFixedString)
        if idx < 0:
            self.item_search.insertItem(0, txt)
        else:
            t = self.item_search.itemText(idx)
            self.item_search.removeItem(idx)
            self.item_search.insertItem(0, t)
        self.item_search.setCurrentIndex(0)
        self.item_search.blockSignals(False)
        self.item_search.lineEdit().blockSignals(False)

        colon = txt.find(':')
        key = None
        if colon > 0:
            key = self.parent.library_view.model().db.\
                        field_metadata.search_term_to_field_key(txt[:colon])
            txt = txt[colon+1:]

        self.current_position = model.find_node(key, txt, self.current_position)
        if self.current_position:
            model.show_item_at_index(self.current_position, box=True)
        elif self.item_search.text():
            warning_dialog(self.tags_view, _('No item found'),
                        _('No (more) matches for that search')).exec_()



# }}}

