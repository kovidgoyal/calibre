#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import cPickle, os, re
from functools import partial
from itertools import izip

from PyQt5.Qt import (
    QStyledItemDelegate, Qt, QTreeView, pyqtSignal, QSize, QIcon, QApplication,
    QMenu, QPoint, QModelIndex, QToolTip, QCursor, QDrag, QRect,
    QLinearGradient, QPalette, QColor, QPen, QBrush, QFont
)

from calibre import sanitize_file_name_unicode
from calibre.constants import config_dir
from calibre.ebooks.metadata import rating_to_stars
from calibre.gui2.tag_browser.model import (TagTreeItem, TAG_SEARCH_STATES,
        TagsModel, DRAG_IMAGE_ROLE, COUNT_ROLE)
from calibre.gui2 import config, gprefs, choose_files, pixmap_to_data, rating_font, empty_index
from calibre.utils.icu import sort_key


class TagDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, *args, **kwargs):
        QStyledItemDelegate.__init__(self, *args, **kwargs)
        self.old_look = gprefs['tag_browser_old_look']
        self.rating_pat = re.compile(r'[%s]' % rating_to_stars(3, True))
        self.rating_font = QFont(rating_font())

    def draw_average_rating(self, item, style, painter, option, widget):
        rating = item.average_rating
        if rating is None:
            return
        r = style.subElementRect(style.SE_ItemViewItemDecoration, option, widget)
        icon = option.icon
        painter.save()
        nr = r.adjusted(0, 0, 0, 0)
        nr.setBottom(r.bottom()-int(r.height()*(rating/5.0)))
        painter.setClipRect(nr)
        bg = option.palette.window()
        if self.old_look:
            bg = option.palette.alternateBase() if option.features&option.Alternate else option.palette.base()
        painter.fillRect(r, bg)
        style.proxy().drawPrimitive(style.PE_PanelItemViewItem, option, painter, widget)
        painter.setOpacity(0.3)
        icon.paint(painter, r, option.decorationAlignment, icon.Normal, icon.On)
        painter.restore()

    def draw_icon(self, style, painter, option, widget):
        r = style.subElementRect(style.SE_ItemViewItemDecoration, option, widget)
        icon = option.icon
        icon.paint(painter, r, option.decorationAlignment, icon.Normal, icon.On)

    def draw_text(self, style, painter, option, widget, index, item):
        tr = style.subElementRect(style.SE_ItemViewItemText, option, widget)
        text = index.data(Qt.DisplayRole)
        hover = option.state & style.State_MouseOver
        if hover or gprefs['tag_browser_show_counts']:
            count = unicode(index.data(COUNT_ROLE))
            width = painter.fontMetrics().boundingRect(count).width()
            r = QRect(tr)
            r.setRight(r.right() - 1), r.setLeft(r.right() - width - 4)
            painter.drawText(r, Qt.AlignCenter | Qt.TextSingleLine, count)
            tr.setRight(r.left() - 1)
        else:
            tr.setRight(tr.right() - 1)
        is_rating = item.type == TagTreeItem.TAG and not self.rating_pat.sub('', text)
        if is_rating:
            painter.setFont(self.rating_font)
        flags = Qt.AlignVCenter | Qt.AlignLeft | Qt.TextSingleLine
        lr = QRect(tr)
        lr.setRight(lr.right() * 2)
        br = painter.boundingRect(lr, flags, text)
        if br.width() > tr.width():
            g = QLinearGradient(tr.topLeft(), tr.topRight())
            c = option.palette.color(QPalette.WindowText)
            g.setColorAt(0, c), g.setColorAt(0.8, c)
            c = QColor(c)
            c.setAlpha(0)
            g.setColorAt(1, c)
            pen = QPen()
            pen.setBrush(QBrush(g))
            painter.setPen(pen)
        painter.drawText(tr, flags, text)

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, empty_index)
        widget = self.parent()
        style = QApplication.style() if widget is None else widget.style()
        self.initStyleOption(option, index)
        item = index.data(Qt.UserRole)
        self.draw_icon(style, painter, option, widget)
        painter.save()
        self.draw_text(style, painter, option, widget, index, item)
        painter.restore()
        if item.boxed:
            r = style.subElementRect(style.SE_ItemViewItemFocusRect, option,
                    widget)
            painter.drawLine(r.bottomLeft(), r.bottomRight())
        if item.type == TagTreeItem.TAG and item.tag.state == 0 and config['show_avg_rating']:
            self.draw_average_rating(item, style, painter, option, widget)

    # }}}


