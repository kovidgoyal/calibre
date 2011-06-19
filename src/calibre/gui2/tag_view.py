#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Browsing book collection by tags.
'''

import traceback, copy, cPickle

from itertools import izip, repeat
from functools import partial

from PyQt4.Qt import (Qt, QTreeView, QApplication, pyqtSignal, QFont, QSize,
                     QIcon, QPoint, QVBoxLayout, QHBoxLayout, QComboBox, QTimer,
                     QAbstractItemModel, QVariant, QModelIndex, QMenu, QFrame,
                     QWidget, QItemDelegate, QString, QLabel, QPushButton,
                     QShortcut, QKeySequence, SIGNAL, QMimeData, QToolButton)

from calibre.ebooks.metadata import title_sort
from calibre.gui2 import config, NONE, gprefs
from calibre.library.field_metadata import TagsIcons, category_icon_map
from calibre.library.database2 import Tag
from calibre.utils.config import tweaks
from calibre.utils.icu import sort_key, lower, strcmp
from calibre.utils.search_query_parser import saved_searches
from calibre.utils.formatter import eval_formatter
from calibre.gui2 import error_dialog, question_dialog
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

TAG_SEARCH_STATES = {'clear': 0, 'mark_plus': 1, 'mark_plusplus': 2,
                     'mark_minus': 3, 'mark_minusminus': 4}

class TagsView(QTreeView): # {{{

    refresh_required        = pyqtSignal()
    tags_marked             = pyqtSignal(object)
    edit_user_category      = pyqtSignal(object)
    delete_user_category    = pyqtSignal(object)
    del_item_from_user_cat  = pyqtSignal(object, object, object)
    add_item_to_user_cat    = pyqtSignal(object, object, object)
    add_subcategory         = pyqtSignal(object)
    tag_list_edit           = pyqtSignal(object, object)
    saved_search_edit       = pyqtSignal(object)
    rebuild_saved_searches  = pyqtSignal()
    author_sort_edit        = pyqtSignal(object, object)
    tag_item_renamed        = pyqtSignal()
    search_item_renamed     = pyqtSignal()
    drag_drop_finished      = pyqtSignal(object)
    restriction_error       = pyqtSignal()

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
        self.setDragEnabled(True)
        self.setDragDropMode(self.DragDrop)
        self.setDropIndicatorShown(True)
        self.setAutoExpandDelay(500)
        self.pane_is_visible = False
        if gprefs['tags_browser_collapse_at'] == 0:
            self.collapse_model = 'disable'
        else:
            self.collapse_model = gprefs['tags_browser_partition_method']
        self.search_icon = QIcon(I('search.png'))
        self.user_category_icon = QIcon(I('tb_folder.png'))
        self.delete_icon = QIcon(I('list_remove.png'))
        self.rename_icon = QIcon(I('edit-undo.png'))

    def set_pane_is_visible(self, to_what):
        pv = self.pane_is_visible
        self.pane_is_visible = to_what
        if to_what and not pv:
            self.recount()

    def reread_collapse_parameters(self):
        if gprefs['tags_browser_collapse_at'] == 0:
            self.collapse_model = 'disable'
        else:
            self.collapse_model = gprefs['tags_browser_partition_method']
        self.set_new_model(self._model.get_filter_categories_by())

    def set_database(self, db, tag_match, sort_by):
        hidden_cats = db.prefs.get('tag_browser_hidden_categories', None)
        self.hidden_categories = []
        # migrate from config to db prefs
        if hidden_cats is None:
            hidden_cats = config['tag_browser_hidden_categories']
        # strip out any non-existence field keys
        for cat in hidden_cats:
            if cat in db.field_metadata:
                self.hidden_categories.append(cat)
        db.prefs.set('tag_browser_hidden_categories', list(self.hidden_categories))
        self.hidden_categories = set(self.hidden_categories)

        old = getattr(self, '_model', None)
        if old is not None:
            old.break_cycles()
        self._model = TagsModel(db, parent=self,
                                hidden_categories=self.hidden_categories,
                                search_restriction=None,
                                drag_drop_finished=self.drag_drop_finished,
                                collapse_model=self.collapse_model)
        self.pane_is_visible = True # because TagsModel.init did a recount
        self.sort_by = sort_by
        self.tag_match = tag_match
        self.db = db
        self.search_restriction = None
        self.setModel(self._model)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        pop = config['sort_tags_by']
        self.sort_by.setCurrentIndex(self.db.CATEGORY_SORTS.index(pop))
        try:
            match_pop = self.db.MATCH_TYPE.index(config['match_tags_type'])
        except ValueError:
            match_pop = 0
        self.tag_match.setCurrentIndex(match_pop)
        if not self.made_connections:
            self.clicked.connect(self.toggle)
            self.customContextMenuRequested.connect(self.show_context_menu)
            self.refresh_required.connect(self.recount, type=Qt.QueuedConnection)
            self.sort_by.currentIndexChanged.connect(self.sort_changed)
            self.tag_match.currentIndexChanged.connect(self.match_changed)
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

    def match_changed(self, pop):
        try:
            config.set('match_tags_type', self.db.MATCH_TYPE[pop])
        except:
            pass

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
        self._toggle(index, None)

    def _toggle(self, index, set_to):
        '''
        set_to: if None, advance the state. Otherwise must be one of the values
        in TAG_SEARCH_STATES
        '''
        modifiers = int(QApplication.keyboardModifiers())
        exclusive = modifiers not in (Qt.CTRL, Qt.SHIFT)
        if self._model.toggle(index, exclusive, set_to=set_to):
            self.tags_marked.emit(self.search_string)

    def conditional_clear(self, search_string):
        if search_string != self.search_string:
            self.clear()

    def context_menu_handler(self, action=None, category=None,
                             key=None, index=None, search_state=None):
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
                self.edit_user_category.emit(category)
                return
            if action == 'search':
                self._toggle(index, set_to=search_state)
                return
            if action == 'add_to_category':
                tag = index.tag
                if len(index.children) > 0:
                    for c in index.children:
                        self.add_item_to_user_cat.emit(category, c.tag.original_name,
                                               c.tag.category)
                self.add_item_to_user_cat.emit(category, tag.original_name,
                                               tag.category)
                return
            if action == 'add_subcategory':
                self.add_subcategory.emit(key)
                return
            if action == 'search_category':
                self._toggle(index, set_to=search_state)
                return
            if action == 'delete_user_category':
                self.delete_user_category.emit(key)
                return
            if action == 'delete_search':
                saved_searches().delete(key)
                self.rebuild_saved_searches.emit()
                return
            if action == 'delete_item_from_user_category':
                tag = index.tag
                if len(index.children) > 0:
                    for c in index.children:
                        self.del_item_from_user_cat.emit(key, c.tag.original_name,
                                               c.tag.category)
                self.del_item_from_user_cat.emit(key, tag.original_name, tag.category)
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
            elif action == 'categorization':
                changed = self.collapse_model != category
                self.collapse_model = category
                if changed:
                    self.set_new_model(self._model.get_filter_categories_by())
                    gprefs['tags_browser_partition_method'] = category
            elif action == 'defaults':
                self.hidden_categories.clear()
            self.db.prefs.set('tag_browser_hidden_categories', list(self.hidden_categories))
            self.set_new_model()
        except:
            return

    def show_context_menu(self, point):
        def display_name( tag):
            if tag.category == 'search':
                n = tag.name
                if len(n) > 45:
                    n = n[:45] + '...'
                return "'" + n + "'"
            return tag.name

        index = self.indexAt(point)
        self.context_menu = QMenu(self)

        if index.isValid():
            item = index.internalPointer()
            tag = None

            if item.type == TagTreeItem.TAG:
                tag_item = item
                tag = item.tag
                while item.type != TagTreeItem.CATEGORY:
                    item = item.parent

            if item.type == TagTreeItem.CATEGORY:
                if not item.category_key.startswith('@'):
                    while item.parent != self._model.root_item:
                        item = item.parent
                category = unicode(item.name.toString())
                key = item.category_key
                # Verify that we are working with a field that we know something about
                if key not in self.db.field_metadata:
                    return True

                # Did the user click on a leaf node?
                if tag:
                    # If the user right-clicked on an editable item, then offer
                    # the possibility of renaming that item.
                    if tag.is_editable:
                        # Add the 'rename' items
                        self.context_menu.addAction(self.rename_icon,
                                                    _('Rename %s')%display_name(tag),
                            partial(self.context_menu_handler, action='edit_item',
                                    index=index))
                        if key == 'authors':
                            self.context_menu.addAction(_('Edit sort for %s')%display_name(tag),
                                    partial(self.context_menu_handler,
                                            action='edit_author_sort', index=tag.id))

                        # is_editable is also overloaded to mean 'can be added
                        # to a user category'
                        m = self.context_menu.addMenu(self.user_category_icon,
                                        _('Add %s to user category')%display_name(tag))
                        nt = self.model().category_node_tree
                        def add_node_tree(tree_dict, m, path):
                            p = path[:]
                            for k in sorted(tree_dict.keys(), key=sort_key):
                                p.append(k)
                                n = k[1:] if k.startswith('@') else k
                                m.addAction(self.user_category_icon, n,
                                    partial(self.context_menu_handler,
                                            'add_to_category',
                                            category='.'.join(p), index=tag_item))
                                if len(tree_dict[k]):
                                    tm = m.addMenu(self.user_category_icon,
                                                   _('Children of %s')%n)
                                    add_node_tree(tree_dict[k], tm, p)
                                p.pop()
                        add_node_tree(nt, m, [])
                    elif key == 'search':
                        self.context_menu.addAction(self.rename_icon,
                                                    _('Rename %s')%display_name(tag),
                            partial(self.context_menu_handler, action='edit_item',
                                    index=index))
                        self.context_menu.addAction(self.delete_icon,
                                _('Delete search %s')%display_name(tag),
                                partial(self.context_menu_handler,
                                        action='delete_search', key=tag.name))
                    if key.startswith('@') and not item.is_gst:
                        self.context_menu.addAction(self.user_category_icon,
                                _('Remove %s from category %s')%
                                            (display_name(tag), item.py_name),
                                partial(self.context_menu_handler,
                                        action='delete_item_from_user_category',
                                        key = key, index = tag_item))
                    # Add the search for value items. All leaf nodes are searchable
                    self.context_menu.addAction(self.search_icon,
                            _('Search for %s')%display_name(tag),
                            partial(self.context_menu_handler, action='search',
                                    search_state=TAG_SEARCH_STATES['mark_plus'],
                                    index=index))
                    self.context_menu.addAction(self.search_icon,
                            _('Search for everything but %s')%display_name(tag),
                            partial(self.context_menu_handler, action='search',
                                    search_state=TAG_SEARCH_STATES['mark_minus'],
                                    index=index))
                    self.context_menu.addSeparator()
                elif key.startswith('@') and not item.is_gst:
                    if item.can_be_edited:
                        self.context_menu.addAction(self.rename_icon,
                            _('Rename %s')%item.py_name,
                            partial(self.context_menu_handler, action='edit_item',
                                    index=index))
                    self.context_menu.addAction(self.user_category_icon,
                            _('Add sub-category to %s')%item.py_name,
                            partial(self.context_menu_handler,
                                    action='add_subcategory', key=key))
                    self.context_menu.addAction(self.delete_icon,
                            _('Delete user category %s')%item.py_name,
                            partial(self.context_menu_handler,
                                    action='delete_user_category', key=key))
                    self.context_menu.addSeparator()
                # Hide/Show/Restore categories
                self.context_menu.addAction(_('Hide category %s') % category,
                    partial(self.context_menu_handler, action='hide',
                            category=key))
                if self.hidden_categories:
                    m = self.context_menu.addMenu(_('Show category'))
                    for col in sorted(self.hidden_categories,
                            key=lambda x: sort_key(self.db.field_metadata[x]['name'])):
                        m.addAction(self.db.field_metadata[col]['name'],
                            partial(self.context_menu_handler, action='show', category=col))

                # search by category. Some categories are not searchable, such
                # as search and news
                if item.tag.is_searchable:
                    self.context_menu.addAction(self.search_icon,
                            _('Search for books in category %s')%category,
                            partial(self.context_menu_handler,
                                    action='search_category',
                                    index=self._model.createIndex(item.row(), 0, item),
                                    search_state=TAG_SEARCH_STATES['mark_plus']))
                    self.context_menu.addAction(self.search_icon,
                            _('Search for books not in category %s')%category,
                            partial(self.context_menu_handler,
                                    action='search_category',
                                    index=self._model.createIndex(item.row(), 0, item),
                                    search_state=TAG_SEARCH_STATES['mark_minus']))
                # Offer specific editors for tags/series/publishers/saved searches
                self.context_menu.addSeparator()
                if key in ['tags', 'publisher', 'series'] or \
                            self.db.field_metadata[key]['is_custom']:
                    self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='open_editor',
                                    category=tag.original_name if tag else None,
                                    key=key))
                elif key == 'authors':
                    self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='edit_author_sort'))
                elif key == 'search':
                    self.context_menu.addAction(_('Manage Saved Searches'),
                        partial(self.context_menu_handler, action='manage_searches',
                                category=tag.name if tag else None))

                # Always show the user categories editor
                self.context_menu.addSeparator()
                if key.startswith('@') and \
                        key[1:] in self.db.prefs.get('user_categories', {}).keys():
                    self.context_menu.addAction(_('Manage User Categories'),
                            partial(self.context_menu_handler, action='manage_categories',
                                    category=key[1:]))
                else:
                    self.context_menu.addAction(_('Manage User Categories'),
                            partial(self.context_menu_handler, action='manage_categories',
                                    category=None))

        if self.hidden_categories:
            if not self.context_menu.isEmpty():
                self.context_menu.addSeparator()
            self.context_menu.addAction(_('Show all categories'),
                        partial(self.context_menu_handler, action='defaults'))

        m = self.context_menu.addMenu(_('Change sub-categorization scheme'))
        da = m.addAction('Disable',
            partial(self.context_menu_handler, action='categorization', category='disable'))
        fla = m.addAction('By first letter',
            partial(self.context_menu_handler, action='categorization', category='first letter'))
        pa = m.addAction('Partition',
            partial(self.context_menu_handler, action='categorization', category='partition'))
        if self.collapse_model == 'disable':
            da.setCheckable(True)
            da.setChecked(True)
        elif self.collapse_model == 'first letter':
            fla.setCheckable(True)
            fla.setChecked(True)
        else:
            pa.setCheckable(True)
            pa.setChecked(True)

        if not self.context_menu.isEmpty():
            self.context_menu.popup(self.mapToGlobal(point))
        return True

    def dragMoveEvent(self, event):
        QTreeView.dragMoveEvent(self, event)
        self.setDropIndicatorShown(False)
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        src_is_tb = event.mimeData().hasFormat('application/calibre+from_tag_browser')
        item = index.internalPointer()
        flags = self._model.flags(index)
        if item.type == TagTreeItem.TAG and flags & Qt.ItemIsDropEnabled:
            self.setDropIndicatorShown(not src_is_tb)
            return
        if item.type == TagTreeItem.CATEGORY and not item.is_gst:
            fm_dest = self.db.metadata_for_field(item.category_key)
            if fm_dest['kind'] == 'user':
                if src_is_tb:
                    if event.dropAction() == Qt.MoveAction:
                        data = str(event.mimeData().data('application/calibre+from_tag_browser'))
                        src = cPickle.loads(data)
                        for s in src:
                            if s[0] == TagTreeItem.TAG and \
                                    (not s[1].startswith('@') or s[2]):
                                return
                    self.setDropIndicatorShown(True)
                    return
                md = event.mimeData()
                if hasattr(md, 'column_name'):
                    fm_src = self.db.metadata_for_field(md.column_name)
                    if md.column_name in ['authors', 'publisher', 'series'] or \
                            (fm_src['is_custom'] and (
                             (fm_src['datatype'] in ['series', 'text', 'enumeration'] and
                              not fm_src['is_multiple']) or
                             (fm_src['datatype'] == 'composite' and
                              fm_src['display'].get('make_category', False)))):
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
        self._model.show_item_at_path(path)

    # If the number of user categories changed,  if custom columns have come or
    # gone, or if columns have been hidden or restored, we must rebuild the
    # model. Reason: it is much easier than reconstructing the browser tree.
    def set_new_model(self, filter_categories_by=None):
        try:
            old = getattr(self, '_model', None)
            if old is not None:
                old.break_cycles()
            self._model = TagsModel(self.db, parent=self,
                                    hidden_categories=self.hidden_categories,
                                    search_restriction=self.search_restriction,
                                    drag_drop_finished=self.drag_drop_finished,
                                    filter_categories_by=filter_categories_by,
                                    collapse_model=self.collapse_model)
            self.setModel(self._model)
        except:
            # The DB must be gone. Set the model to None and hope that someone
            # will call set_database later. I don't know if this in fact works.
            # But perhaps a Bad Thing Happened, so print the exception
            traceback.print_exc()
            self._model = None
            self.setModel(None)
    # }}}

class TagTreeItem(object): # {{{

    CATEGORY = 0
    TAG      = 1
    ROOT     = 2

    def __init__(self, data=None, category_icon=None, icon_map=None,
                 parent=None, tooltip=None, category_key=None, temporary=False):
        self.parent = parent
        self.children = []
        self.id_set = set()
        self.is_gst = False
        self.boxed = False
        self.icon_state_map = list(map(QVariant, icon_map))
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
            self.temporary = temporary
            self.tag = Tag(data, category=category_key,
                   is_editable=category_key not in ['news', 'search', 'identifiers'],
                   is_searchable=category_key not in ['search'])

        elif self.type == self.TAG:
            self.icon_state_map[0] = QVariant(data.icon)
            self.tag = data
        if tooltip:
            self.tooltip = tooltip + ' '
        else:
            self.tooltip = ''

    def break_cycles(self):
        for x in self.children:
            try:
                x.break_cycles()
            except:
                pass
        self.parent = self.icon_state_map = self.bold_font = self.tag = \
                self.icon = self.children = None

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
        if role == Qt.EditRole:
            return QVariant(self.py_name)
        if role == Qt.DecorationRole:
            if self.tag.state:
                return self.icon_state_map[self.tag.state]
            return self.icon
        if role == Qt.FontRole:
            return self.bold_font
        if role == Qt.ToolTipRole and self.tooltip is not None:
            return QVariant(self.tooltip)
        return NONE

    def tag_data(self, role):
        tag = self.tag
        if tag.use_sort_as_name:
            name = tag.sort
            tt_author = True
        else:
            p = self
            while p.parent.type != self.ROOT:
                p = p.parent
            if not tag.is_hierarchical:
                name = tag.original_name
            else:
                name = tag.name
            tt_author = False
        if role == Qt.DisplayRole:
            count = len(self.id_set)
            count = count if count > 0 else tag.count
            if count == 0:
                return QVariant('%s'%(name))
            else:
                return QVariant('[%d] %s'%(count, name))
        if role == Qt.EditRole:
            return QVariant(tag.original_name)
        if role == Qt.DecorationRole:
            return self.icon_state_map[tag.state]
        if role == Qt.ToolTipRole:
            if tt_author:
                if tag.tooltip is not None:
                    return QVariant('(%s) %s'%(tag.name, tag.tooltip))
                else:
                    return QVariant(tag.name)
            if tag.tooltip:
                return QVariant(self.tooltip + tag.tooltip)
            else:
                return QVariant(self.tooltip)
        return NONE

    def toggle(self, set_to=None):
        '''
        set_to: None => advance the state, otherwise a value from TAG_SEARCH_STATES
        '''
        if set_to is None:
            while True:
                self.tag.state = (self.tag.state + 1)%5
                if self.tag.state == TAG_SEARCH_STATES['mark_plus'] or \
                        self.tag.state == TAG_SEARCH_STATES['mark_minus']:
                    if self.tag.is_searchable:
                        break
                elif self.tag.state == TAG_SEARCH_STATES['mark_plusplus'] or\
                        self.tag.state == TAG_SEARCH_STATES['mark_minusminus']:
                    if self.tag.is_searchable and len(self.children) and \
                                    self.tag.is_hierarchical == '5state':
                        break
                else:
                    break
        else:
            self.tag.state = set_to

    def all_children(self):
        res = []
        def recurse(nodes, res):
            for t in nodes:
                res.append(t)
                recurse(t.children, res)
        recurse(self.children, res)
        return res

    def child_tags(self):
        res = []
        def recurse(nodes, res):
            for t in nodes:
                if t.type != TagTreeItem.CATEGORY:
                    res.append(t)
                recurse(t.children, res)
        recurse(self.children, res)
        return res
    # }}}

class TagsModel(QAbstractItemModel): # {{{

    def __init__(self, db, parent, hidden_categories=None,
            search_restriction=None, drag_drop_finished=None,
            filter_categories_by=None, collapse_model='disable'):
        QAbstractItemModel.__init__(self, parent)

        # must do this here because 'QPixmap: Must construct a QApplication
        # before a QPaintDevice'. The ':' at the end avoids polluting either of
        # the other namespaces (alpha, '#', or '@')
        iconmap = {}
        for key in category_icon_map:
            iconmap[key] = QIcon(I(category_icon_map[key]))
        self.category_icon_map = TagsIcons(iconmap)

        self.categories_with_ratings = ['authors', 'series', 'publisher', 'tags']
        self.drag_drop_finished = drag_drop_finished

        self.icon_state_map = [None, QIcon(I('plus.png')), QIcon(I('plusplus.png')),
                               QIcon(I('minus.png')), QIcon(I('minusminus.png'))]
        self.db = db
        self.tags_view = parent
        self.hidden_categories = hidden_categories
        self.search_restriction = search_restriction
        self.row_map = []
        self.filter_categories_by = filter_categories_by
        self.collapse_model = collapse_model

        # get_node_tree cannot return None here, because row_map is empty. Note
        # that get_node_tree can indirectly change the user_categories dict.

        data = self.get_node_tree(config['sort_tags_by'])
        gst = db.prefs.get('grouped_search_terms', {})
        self.root_item = TagTreeItem(icon_map=self.icon_state_map)
        self.category_nodes = []

        last_category_node = None
        category_node_map = {}
        self.category_node_tree = {}
        for i, key in enumerate(self.row_map):
            if self.hidden_categories:
                if key in self.hidden_categories:
                    continue
                found = False
                for cat in self.hidden_categories:
                    if cat.startswith('@') and key.startswith(cat + '.'):
                        found = True
                if found:
                    continue
            is_gst = False
            if key.startswith('@') and key[1:] in gst:
                tt = _(u'The grouped search term name is "{0}"').format(key[1:])
                is_gst = True
            elif key == 'news':
                tt = ''
            else:
                tt = _(u'The lookup/search name is "{0}"').format(key)

            if key.startswith('@'):
                path_parts = [p for p in key.split('.')]
                path = ''
                last_category_node = self.root_item
                tree_root = self.category_node_tree
                for i,p in enumerate(path_parts):
                    path += p
                    if path not in category_node_map:
                        node = TagTreeItem(parent=last_category_node,
                                           data=p[1:] if i == 0 else p,
                                           category_icon=self.category_icon_map[key],
                                           tooltip=tt if path == key else path,
                                           category_key=path,
                                           icon_map=self.icon_state_map)
                        last_category_node = node
                        category_node_map[path] = node
                        self.category_nodes.append(node)
                        node.can_be_edited = (not is_gst) and (i == (len(path_parts)-1))
                        node.is_gst = is_gst
                        if not is_gst:
                            node.tag.is_hierarchical = '5state'
                        if not is_gst:
                            tree_root[p] = {}
                            tree_root = tree_root[p]
                    else:
                        last_category_node = category_node_map[path]
                        tree_root = tree_root[p]
                    path += '.'
            else:
                node = TagTreeItem(parent=self.root_item,
                                   data=self.categories[key],
                                   category_icon=self.category_icon_map[key],
                                   tooltip=tt, category_key=key,
                                   icon_map=self.icon_state_map)
                node.is_gst = False
                category_node_map[key] = node
                last_category_node = node
                self.category_nodes.append(node)
        self.refresh(data=data)

    def break_cycles(self):
        self.root_item.break_cycles()
        self.db = self.root_item = None

    def mimeTypes(self):
        return ["application/calibre+from_library",
                'application/calibre+from_tag_browser']

    def mimeData(self, indexes):
        data = []
        for idx in indexes:
            if idx.isValid():
                # get some useful serializable data
                node = idx.internalPointer()
                path = self.path_for_index(idx)
                if node.type == TagTreeItem.CATEGORY:
                    d = (node.type, node.py_name, node.category_key)
                else:
                    t = node.tag
                    p = node
                    while p.type != TagTreeItem.CATEGORY:
                        p = p.parent
                    d = (node.type, p.category_key, p.is_gst, t.original_name,
                         t.category, path)
                data.append(d)
            else:
                data.append(None)
        raw = bytearray(cPickle.dumps(data, -1))
        ans = QMimeData()
        ans.setData('application/calibre+from_tag_browser', raw)
        return ans

    def dropMimeData(self, md, action, row, column, parent):
        fmts = set([unicode(x) for x in md.formats()])
        if not fmts.intersection(set(self.mimeTypes())):
            return False
        if "application/calibre+from_library" in fmts:
            if action != Qt.CopyAction:
                return False
            return self.do_drop_from_library(md, action, row, column, parent)
        elif 'application/calibre+from_tag_browser' in fmts:
            return self.do_drop_from_tag_browser(md, action, row, column, parent)

    def do_drop_from_tag_browser(self, md, action, row, column, parent):
        if not parent.isValid():
            return False
        dest = parent.internalPointer()
        if dest.type != TagTreeItem.CATEGORY:
            return False
        if not md.hasFormat('application/calibre+from_tag_browser'):
            return False
        data = str(md.data('application/calibre+from_tag_browser'))
        src = cPickle.loads(data)
        for s in src:
            if s[0] != TagTreeItem.TAG:
                return False
        return self.move_or_copy_item_to_user_category(src, dest, action)

    def move_or_copy_item_to_user_category(self, src, dest, action):
        '''
        src is a list of tuples representing items to copy. The tuple is
        (type, containing category key, category key is global search term,
         full name, category key, path to node)
        The type must be TagTreeItem.TAG
        dest is the TagTreeItem node to receive the items
        action is Qt.CopyAction or Qt.MoveAction
        '''
        def process_source_node(user_cats, src_parent, src_parent_is_gst,
                                is_uc, dest_key, node):
            '''
            Copy/move an item and all its children to the destination
            '''
            copied = False
            src_name = node.tag.original_name
            src_cat = node.tag.category
            # delete the item if the source is a user category and action is move
            if is_uc and not src_parent_is_gst and src_parent in user_cats and \
                                    action == Qt.MoveAction:
                new_cat = []
                for tup in user_cats[src_parent]:
                    if src_name == tup[0] and src_cat == tup[1]:
                        continue
                    new_cat.append(list(tup))
                user_cats[src_parent] = new_cat
            else:
                copied = True

            # Now add the item to the destination user category
            add_it = True
            if not is_uc and src_cat == 'news':
                src_cat = 'tags'
            for tup in user_cats[dest_key]:
                if src_name == tup[0] and src_cat == tup[1]:
                    add_it = False
            if add_it:
                user_cats[dest_key].append([src_name, src_cat, 0])

            for c in node.children:
                copied = process_source_node(user_cats, src_parent, src_parent_is_gst,
                                             is_uc, dest_key, c)
            return copied

        user_cats = self.db.prefs.get('user_categories', {})
        parent_node = None
        copied = False
        path = None
        for s in src:
            src_parent, src_parent_is_gst = s[1:3]
            path = s[5]
            parent_node = src_parent

            if src_parent.startswith('@'):
                is_uc = True
                src_parent = src_parent[1:]
            else:
                is_uc = False
            dest_key = dest.category_key[1:]

            if dest_key not in user_cats:
                continue

            node = self.index_for_path(path)
            if node:
                copied = process_source_node(user_cats, src_parent, src_parent_is_gst,
                                             is_uc, dest_key, node.internalPointer())

        self.db.prefs.set('user_categories', user_cats)
        self.tags_view.recount()

        # Scroll to the item copied. If it was moved, scroll to the parent
        if parent_node is not None:
            self.clear_boxed()
            m = self.tags_view.model()
            if not copied:
                p = path[-1]
                if p == 0:
                    path = m.find_category_node(parent_node)
                else:
                    path[-1] = p - 1
            idx = m.index_for_path(path)
            self.tags_view.setExpanded(idx, True)
            if idx.internalPointer().type == TagTreeItem.TAG:
                m.show_item_at_index(idx, box=True)
            else:
                m.show_item_at_index(idx)
        return True

    def do_drop_from_library(self, md, action, row, column, parent):
        idx = parent
        if idx.isValid():
            self.tags_view.setCurrentIndex(idx)
            node = self.data(idx, Qt.UserRole)
            if node.type == TagTreeItem.TAG:
                fm = self.db.metadata_for_field(node.tag.category)
                if node.tag.category in \
                    ('tags', 'series', 'authors', 'rating', 'publisher') or \
                    (fm['is_custom'] and (
                            fm['datatype'] in ['text', 'rating', 'series',
                                               'enumeration'] or
                                (fm['datatype'] == 'composite' and
                                 fm['display'].get('make_category', False)))):
                    mime = 'application/calibre+from_library'
                    ids = list(map(int, str(md.data(mime)).split()))
                    self.handle_drop(node, ids)
                    return True
            elif node.type == TagTreeItem.CATEGORY:
                fm_dest = self.db.metadata_for_field(node.category_key)
                if fm_dest['kind'] == 'user':
                    fm_src = self.db.metadata_for_field(md.column_name)
                    if md.column_name in ['authors', 'publisher', 'series'] or \
                            (fm_src['is_custom'] and (
                             (fm_src['datatype'] in ['series', 'text', 'enumeration'] and
                              not fm_src['is_multiple']))or
                             (fm_src['datatype'] == 'composite' and
                              fm_src['display'].get('make_category', False))):
                        mime = 'application/calibre+from_library'
                        ids = list(map(int, str(md.data(mime)).split()))
                        self.handle_user_category_drop(node, ids, md.column_name)
                        return True
        return False

    def handle_user_category_drop(self, on_node, ids, column):
        categories = self.db.prefs.get('user_categories', {})
        category = categories.get(on_node.category_key[1:], None)
        if category is None:
            return
        fm_src = self.db.metadata_for_field(column)
        for id in ids:
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
                if fm_src['datatype'] != 'composite':
                    value = self.db.get_custom(id, label=label, index_is_id=True)
                else:
                    value = self.db.get_property(id, loc=fm_src['rec_index'],
                                                 index_is_id=True)
            if value is None:
                return
            if not isinstance(value, list):
                value = [value]
            for val in value:
                for (v, c, id) in category:
                    if v == val and c == column:
                        break
                else:
                    category.append([val, column, 0])
            categories[on_node.category_key[1:]] = category
            self.db.prefs.set('user_categories', categories)
            self.tags_view.recount()

    def handle_drop(self, on_node, ids):
        #print 'Dropped ids:', ids, on_node.tag
        key = on_node.tag.category
        if (key == 'authors' and len(ids) >= 5):
            if not confirm('<p>'+_('Changing the authors for several books can '
                           'take a while. Are you sure?')
                        +'</p>', 'tag_browser_drop_authors', self.tags_view):
                return
        elif len(ids) > 15:
            if not confirm('<p>'+_('Changing the metadata for that many books '
                           'can take a while. Are you sure?')
                        +'</p>', 'tag_browser_many_changes', self.tags_view):
                return

        fm = self.db.metadata_for_field(key)
        is_multiple = fm['is_multiple']
        val = on_node.tag.original_name
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
        self.drag_drop_finished.emit(ids)

    def set_search_restriction(self, s):
        self.search_restriction = s

    def get_node_tree(self, sort):
        old_row_map = self.row_map[:]
        self.row_map = []
        self.categories = {}

        # Get the categories
        if self.search_restriction:
            try:
                data = self.db.get_categories(sort=sort,
                        icon_map=self.category_icon_map,
                        ids=self.db.search('', return_matches=True))
            except:
                data = self.db.get_categories(sort=sort, icon_map=self.category_icon_map)
                self.tags_view.restriction_error.emit()
        else:
            data = self.db.get_categories(sort=sort, icon_map=self.category_icon_map)

        # Reconstruct the user categories, putting them into metadata
        self.db.field_metadata.remove_dynamic_categories()
        tb_cats = self.db.field_metadata
        for user_cat in sorted(self.db.prefs.get('user_categories', {}).keys(),
                               key=sort_key):
            cat_name = '@' + user_cat # add the '@' to avoid name collision
            while True:
                try:
                    tb_cats.add_user_category(label=cat_name, name=user_cat)
                    dot = cat_name.rfind('.')
                    if dot < 0:
                        break
                    cat_name = cat_name[:dot]
                except ValueError:
                    break

        for cat in sorted(self.db.prefs.get('grouped_search_terms', {}).keys(),
                          key=sort_key):
            if (u'@' + cat) in data:
                try:
                    tb_cats.add_user_category(label=u'@' + cat, name=cat)
                except ValueError:
                    traceback.print_exc()
        self.db.data.change_search_locations(self.db.field_metadata.get_search_terms())

        if len(saved_searches().names()):
            tb_cats.add_search_category(label='search', name=_('Searches'))

        if self.filter_categories_by:
            for category in data.keys():
                data[category] = [t for t in data[category]
                        if lower(t.name).find(self.filter_categories_by) >= 0]

        tb_categories = self.db.field_metadata
        for category in tb_categories:
            if category in data: # The search category can come and go
                self.row_map.append(category)
                self.categories[category] = tb_categories[category]['name']

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

        collapse = gprefs['tags_browser_collapse_at']
        collapse_model = self.collapse_model
        if collapse == 0:
            collapse_model = 'disable'
        elif collapse_model != 'disable':
            if sort_by == 'name':
                collapse_template = tweaks['categories_collapsed_name_template']
            elif sort_by == 'rating':
                collapse_model = 'partition'
                collapse_template = tweaks['categories_collapsed_rating_template']
            else:
                collapse_model = 'partition'
                collapse_template = tweaks['categories_collapsed_popularity_template']

        def process_one_node(category, state_map): # {{{
            collapse_letter = None
            category_index = self.createIndex(category.row(), 0, category)
            category_node = category_index.internalPointer()
            key = category_node.category_key
            if key not in data:
                return
            cat_len = len(data[key])
            if cat_len <= 0:
                return

            category_child_map = {}
            fm = self.db.field_metadata[key]
            clear_rating = True if key not in self.categories_with_ratings and \
                                not fm['is_custom'] and \
                                not fm['kind'] == 'user' \
                            else False
            in_uc = fm['kind'] == 'user'
            tt = key if in_uc else None

            if collapse_model == 'first letter':
                # Build a list of 'equal' first letters by looking for
                # overlapping ranges. If a range overlaps another, then the
                # letters are assumed to be equivalent. ICU collating is complex
                # beyond belief. This mechanism lets us determine the logical
                # first character from ICU's standpoint.
                chardict = {}
                for idx,tag in enumerate(data[key]):
                    if not tag.sort:
                        c = ' '
                    else:
                        c = icu_upper(tag.sort[0])
                    if c not in chardict:
                        chardict[c] = [idx, idx]
                    else:
                        chardict[c][1] = idx

                # sort the ranges to facilitate detecting overlap
                ranges = sorted([(v[0], v[1], c) for c,v in chardict.items()])

                # Create a list of 'first letters' to use for each item in
                # the category. The list is generated using the ranges. Overlaps
                # are filled with the character that first occurs.
                cl_list = list(repeat(None, len(data[key])))
                for t in ranges:
                    start = t[0]
                    c = t[2]
                    if cl_list[start] is None:
                        nc = c
                    else:
                        nc = cl_list[start]
                    for i in range(start, t[1]+1):
                        cl_list[i] = nc

            for idx,tag in enumerate(data[key]):
                if clear_rating:
                    tag.avg_rating = None
                tag.state = state_map.get((tag.name, tag.category), 0)

                if collapse_model != 'disable' and cat_len > collapse:
                    if collapse_model == 'partition':
                        if (idx % collapse) == 0:
                            d = {'first': tag}
                            if cat_len > idx + collapse:
                                d['last'] = data[key][idx+collapse-1]
                            else:
                                d['last'] = data[key][cat_len-1]
                            name = eval_formatter.safe_format(collapse_template,
                                                              d, 'TAG_VIEW', None)
                            self.beginInsertRows(category_index, 999998, 999999) #len(data[key])-1)
                            sub_cat = TagTreeItem(parent=category, data = name,
                                     tooltip = None, temporary=True,
                                     category_icon = category_node.icon,
                                     category_key=category_node.category_key,
                                     icon_map=self.icon_state_map)
                            sub_cat.tag.is_searchable = False
                            self.endInsertRows()
                    else: # by 'first letter'
                        cl = cl_list[idx]
                        if cl != collapse_letter:
                            collapse_letter = cl
                            sub_cat = TagTreeItem(parent=category,
                                     data = collapse_letter,
                                     category_icon = category_node.icon,
                                     tooltip = None, temporary=True,
                                     category_key=category_node.category_key,
                                     icon_map=self.icon_state_map)
                    node_parent = sub_cat
                else:
                    node_parent = category

                # category display order is important here. The following works
                # only of all the non-user categories are displayed before the
                # user categories
                components = [t.strip() for t in tag.original_name.split('.')
                              if t.strip()]
                if len(components) == 0 or '.'.join(components) != tag.original_name:
                    components = [tag.original_name]
                if (not tag.is_hierarchical) and (in_uc or
                        (fm['is_custom'] and fm['display'].get('is_names', False)) or
                        key in ['authors', 'publisher', 'news', 'formats', 'rating'] or
                        key not in self.db.prefs.get('categories_using_hierarchy', []) or
                        len(components) == 1):
                    self.beginInsertRows(category_index, 999998, 999999)
                    n = TagTreeItem(parent=node_parent, data=tag, tooltip=tt,
                                    icon_map=self.icon_state_map)
                    if tag.id_set is not None:
                        n.id_set |= tag.id_set
                    category_child_map[tag.name, tag.category] = n
                    self.endInsertRows()
                else:
                    for i,comp in enumerate(components):
                        if i == 0:
                            child_map = category_child_map
                        else:
                            child_map = dict([((t.tag.name, t.tag.category), t)
                                        for t in node_parent.children
                                            if t.type != TagTreeItem.CATEGORY])
                        if (comp,tag.category) in child_map:
                            node_parent = child_map[(comp,tag.category)]
                            node_parent.tag.is_hierarchical = \
                                '5state' if tag.category != 'search' else '3state'
                        else:
                            if i < len(components)-1:
                                t = copy.copy(tag)
                                t.original_name = '.'.join(components[:i+1])
                                if key != 'search':
                                    # This 'manufactured' intermediate node can
                                    # be searched, but cannot be edited.
                                    t.is_editable = False
                                else:
                                    t.is_searchable = t.is_editable = False
                            else:
                                t = tag
                                if not in_uc:
                                    t.original_name = t.name
                            t.is_hierarchical = \
                                '5state' if t.category != 'search' else '3state'
                            t.name = comp
                            self.beginInsertRows(category_index, 999998, 999999)
                            node_parent = TagTreeItem(parent=node_parent, data=t,
                                            tooltip=tt, icon_map=self.icon_state_map)
                            child_map[(comp,tag.category)] = node_parent
                            self.endInsertRows()
                        # This id_set must not be None
                        node_parent.id_set |= tag.id_set
            return
        # }}}

        for category in self.category_nodes:
            if len(category.children) > 0:
                child_map = category.children
                states = [c.tag.state for c in category.child_tags()]
                names = [(c.tag.name, c.tag.category) for c in category.child_tags()]
                state_map = dict(izip(names, states))
                # temporary sub-categories (the partitioning ones) must follow
                # the permanent sub-categories. This will happen naturally if
                # the temp ones are added by process_node
                ctags = [c for c in child_map if
                         c.type == TagTreeItem.CATEGORY and not c.temporary]
                start = len(ctags)
                self.beginRemoveRows(self.createIndex(category.row(), 0, category),
                                     start, len(child_map)-1)
                category.children = ctags
                self.endRemoveRows()
            else:
                state_map = {}

            process_one_node(category, state_map)
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
        val = unicode(value.toString()).strip()
        if not val:
            error_dialog(self.tags_view, _('Item is blank'),
                        _('An item cannot be set to nothing. Delete it instead.')).exec_()
            return False
        item = index.internalPointer()
        if item.type == TagTreeItem.CATEGORY and item.category_key.startswith('@'):
            if val.find('.') >= 0:
                error_dialog(self.tags_view, _('Rename user category'),
                    _('You cannot use periods in the name when '
                      'renaming user categories'), show=True)
                return False

            user_cats = self.db.prefs.get('user_categories', {})
            user_cat_keys_lower = [icu_lower(k) for k in user_cats]
            ckey = item.category_key[1:]
            ckey_lower = icu_lower(ckey)
            dotpos = ckey.rfind('.')
            if dotpos < 0:
                nkey = val
            else:
                nkey = ckey[:dotpos+1] + val
            nkey_lower = icu_lower(nkey)
            for c in sorted(user_cats.keys(), key=sort_key):
                if icu_lower(c).startswith(ckey_lower):
                    if len(c) == len(ckey):
                        if strcmp(ckey, nkey) != 0 and \
                                nkey_lower in user_cat_keys_lower:
                            error_dialog(self.tags_view, _('Rename user category'),
                                _('The name %s is already used')%nkey, show=True)
                            return False
                        user_cats[nkey] = user_cats[ckey]
                        del user_cats[ckey]
                    elif c[len(ckey)] == '.':
                        rest = c[len(ckey):]
                        if strcmp(ckey, nkey) != 0 and \
                                    icu_lower(nkey + rest) in user_cat_keys_lower:
                            error_dialog(self.tags_view, _('Rename user category'),
                                _('The name %s is already used')%(nkey+rest), show=True)
                            return False
                        user_cats[nkey + rest] = user_cats[ckey + rest]
                        del user_cats[ckey + rest]
            self.db.prefs.set('user_categories', user_cats)
            self.tags_view.set_new_model()
            # must not use 'self' below because the model has changed!
            p = self.tags_view.model().find_category_node('@' + nkey)
            self.tags_view.model().show_item_at_path(p)
            return True

        key = item.tag.category
        name = item.tag.original_name
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
            self.rename_item_in_all_user_categories(name, key, val)
            self.refresh() # Should work, because no categories can have disappeared
        self.show_item_at_path(path)
        return True

    def rename_item_in_all_user_categories(self, item_name, item_category, new_name):
        '''
        Search all user categories for items named item_name with category
        item_category and rename them to new_name. The caller must arrange to
        redisplay the tree as appropriate (recount or set_new_model)
        '''
        user_cats = self.db.prefs.get('user_categories', {})
        for k in user_cats.keys():
            new_contents = []
            for tup in user_cats[k]:
                if tup[0] == item_name and tup[1] == item_category:
                    new_contents.append([new_name, item_category, 0])
                else:
                    new_contents.append(tup)
            user_cats[k] = new_contents
        self.db.prefs.set('user_categories', user_cats)

    def delete_item_from_all_user_categories(self, item_name, item_category):
        '''
        Search all user categories for items named item_name with category
        item_category and delete them. The caller must arrange to redisplay the
        tree as appropriate (recount or set_new_model)
        '''
        user_cats = self.db.prefs.get('user_categories', {})
        for cat in user_cats.keys():
            self.delete_item_from_user_category(cat, item_name, item_category,
                                                user_categories=user_cats)
        self.db.prefs.set('user_categories', user_cats)

    def delete_item_from_user_category(self, category, item_name, item_category,
                                       user_categories=None):
        if user_categories is not None:
            user_cats = user_categories
        else:
            user_cats = self.db.prefs.get('user_categories', {})
        new_contents = []
        for tup in user_cats[category]:
            if tup[0] != item_name or tup[1] != item_category:
                new_contents.append(tup)
        user_cats[category] = new_contents
        if user_categories is None:
            self.db.prefs.set('user_categories', user_cats)

    def headerData(self, *args):
        return NONE

    def flags(self, index, *args):
        ans = Qt.ItemIsEnabled|Qt.ItemIsSelectable|Qt.ItemIsEditable
        if index.isValid():
            node = self.data(index, Qt.UserRole)
            if node.type == TagTreeItem.TAG:
                if node.tag.is_editable:
                    ans |= Qt.ItemIsDragEnabled
                fm = self.db.metadata_for_field(node.tag.category)
                if node.tag.category in \
                    ('tags', 'series', 'authors', 'rating', 'publisher') or \
                    (fm['is_custom'] and \
                        fm['datatype'] in ['text', 'rating', 'series', 'enumeration']):
                    ans |= Qt.ItemIsDropEnabled
            else:
                ans |= Qt.ItemIsDropEnabled
        return ans

    def supportedDropActions(self):
        return Qt.CopyAction|Qt.MoveAction

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
        def process_tag(tag_item):
            tag = tag_item.tag
            if tag is except_:
                tag_index = self.createIndex(tag_item.row(), 0, tag_item)
                self.dataChanged.emit(tag_index, tag_index)
            elif tag.state != 0 or tag in update_list:
                tag_index = self.createIndex(tag_item.row(), 0, tag_item)
                tag.state = 0
                update_list.append(tag)
                self.dataChanged.emit(tag_index, tag_index)
            for t in tag_item.children:
                process_tag(t)

        for t in self.root_item.children:
            process_tag(t)

    def clear_state(self):
        self.reset_all_states()

    def toggle(self, index, exclusive, set_to=None):
        '''
        exclusive: clear all states before applying this one
        set_to: None => advance the state, otherwise a value from TAG_SEARCH_STATES
        '''
        if not index.isValid(): return False
        item = index.internalPointer()
        item.toggle(set_to=set_to)
        if exclusive:
            self.reset_all_states(except_=item.tag)
        self.dataChanged.emit(index, index)
        return True

    def tokens(self):
        ans = []
        # Tags can be in the news and the tags categories. However, because of
        # the desire to use two different icons (tags and news), the nodes are
        # not shared, which can lead to the possibility of searching twice for
        # the same tag. The tags_seen set helps us prevent that
        tags_seen = set()
        # Tag nodes are in their own category and possibly in user categories.
        # They will be 'checked' in both places, but we want to put the node
        # into the search string only once. The nodes_seen set helps us do that
        nodes_seen = set()

        node_searches = {TAG_SEARCH_STATES['mark_plus']       : 'true',
                         TAG_SEARCH_STATES['mark_plusplus']   : '.true',
                         TAG_SEARCH_STATES['mark_minus']      : 'false',
                         TAG_SEARCH_STATES['mark_minusminus'] : '.false'}

        for node in self.category_nodes:
            if node.tag.state:
                if node.category_key == "news":
                    if node_searches[node.tag.state] == 'true':
                        ans.append('tags:"=' + _('News') + '"')
                    else:
                        ans.append('( not tags:"=' + _('News') + '")')
                else:
                    ans.append('%s:%s'%(node.category_key, node_searches[node.tag.state]))

            key = node.category_key
            for tag_item in node.all_children():
                if tag_item.type == TagTreeItem.CATEGORY:
                    if self.collapse_model == 'first letter' and \
                            tag_item.temporary and not key.startswith('@') \
                            and tag_item.tag.state:
                        if node_searches[tag_item.tag.state] == 'true':
                            ans.append('%s:~^%s'%(key, tag_item.py_name))
                        else:
                            ans.append('(not %s:~^%s )'%(key, tag_item.py_name))
                    continue
                tag = tag_item.tag
                if tag.state != TAG_SEARCH_STATES['clear']:
                    if tag.state == TAG_SEARCH_STATES['mark_minus'] or \
                            tag.state == TAG_SEARCH_STATES['mark_minusminus']:
                        prefix = ' not '
                    else:
                        prefix = ''
                    category = tag.category if key != 'news' else 'tag'
                    add_colon = False
                    if self.db.field_metadata[tag.category]['is_csp']:
                        add_colon = True

                    if tag.name and tag.name[0] == u'\u2605': # char is a star. Assume rating
                        ans.append('%s%s:%s'%(prefix, category, len(tag.name)))
                    else:
                        name = tag.original_name
                        use_prefix = tag.state in [TAG_SEARCH_STATES['mark_plusplus'],
                                                   TAG_SEARCH_STATES['mark_minusminus']]
                        if category == 'tags':
                            if name in tags_seen:
                                continue
                            tags_seen.add(name)
                        if tag in nodes_seen:
                            continue
                        nodes_seen.add(tag)
                        n = name.replace(r'"', r'\"')
                        if name.startswith('.'):
                            n = '.' + n
                        ans.append('%s%s:"=%s%s%s"'%(prefix, category,
                                                '.' if use_prefix else '', n,
                                                ':' if add_colon else ''))
        return ans

    def find_item_node(self, key, txt, start_path, equals_match=False):
        '''
        Search for an item (a node) in the tags browser list that matches both
        the key (exact case-insensitive match) and txt (not equals_match =>
        case-insensitive contains match; equals_match => case_insensitive
        equal match). Returns the path to the node. Note that paths are to a
        location (second item, fourth item, 25 item), not to a node. If
        start_path is None, the search starts with the topmost node. If the tree
        is changed subsequent to calling this method, the path can easily refer
        to a different node or no node at all.
        '''
        if not txt:
            return None
        txt = lower(txt) if not equals_match else txt
        self.path_found = None
        if start_path is None:
            start_path = []

        def process_tag(depth, tag_index, tag_item, start_path):
            path = self.path_for_index(tag_index)
            if depth < len(start_path) and path[depth] <= start_path[depth]:
                return False
            tag = tag_item.tag
            if tag is None:
                return False
            name = tag.original_name
            if (equals_match and strcmp(name, txt) == 0) or \
                    (not equals_match and lower(name).find(txt) >= 0):
                self.path_found = path
                return True
            for i,c in enumerate(tag_item.children):
                if process_tag(depth+1, self.createIndex(i, 0, c), c, start_path):
                    return True
            return False

        def process_level(depth, category_index, start_path):
            path = self.path_for_index(category_index)
            if depth < len(start_path):
                if path[depth] < start_path[depth]:
                    return False
                if path[depth] > start_path[depth]:
                    start_path = path
            my_key = category_index.internalPointer().category_key
            for j in xrange(self.rowCount(category_index)):
                tag_index = self.index(j, 0, category_index)
                tag_item = tag_index.internalPointer()
                if tag_item.type == TagTreeItem.CATEGORY:
                    if process_level(depth+1, tag_index, start_path):
                        return True
                elif not key or strcmp(key, my_key) == 0:
                    if process_tag(depth+1, tag_index, tag_item, start_path):
                        return True
            return False

        for i in xrange(self.rowCount(QModelIndex())):
            if process_level(0, self.index(i, 0, QModelIndex()), start_path):
                break
        return self.path_found

    def find_category_node(self, key, parent=QModelIndex()):
        '''
        Search for an category node (a top-level node) in the tags browser list
        that matches the key (exact case-insensitive match). Returns the path to
        the node. Paths are as in find_item_node.
        '''
        if not key:
            return None

        for i in xrange(self.rowCount(parent)):
            idx = self.index(i, 0, parent)
            node = idx.internalPointer()
            if node.type == TagTreeItem.CATEGORY:
                ckey = node.category_key
                if strcmp(ckey, key) == 0:
                    return self.path_for_index(idx)
                if len(node.children):
                    v = self.find_category_node(key, idx)
                    if v is not None:
                        return v
        return None

    def show_item_at_path(self, path, box=False):
        '''
        Scroll the browser and open categories to show the item referenced by
        path. If possible, the item is placed in the center. If box=True, a
        box is drawn around the item.
        '''
        if path:
            self.show_item_at_index(self.index_for_path(path), box)

    def show_item_at_index(self, idx, box=False):
        if idx.isValid():
            self.tags_view.setCurrentIndex(idx)
            self.tags_view.scrollTo(idx, QTreeView.PositionAtCenter)
            if box:
                tag_item = idx.internalPointer()
                tag_item.boxed = True
                self.dataChanged.emit(idx, idx)

    def clear_boxed(self):
        '''
        Clear all boxes around items.
        '''
        def process_tag(tag_index, tag_item):
            if tag_item.boxed:
                tag_item.boxed = False
                self.dataChanged.emit(tag_index, tag_index)
            for i,c in enumerate(tag_item.children):
                process_tag(self.index(i, 0, tag_index), c)

        def process_level(category_index):
            for j in xrange(self.rowCount(category_index)):
                tag_index = self.index(j, 0, category_index)
                tag_item = tag_index.internalPointer()
                if tag_item.boxed:
                    tag_item.boxed = False
                    self.dataChanged.emit(tag_index, tag_index)
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
        self.tags_view.set_database(db, self.tag_match, self.sort_by)
        self.tags_view.tags_marked.connect(self.search.set_search_string)
        self.tags_view.tag_list_edit.connect(self.do_tags_list_edit)
        self.tags_view.edit_user_category.connect(self.do_edit_user_categories)
        self.tags_view.delete_user_category.connect(self.do_delete_user_category)
        self.tags_view.del_item_from_user_cat.connect(self.do_del_item_from_user_cat)
        self.tags_view.add_subcategory.connect(self.do_add_subcategory)
        self.tags_view.add_item_to_user_cat.connect(self.do_add_item_to_user_cat)
        self.tags_view.saved_search_edit.connect(self.do_saved_search_edit)
        self.tags_view.rebuild_saved_searches.connect(self.do_rebuild_saved_searches)
        self.tags_view.author_sort_edit.connect(self.do_author_sort_edit)
        self.tags_view.tag_item_renamed.connect(self.do_tag_item_renamed)
        self.tags_view.search_item_renamed.connect(self.saved_searches_changed)
        self.tags_view.drag_drop_finished.connect(self.drag_drop_finished)
        self.tags_view.restriction_error.connect(self.do_restriction_error,
                                                 type=Qt.QueuedConnection)

        for text, func, args, cat_name in (
             (_('Manage Authors'),
                        self.do_author_sort_edit, (self, None), 'authors'),
             (_('Manage Series'),
                        self.do_tags_list_edit, (None, 'series'), 'series'),
             (_('Manage Publishers'),
                        self.do_tags_list_edit, (None, 'publisher'), 'publisher'),
             (_('Manage Tags'),
                        self.do_tags_list_edit, (None, 'tags'), 'tags'),
             (_('Manage User Categories'),
                        self.do_edit_user_categories, (None,), 'user:'),
             (_('Manage Saved Searches'),
                        self.do_saved_search_edit, (None,), 'search')
            ):
            self.manage_items_button.menu().addAction(
                                        QIcon(I(category_icon_map[cat_name])),
                                        text, partial(func, *args))

    def do_restriction_error(self):
        error_dialog(self.tags_view, _('Invalid search restriction'),
                         _('The current search restriction is invalid'), show=True)

    def do_add_subcategory(self, on_category_key, new_category_name=None):
        '''
        Add a subcategory to the category 'on_category'. If new_category_name is
        None, then a default name is shown and the user is offered the
        opportunity to edit the name.
        '''
        db = self.library_view.model().db
        user_cats = db.prefs.get('user_categories', {})

        # Ensure that the temporary name we will use is not already there
        i = 0
        if new_category_name is not None:
            new_name = new_category_name.replace('.', '')
        else:
            new_name = _('New Category').replace('.', '')
        n = new_name
        while True:
            new_cat = on_category_key[1:] + '.' + n
            if new_cat not in user_cats:
                break
            i += 1
            n = new_name + unicode(i)
        # Add the new category
        user_cats[new_cat] = []
        db.prefs.set('user_categories', user_cats)
        self.tags_view.set_new_model()
        m = self.tags_view.model()
        idx = m.index_for_path(m.find_category_node('@' + new_cat))
        m.show_item_at_index(idx)
        # Open the editor on the new item to rename it
        if new_category_name is None:
            self.tags_view.edit(idx)

    def do_edit_user_categories(self, on_category=None):
        '''
        Open the user categories editor.
        '''
        db = self.library_view.model().db
        d = TagCategories(self, db, on_category)
        if d.exec_() == d.Accepted:
            db.prefs.set('user_categories', d.categories)
            db.field_metadata.remove_user_categories()
            for k in d.categories:
                db.field_metadata.add_user_category('@' + k, k)
            db.data.change_search_locations(db.field_metadata.get_search_terms())
            self.tags_view.set_new_model()

    def do_delete_user_category(self, category_name):
        '''
        Delete the user category named category_name. Any leading '@' is removed
        '''
        if category_name.startswith('@'):
            category_name = category_name[1:]
        db = self.library_view.model().db
        user_cats = db.prefs.get('user_categories', {})
        cat_keys = sorted(user_cats.keys(), key=sort_key)
        has_children = False
        found = False
        for k in cat_keys:
            if k == category_name:
                found = True
                has_children = len(user_cats[k])
            elif k.startswith(category_name + '.'):
                has_children = True
        if not found:
            return error_dialog(self.tags_view, _('Delete user category'),
                         _('%s is not a user category')%category_name, show=True)
        if has_children:
            if not question_dialog(self.tags_view, _('Delete user category'),
                                   _('%s contains items. Do you really '
                                     'want to delete it?')%category_name):
                return
        for k in cat_keys:
            if k == category_name:
                del user_cats[k]
            elif k.startswith(category_name + '.'):
                del user_cats[k]
        db.prefs.set('user_categories', user_cats)
        self.tags_view.set_new_model()

    def do_del_item_from_user_cat(self, user_cat, item_name, item_category):
        '''
        Delete the item (item_name, item_category) from the user category with
        key user_cat. Any leading '@' characters are removed
        '''
        if user_cat.startswith('@'):
            user_cat = user_cat[1:]
        db = self.library_view.model().db
        user_cats = db.prefs.get('user_categories', {})
        if user_cat not in user_cats:
            error_dialog(self.tags_view, _('Remove category'),
                         _('User category %s does not exist')%user_cat,
                         show=True)
            return
        self.tags_view.model().delete_item_from_user_category(user_cat,
                                                      item_name, item_category)
        self.tags_view.recount()

    def do_add_item_to_user_cat(self, dest_category, src_name, src_category):
        '''
        Add the item src_name in src_category to the user category
        dest_category. Any leading '@' is removed
        '''
        db = self.library_view.model().db
        user_cats = db.prefs.get('user_categories', {})

        if dest_category and dest_category.startswith('@'):
            dest_category = dest_category[1:]

        if dest_category not in user_cats:
            return error_dialog(self.tags_view, _('Add to user category'),
                    _('A user category %s does not exist')%dest_category, show=True)

        # Now add the item to the destination user category
        add_it = True
        if src_category == 'news':
            src_category = 'tags'
        for tup in user_cats[dest_category]:
            if src_name == tup[0] and src_category == tup[1]:
                add_it = False
        if add_it:
            user_cats[dest_category].append([src_name, src_category, 0])
        db.prefs.set('user_categories', user_cats)
        self.tags_view.recount()

    def do_tags_list_edit(self, tag, category):
        '''
        Open the 'manage_X' dialog where X == category. If tag is not None, the
        dialog will position the editor on that item.
        '''
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
            orig_name = d.original_names # dict of id: name

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
            m = self.tags_view.model()
            if rename_func:
                for item in to_delete:
                    delete_func(item)
                    m.delete_item_from_all_user_categories(orig_name[item], category)
                for old_id in to_rename:
                    rename_func(old_id, new_name=unicode(to_rename[old_id]))
                    m.rename_item_in_all_user_categories(orig_name[old_id],
                                            category, unicode(to_rename[old_id]))

            # Clean up the library view
            self.do_tag_item_renamed()
            self.tags_view.recount()

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

    def do_author_sort_edit(self, parent, id, select_sort=True):
        '''
        Open the manage authors dialog
        '''
        db = self.library_view.model().db
        editor = EditAuthorsDialog(parent, db, id, select_sort)
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

    def drag_drop_finished(self, ids):
        self.library_view.model().refresh_ids(ids)

# }}}

class TagBrowserWidget(QWidget): # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.parent = parent
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0,0,0,0)

        # Set up the find box & button
        search_layout = QHBoxLayout()
        self._layout.addLayout(search_layout)
        self.item_search = HistoryLineEdit(parent)
        try:
            self.item_search.lineEdit().setPlaceholderText(
                                                _('Find item in tag browser'))
        except:
            pass             # Using Qt < 4.7
        self.item_search.setToolTip(_(
        'Search for items. This is a "contains" search; items containing the\n'
        'text anywhere in the name will be found. You can limit the search\n'
        'to particular categories using syntax similar to search. For example,\n'
        'tags:foo will find foo in any tag, but not in authors etc. Entering\n'
        '*foo will filter all categories at once, showing only those items\n'
        'containing the text "foo"'))
        search_layout.addWidget(self.item_search)
        # Not sure if the shortcut should be translatable ...
        sc = QShortcut(QKeySequence(_('ALT+f')), parent)
        sc.connect(sc, SIGNAL('activated()'), self.set_focus_to_find_box)

        self.search_button = QToolButton()
        self.search_button.setText(_('F&ind'))
        self.search_button.setToolTip(_('Find the first/next matching item'))
        search_layout.addWidget(self.search_button)

        self.expand_button = QToolButton()
        self.expand_button.setText('-')
        self.expand_button.setToolTip(_('Collapse all categories'))
        search_layout.addWidget(self.expand_button)
        search_layout.setStretch(0, 10)
        search_layout.setStretch(1, 1)
        search_layout.setStretch(2, 1)

        self.current_find_position = None
        self.search_button.clicked.connect(self.find)
        self.item_search.initialize('tag_browser_search')
        self.item_search.lineEdit().returnPressed.connect(self.do_find)
        self.item_search.lineEdit().textEdited.connect(self.find_text_changed)
        self.item_search.activated[QString].connect(self.do_find)
        self.item_search.completer().setCaseSensitivity(Qt.CaseSensitive)

        parent.tags_view = TagsView(parent)
        self.tags_view = parent.tags_view
        self.expand_button.clicked.connect(self.tags_view.collapseAll)
        self._layout.addWidget(parent.tags_view)

        # Now the floating 'not found' box
        l = QLabel(self.tags_view)
        self.not_found_label = l
        l.setFrameStyle(QFrame.StyledPanel)
        l.setAutoFillBackground(True)
        l.setText('<p><b>'+_('No More Matches.</b><p> Click Find again to go to first match'))
        l.setAlignment(Qt.AlignVCenter)
        l.setWordWrap(True)
        l.resize(l.sizeHint())
        l.move(10,20)
        l.setVisible(False)
        self.not_found_label_timer = QTimer()
        self.not_found_label_timer.setSingleShot(True)
        self.not_found_label_timer.timeout.connect(self.not_found_label_timer_event,
                                                   type=Qt.QueuedConnection)

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

        # Must be in the same order as db2.MATCH_TYPE
        parent.tag_match = QComboBox(parent)
        for x in (_('Match any'), _('Match all')):
            parent.tag_match.addItem(x)
        parent.tag_match.setCurrentIndex(0)
        self._layout.addWidget(parent.tag_match)
        parent.tag_match.setToolTip(
                _('When selecting multiple entries in the Tag Browser '
                    'match any or all of them'))
        parent.tag_match.setStatusTip(parent.tag_match.toolTip())


        l = parent.manage_items_button = QPushButton(self)
        l.setStyleSheet('QPushButton {text-align: left; }')
        l.setText(_('Manage authors, tags, etc'))
        l.setToolTip(_('All of these category_managers are available by right-clicking '
                       'on items in the tag browser above'))
        l.m = QMenu()
        l.setMenu(l.m)
        self._layout.addWidget(l)

        # self.leak_test_timer = QTimer(self)
        # self.leak_test_timer.timeout.connect(self.test_for_leak)
        # self.leak_test_timer.start(5000)

    def set_pane_is_visible(self, to_what):
        self.tags_view.set_pane_is_visible(to_what)

    def find_text_changed(self, str):
        self.current_find_position = None

    def set_focus_to_find_box(self):
        self.item_search.setFocus()
        self.item_search.lineEdit().selectAll()

    def do_find(self, str=None):
        self.current_find_position = None
        self.find()

    def find(self):
        model = self.tags_view.model()
        model.clear_boxed()
        txt = unicode(self.item_search.currentText()).strip()

        if txt.startswith('*'):
            self.tags_view.set_new_model(filter_categories_by=txt[1:])
            self.current_find_position = None
            return
        if model.get_filter_categories_by():
            self.tags_view.set_new_model(filter_categories_by=None)
            self.current_find_position = None
            model = self.tags_view.model()

        if not txt:
            return

        self.item_search.lineEdit().blockSignals(True)
        self.search_button.setFocus(True)
        self.item_search.lineEdit().blockSignals(False)

        key = None
        colon = txt.rfind(':') if len(txt) > 2 else 0
        if colon > 0:
            key = self.parent.library_view.model().db.\
                        field_metadata.search_term_to_field_key(txt[:colon])
            txt = txt[colon+1:]

        self.current_find_position = \
            model.find_item_node(key, txt, self.current_find_position)
        if self.current_find_position:
            model.show_item_at_path(self.current_find_position, box=True)
        elif self.item_search.text():
            self.not_found_label.setVisible(True)
            if self.tags_view.verticalScrollBar().isVisible():
                sbw = self.tags_view.verticalScrollBar().width()
            else:
                sbw = 0
            width = self.width() - 8 - sbw
            height = self.not_found_label.heightForWidth(width) + 20
            self.not_found_label.resize(width, height)
            self.not_found_label.move(4, 10)
            self.not_found_label_timer.start(2000)

    def not_found_label_timer_event(self):
        self.not_found_label.setVisible(False)

    def test_for_leak(self):
        from calibre.utils.mem import memory
        import gc
        before = memory()
        self.tags_view.recount()
        for i in xrange(3): gc.collect()
        print 'Used memory:', memory(before)/(1024.), 'KB'

# }}}

