#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import cPickle
from functools import partial
from itertools import izip

from PyQt4.Qt import (QStyledItemDelegate, Qt, QTreeView, pyqtSignal, QSize,
        QIcon, QApplication, QMenu, QPoint, QModelIndex, QToolTip, QCursor)

from calibre.gui2.tag_browser.model import (TagTreeItem, TAG_SEARCH_STATES,
        TagsModel)
from calibre.gui2 import config, gprefs
from calibre.utils.search_query_parser import saved_searches
from calibre.utils.icu import sort_key

class TagDelegate(QStyledItemDelegate): # {{{

    def paint(self, painter, option, index):
        item = index.data(Qt.UserRole).toPyObject()
        QStyledItemDelegate.paint(self, painter, option, index)
        widget = self.parent()
        style = QApplication.style() if widget is None else widget.style()
        self.initStyleOption(option, index)
        if item.boxed:
            r = style.subElementRect(style.SE_ItemViewItemFocusRect, option,
                    widget)
            painter.save()
            painter.drawLine(r.bottomLeft(), r.bottomRight())
            painter.restore()
        if item.type != TagTreeItem.TAG:
            return
        if (item.tag.state == 0 and config['show_avg_rating'] and
                item.tag.avg_rating is not None):
            r = style.subElementRect(style.SE_ItemViewItemDecoration,
                    option, widget)
            icon = option.icon
            painter.save()
            rating = item.tag.avg_rating
            nr = r.adjusted(0, 0, 0, 0)
            nr.setBottom(r.bottom()-int(r.height()*(rating/5.0)))
            painter.setClipRect(nr)
            painter.fillRect(r, widget.palette().window())
            style.proxy().drawPrimitive(style.PE_PanelItemViewItem, option,
                    painter, widget)
            painter.setOpacity(0.3)
            icon.paint(painter, r, option.decorationAlignment, icon.Normal,
                    icon.On)
            painter.restore()


    # }}}