class TagsView(QTreeView):  # {{{

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
    tag_item_delete         = pyqtSignal(object, object, object, object)

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent=None)
        self.setMouseTracking(True)
        self.alter_tb = None
        self.disable_recounting = False
        self.setUniformRowHeights(True)
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
        self.in_drag_drop = False
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
        stylish_tb = '''
                QTreeView {
                    background-color: palette(window);
                    color: palette(window-text);
                    border: none;
                }
        '''
        self.setStyleSheet('''
                QTreeView::item {
                    border: 1px solid transparent;
                    padding-top:0.8ex;
                    padding-bottom:0.8ex;
                }

                QTreeView::item:hover {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #e7effd, stop: 1 #cbdaf1);
                    border: 1px solid #bfcde4;
                    border-radius: 6px;
                }
        ''' + ('' if gprefs['tag_browser_old_look'] else stylish_tb))
        if gprefs['tag_browser_old_look']:
            self.setAlternatingRowColors(True)
        # Allowing keyboard focus looks bad in the Qt Fusion style and is useless
        # anyway since the enter/spacebar keys do nothing
        self.setFocusPolicy(Qt.NoFocus)

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
        self.pane_is_visible = True  # because TagsModel.set_database did a recount
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
        self.db.new_api.set_pref('user_categories', user_cats)
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

    def mouseMoveEvent(self, event):
        dex = self.indexAt(event.pos())
        if dex.isValid():
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()
        if not event.buttons() & Qt.LeftButton:
            return
        if self.in_drag_drop or not dex.isValid():
            QTreeView.mouseMoveEvent(self, event)
            return
        # Must deal with odd case where the node being dragged is 'virtual',
        # created to form a hierarchy. We can't really drag this node, but in
        # addition we can't allow drag recognition to notice going over some
        # other node and grabbing that one. So we set in_drag_drop to prevent
        # this from happening, turning it off when the user lifts the button.
        self.in_drag_drop = True
        if not self._model.flags(dex) & Qt.ItemIsDragEnabled:
            QTreeView.mouseMoveEvent(self, event)
            return
        md = self._model.mimeData([dex])
        pixmap = dex.data(DRAG_IMAGE_ROLE).pixmap(self.iconSize())
        drag = QDrag(self)
        drag.setPixmap(pixmap)
        drag.setMimeData(md)
        if self._model.is_in_user_category(dex):
            drag.exec_(Qt.CopyAction|Qt.MoveAction, Qt.CopyAction)
        else:
            drag.exec_(Qt.CopyAction)

    def mouseReleaseEvent(self, event):
        # Swallow everything except leftButton so context menus work correctly
        if event.button() == Qt.LeftButton or self.in_drag_drop:
            QTreeView.mouseReleaseEvent(self, event)
            self.in_drag_drop = False

    def mouseDoubleClickEvent(self, event):
        # swallow these to avoid toggling and editing at the same time
        pass

    @property
    def search_string(self):
        tokens = self._model.tokens()
        joiner = ' and ' if self.match_all else ' or '
        return joiner.join(tokens)

    def toggle_current_index(self):
        ci = self.currentIndex()
        if ci.isValid():
            self.toggle(ci)

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
                             key=None, index=None, search_state=None,
                             use_vl=None):
        if not action:
            return
        try:
            if action == 'set_icon':
                try:
                    path = choose_files(self, 'choose_category_icon',
                                _('Change icon for: %s')%key, filters=[
                                ('Images', ['png', 'gif', 'jpg', 'jpeg'])],
                            all_files=False, select_only_single_file=True)
                    if path:
                        path = path[0]
                        p = QIcon(path).pixmap(QSize(128, 128))
                        d = os.path.join(config_dir, 'tb_icons')
                        if not os.path.exists(d):
                            os.makedirs(d)
                        with open(os.path.join(d, 'icon_'+
                            sanitize_file_name_unicode(key)+'.png'), 'wb') as f:
                            f.write(pixmap_to_data(p, format='PNG'))
                            path = os.path.basename(f.name)
                        self._model.set_custom_category_icon(key, unicode(path))
                        self.recount()
                except:
                    import traceback
                    traceback.print_exc()
                return
            if action == 'clear_icon':
                self._model.set_custom_category_icon(key, None)
                self.recount()
                return

            if action == 'edit_item_no_vl':
                item = self.model().get_node(index)
                item.use_vl = False
                self.edit(index)
                return
            if action == 'edit_item_in_vl':
                item = self.model().get_node(index)
                item.use_vl = True
                self.edit(index)
                return
            if action == 'delete_item_in_vl':
                self.tag_item_delete.emit(key, index.id, index.original_name,
                                          self.model().get_book_ids_to_use())
                return
            if action == 'delete_item_no_vl':
                self.tag_item_delete.emit(key, index.id, index.original_name, None)
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
                self.model().db.saved_search_delete(key)
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
            self.db.new_api.set_pref('tag_browser_hidden_categories', list(self.hidden_categories))
            if reset_filter_categories:
                self._model.set_categories_filter(None)
            self._model.rebuild_node_tree()
        except:
            return

    def show_context_menu(self, point):
        def display_name(tag):
            if tag.category == 'search':
                n = tag.name
                if len(n) > 45:
                    n = n[:45] + '...'
                return "'" + n + "'"
            return tag.name

        index = self.indexAt(point)
        self.context_menu = QMenu(self)

        if index.isValid():
            item = index.data(Qt.UserRole)
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
                category = unicode(item.name or '')
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
                        if self.model().get_in_vl():
                            self.context_menu.addAction(self.rename_icon,
                                                    _('Rename %s in virtual library')%display_name(tag),
                                    partial(self.context_menu_handler, action='edit_item_in_vl',
                                            index=index))
                        self.context_menu.addAction(self.rename_icon,
                                                _('Rename %s')%display_name(tag),
                                partial(self.context_menu_handler, action='edit_item_no_vl',
                                        index=index))
                        if key in ('tags', 'series', 'publisher') or \
                                self._model.db.field_metadata.is_custom_field(key):
                            if self.model().get_in_vl():
                                self.context_menu.addAction(self.delete_icon,
                                                    _('Delete %s in virtual library')%display_name(tag),
                                partial(self.context_menu_handler, action='delete_item_in_vl',
                                    key=key, index=tag))

                            self.context_menu.addAction(self.delete_icon,
                                                    _('Delete %s')%display_name(tag),
                                partial(self.context_menu_handler, action='delete_item_no_vl',
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
                        nt = self.model().user_category_node_tree

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
                            partial(self.context_menu_handler, action='edit_item_no_vl',
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
                                    key=key, index=tag_item))
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
                            partial(self.context_menu_handler, action='edit_item_no_vl',
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
                            (self.db.field_metadata[key]['is_custom'] and
                             self.db.field_metadata[key]['datatype'] != 'composite'):
                    self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='open_editor',
                                    category=tag.original_name if tag else None,
                                    key=key))
                elif key == 'authors':
                    self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='edit_author_sort'))
                elif key == 'search':
                    self.context_menu.addAction(_('Manage Saved searches'),
                        partial(self.context_menu_handler, action='manage_searches',
                                category=tag.name if tag else None))

                self.context_menu.addSeparator()
                self.context_menu.addAction(_('Change category icon'),
                        partial(self.context_menu_handler, action='set_icon', key=key))
                self.context_menu.addAction(_('Restore default icon'),
                        partial(self.context_menu_handler, action='clear_icon', key=key))

                # Always show the user categories editor
                self.context_menu.addSeparator()
                if key.startswith('@') and \
                        key[1:] in self.db.prefs.get('user_categories', {}).keys():
                    self.context_menu.addAction(_('Manage User categories'),
                            partial(self.context_menu_handler, action='manage_categories',
                                    category=key[1:]))
                else:
                    self.context_menu.addAction(_('Manage User categories'),
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

        if index.isValid() and self.model().rowCount(index) > 0:
            self.context_menu.addSeparator()
            self.context_menu.addAction(_('E&xpand all children'), partial(self.expand_node_and_descendants, index))

        if not self.context_menu.isEmpty():
            self.context_menu.popup(self.mapToGlobal(point))
        return True

    def expand_node_and_descendants(self, index):
        if not index.isValid():
            return
        self.expand(index)
        for r in xrange(self.model().rowCount(index)):
            self.expand_node_and_descendants(index.child(r, 0))

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
        item = index.data(Qt.UserRole)
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
        item = idx.data(Qt.UserRole)
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
        self.blockSignals(True)
        for category in expanded_categories:
            idx = self._model.index_for_category(category)
            if idx is not None and idx.isValid():
                self.expand(idx)
        self.show_item_at_path(path)
        self.blockSignals(False)

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

    def expand_parent(self, idx):
        # Needed otherwise Qt sometimes segfaults if the node is buried in a
        # collapsed, off screen hierarchy. To be safe, we expand from the
        # outermost in
        p = self._model.parent(idx)
        if p.isValid():
            self.expand_parent(p)
        self.expand(idx)

    def show_item_at_index(self, idx, box=False,
                           position=QTreeView.PositionAtCenter):
        if idx.isValid() and idx.data(Qt.UserRole) is not self._model.root_item:
            self.expand_parent(idx)
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