class TagsView(QTreeView): # {{{

    refresh_required        = pyqtSignal()
    tags_marked             = pyqtSignal(object)
    edit_user_category      = pyqtSignal(object)
    delete_user_category    = pyqtSignal(object)
    del_item_from_user_cat  = pyqtSignal(object, object, object)
    add_item_to_user_cat    = pyqtSignal(object, object, object)
    add_subcategory         = pyqtSignal(object)
    tags_list_edit          = pyqtSignal(object, object)
    saved_search_edit       = pyqtSignal(object)
    rebuild_saved_searches  = pyqtSignal()
    author_sort_edit        = pyqtSignal(object, object, object, object)
    tag_item_renamed        = pyqtSignal()
    search_item_renamed     = pyqtSignal()
    drag_drop_finished      = pyqtSignal(object)
    restriction_error       = pyqtSignal()
    tag_item_delete         = pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent=None)
        self.alter_tb = None
        self.disable_recounting = False
        self.setUniformRowHeights(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(20, 20))
        self.setTabKeyNavigation(True)
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
        self.search_icon = QIcon(I('search.png'))
        self.user_category_icon = QIcon(I('tb_folder.png'))
        self.delete_icon = QIcon(I('list_remove.png'))
        self.rename_icon = QIcon(I('edit-undo.png'))

        self._model = TagsModel(self)
        self._model.search_item_renamed.connect(self.search_item_renamed)
        self._model.refresh_required.connect(self.refresh_required,
                type=Qt.QueuedConnection)
        self._model.tag_item_renamed.connect(self.tag_item_renamed)
        self._model.restriction_error.connect(self.restriction_error)
        self._model.user_categories_edited.connect(self.user_categories_edited,
                type=Qt.QueuedConnection)
        self._model.drag_drop_finished.connect(self.drag_drop_finished)
        self.setStyleSheet('''
                QTreeView {
                    background-color: palette(window);
                    color: palette(window-text);
                    border: none;
                }

                QTreeView::item {
                    border: 1px solid transparent;
                    padding-top:0.9ex;
                    padding-bottom:0.9ex;
                }

                QTreeView::item:hover {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #e7effd, stop: 1 #cbdaf1);
                    border: 1px solid #bfcde4;
                    border-radius: 6px;
                }
        ''')

    @property
    def hidden_categories(self):
        return self._model.hidden_categories

    @property
    def db(self):
        return self._model.db

    @property
    def collapse_model(self):
        return self._model.collapse_model

    def set_pane_is_visible(self, to_what):
        pv = self.pane_is_visible
        self.pane_is_visible = to_what
        if to_what and not pv:
            self.recount()

    def get_state(self):
        state_map = {}
        expanded_categories = []
        for row, category in enumerate(self._model.category_nodes):
            if self.isExpanded(self._model.index(row, 0, QModelIndex())):
                expanded_categories.append(category.category_key)
            states = [c.tag.state for c in category.child_tags()]
            names = [(c.tag.name, c.tag.category) for c in category.child_tags()]
            state_map[category.category_key] = dict(izip(names, states))
        return expanded_categories, state_map

    def reread_collapse_parameters(self):
        self._model.reread_collapse_model(self.get_state()[1])

    def set_database(self, db, alter_tb):
        self._model.set_database(db)
        self.alter_tb = alter_tb
        self.pane_is_visible = True # because TagsModel.set_database did a recount
        self.setModel(self._model)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        pop = self.db.CATEGORY_SORTS.index(config['sort_tags_by'])
        self.alter_tb.sort_menu.actions()[pop].setChecked(True)
        try:
            match_pop = self.db.MATCH_TYPE.index(config['match_tags_type'])
        except ValueError:
            match_pop = 0
        self.alter_tb.match_menu.actions()[match_pop].setChecked(True)
        if not self.made_connections:
            self.clicked.connect(self.toggle)
            self.customContextMenuRequested.connect(self.show_context_menu)
            self.refresh_required.connect(self.recount, type=Qt.QueuedConnection)
            self.alter_tb.sort_menu.triggered.connect(self.sort_changed)
            self.alter_tb.match_menu.triggered.connect(self.match_changed)
            self.made_connections = True
        self.refresh_signal_processed = True
        db.add_listener(self.database_changed)
        self.expanded.connect(self.item_expanded)

    def database_changed(self, event, ids):
        if self.refresh_signal_processed:
            self.refresh_signal_processed = False
            self.refresh_required.emit()

    def user_categories_edited(self, user_cats, nkey):
        state_map = self.get_state()[1]
        self.db.prefs.set('user_categories', user_cats)
        self._model.rebuild_node_tree(state_map=state_map)
        p = self._model.find_category_node('@'+nkey)
        self.show_item_at_path(p)

    @property
    def match_all(self):
        return (self.alter_tb and
                self.alter_tb.match_menu.actions()[1].isChecked())

    def sort_changed(self, action):
        for i, ac in enumerate(self.alter_tb.sort_menu.actions()):
            if ac is action:
                config.set('sort_tags_by', self.db.CATEGORY_SORTS[i])
                self.recount()
                break

    def match_changed(self, action):
        try:
            for i, ac in enumerate(self.alter_tb.match_menu.actions()):
                if ac is action:
                    config.set('match_tags_type', self.db.MATCH_TYPE[i])
        except:
            pass

    def set_search_restriction(self, s):
        s = s if s else None
        self._model.set_search_restriction(s)

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
            if action == 'delete_item':
                self.tag_item_delete.emit(key, index.id, index.original_name)
                return
            if action == 'open_editor':
                self.tags_list_edit.emit(category, key)
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
                    for c in index.all_children():
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
                self.author_sort_edit.emit(self, index, True, False)
                return
            if action == 'edit_author_link':
                self.author_sort_edit.emit(self, index, False, True)
                return

            reset_filter_categories = True
            if action == 'hide':
                self.hidden_categories.add(category)
            elif action == 'show':
                self.hidden_categories.discard(category)
            elif action == 'categorization':
                changed = self.collapse_model != category
                self._model.collapse_model = category
                if changed:
                    reset_filter_categories = False
                    gprefs['tags_browser_partition_method'] = category
            elif action == 'defaults':
                self.hidden_categories.clear()
            self.db.prefs.set('tag_browser_hidden_categories', list(self.hidden_categories))
            if reset_filter_categories:
                self._model.set_categories_filter(None)
            self._model.rebuild_node_tree()
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
            item = index.data(Qt.UserRole).toPyObject()
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
                        if key in ('tags', 'series', 'publisher') or \
                                self._model.db.field_metadata.is_custom_field(key):
                            self.context_menu.addAction(self.delete_icon,
                                                    _('Delete %s')%display_name(tag),
                                partial(self.context_menu_handler, action='delete_item',
                                    key=key, index=tag))
                        if key == 'authors':
                            self.context_menu.addAction(_('Edit sort for %s')%display_name(tag),
                                    partial(self.context_menu_handler,
                                            action='edit_author_sort', index=tag.id))
                            self.context_menu.addAction(_('Edit link for %s')%display_name(tag),
                                    partial(self.context_menu_handler,
                                            action='edit_author_link', index=tag.id))

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
                    elif key == 'search' and tag.is_searchable:
                        self.context_menu.addAction(self.rename_icon,
                                                    _('Rename %s')%display_name(tag),
                            partial(self.context_menu_handler, action='edit_item',
                                    index=index))
                        self.context_menu.addAction(self.delete_icon,
                                _('Delete search %s')%display_name(tag),
                                partial(self.context_menu_handler,
                                        action='delete_search', key=tag.original_name))
                    if key.startswith('@') and not item.is_gst:
                        self.context_menu.addAction(self.user_category_icon,
                                _('Remove %(item)s from category %(cat)s')%
                                            dict(item=display_name(tag), cat=item.py_name),
                                partial(self.context_menu_handler,
                                        action='delete_item_from_user_category',
                                        key = key, index = tag_item))
                    if tag.is_searchable:
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
        da = m.addAction(_('Disable'),
            partial(self.context_menu_handler, action='categorization', category='disable'))
        fla = m.addAction(_('By first letter'),
            partial(self.context_menu_handler, action='categorization', category='first letter'))
        pa = m.addAction(_('Partition'),
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

        if config['sort_tags_by'] != "name":
            fla.setEnabled(False)
            m.hovered.connect(self.collapse_menu_hovered)
            fla.setToolTip(_('First letter is usable only when sorting by name'))
            # Apparently one cannot set a tooltip to empty, so use a star and
            # deal with it in the hover method
            da.setToolTip('*')
            pa.setToolTip('*')

        if not self.context_menu.isEmpty():
            self.context_menu.popup(self.mapToGlobal(point))
        return True

    def collapse_menu_hovered(self, action):
        tip = action.toolTip()
        if tip == '*':
            tip = ''
        QToolTip.showText(QCursor.pos(), tip)

    def dragMoveEvent(self, event):
        QTreeView.dragMoveEvent(self, event)
        self.setDropIndicatorShown(False)
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        src_is_tb = event.mimeData().hasFormat('application/calibre+from_tag_browser')
        item = index.data(Qt.UserRole).toPyObject()
        if item.type == TagTreeItem.ROOT:
            return
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
        item = idx.data(Qt.UserRole).toPyObject()
        if getattr(item, 'type', None) == TagTreeItem.TAG:
            idx = idx.parent()
        return self.isExpanded(idx)

    def recount(self, *args):
        '''
        Rebuild the category tree, expand any categories that were expanded,
        reset the search states, and reselect the current node.
        '''
        if self.disable_recounting or not self.pane_is_visible:
            return
        self.refresh_signal_processed = True
        ci = self.currentIndex()
        if not ci.isValid():
            ci = self.indexAt(QPoint(10, 10))
        path = self.model().path_for_index(ci) if self.is_visible(ci) else None
        expanded_categories, state_map = self.get_state()
        self._model.rebuild_node_tree(state_map=state_map)
        for category in expanded_categories:
            idx = self._model.index_for_category(category)
            if idx is not None and idx.isValid():
                self.expand(idx)
        self.show_item_at_path(path)

    def show_item_at_path(self, path, box=False,
                          position=QTreeView.PositionAtCenter):
        '''
        Scroll the browser and open categories to show the item referenced by
        path. If possible, the item is placed in the center. If box=True, a
        box is drawn around the item.
        '''
        if path:
            self.show_item_at_index(self._model.index_for_path(path), box=box,
                                    position=position)

    def show_item_at_index(self, idx, box=False,
                           position=QTreeView.PositionAtCenter):
        if idx.isValid() and idx.data(Qt.UserRole).toPyObject() is not self._model.root_item:
            self.expand(self._model.parent(idx)) # Needed otherwise Qt sometimes segfaults if the
                                                 # node is buried in a collapsed, off
                                                 # screen hierarchy
            self.setCurrentIndex(idx)
            self.scrollTo(idx, position)
            if box:
                self._model.set_boxed(idx)

    def item_expanded(self, idx):
        '''
        Called by the expanded signal
        '''
        self.setCurrentIndex(idx)

    # }}}


