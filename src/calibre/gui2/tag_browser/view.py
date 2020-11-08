#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re, traceback
from functools import partial

from PyQt5.Qt import (
    QStyledItemDelegate, Qt, QTreeView, pyqtSignal, QSize, QIcon, QApplication,
    QMenu, QPoint, QToolTip, QCursor, QDrag, QRect, QModelIndex,
    QLinearGradient, QPalette, QColor, QPen, QBrush, QFont, QTimer
)

from calibre import sanitize_file_name
from calibre.constants import config_dir
from calibre.ebooks.metadata import rating_to_stars
from calibre.gui2.complete2 import EditWithComplete
from calibre.gui2.tag_browser.model import (TagTreeItem, TAG_SEARCH_STATES,
        TagsModel, DRAG_IMAGE_ROLE, COUNT_ROLE)
from calibre.gui2.widgets import EnLineEdit
from calibre.gui2 import (config, gprefs, choose_files, pixmap_to_data,
                          rating_font, empty_index, question_dialog)
from calibre.utils.icu import sort_key
from calibre.utils.serialize import json_loads
from polyglot.builtins import unicode_type, range, zip


class TagDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, tags_view):
        QStyledItemDelegate.__init__(self, tags_view)
        self.old_look = False
        self.rating_pat = re.compile(r'[%s]' % rating_to_stars(3, True))
        self.rating_font = QFont(rating_font())
        self.completion_data = None
        self.tags_view = tags_view

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

    def paint_text(self, painter, rect, flags, text, hover):
        set_color = hover and QApplication.instance().is_dark_theme
        if set_color:
            painter.save()
            pen = painter.pen()
            pen.setColor(QColor(Qt.black))
            painter.setPen(pen)
        painter.drawText(rect, flags, text)
        if set_color:
            painter.restore()

    def draw_text(self, style, painter, option, widget, index, item):
        tr = style.subElementRect(style.SE_ItemViewItemText, option, widget)
        text = index.data(Qt.DisplayRole)
        hover = option.state & style.State_MouseOver
        is_search = (True if item.type == TagTreeItem.TAG and
                            item.tag.category == 'search' else False)
        if not is_search and (hover or gprefs['tag_browser_show_counts']):
            count = unicode_type(index.data(COUNT_ROLE))
            width = painter.fontMetrics().boundingRect(count).width()
            r = QRect(tr)
            r.setRight(r.right() - 1), r.setLeft(r.right() - width - 4)
            self.paint_text(painter, r, Qt.AlignCenter | Qt.TextSingleLine, count, hover)
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
        self.paint_text(painter, tr, flags, text, hover)

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

    def set_completion_data(self, data):
        self.completion_data = data

    def createEditor(self, parent, option, index):
        item = self.tags_view.model().get_node(index)
        item.use_vl = False
        if self.tags_view.model().get_in_vl():
            if question_dialog(self.tags_view, _('Rename in Virtual library'), '<p>' +
                               _('Do you want this rename to apply only to books '
                                 'in the current Virtual library?') + '</p>',
                               yes_text=_('Yes, apply only in VL'),
                               no_text=_('No, apply in entire library')):
                item.use_vl = True
        if self.completion_data:
            editor = EditWithComplete(parent)
            editor.set_separator(None)
            editor.update_items_cache(self.completion_data)
        else:
            editor = EnLineEdit(parent)
        return editor

    # }}}


class TagsView(QTreeView):  # {{{

    refresh_required        = pyqtSignal()
    tags_marked             = pyqtSignal(object)
    edit_user_category      = pyqtSignal(object)
    delete_user_category    = pyqtSignal(object)
    del_item_from_user_cat  = pyqtSignal(object, object, object)
    add_item_to_user_cat    = pyqtSignal(object, object, object)
    add_subcategory         = pyqtSignal(object)
    tags_list_edit          = pyqtSignal(object, object, object)
    saved_search_edit       = pyqtSignal(object)
    rebuild_saved_searches  = pyqtSignal()
    author_sort_edit        = pyqtSignal(object, object, object, object, object)
    tag_item_renamed        = pyqtSignal()
    search_item_renamed     = pyqtSignal()
    drag_drop_finished      = pyqtSignal(object)
    restriction_error       = pyqtSignal()
    tag_item_delete         = pyqtSignal(object, object, object, object, object)
    apply_tag_to_selected   = pyqtSignal(object, object, object)
    edit_enum_values        = pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent=None)
        self.setProperty('frame_for_focus', True)
        self.setMouseTracking(True)
        self.alter_tb = None
        self.disable_recounting = False
        self.setUniformRowHeights(True)
        self.setIconSize(QSize(20, 20))
        self.setTabKeyNavigation(True)
        self.setAnimated(True)
        self.setHeaderHidden(True)
        self.setItemDelegate(TagDelegate(tags_view=self))
        self.made_connections = False
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(self.DragDrop)
        self.setDropIndicatorShown(True)
        self.setAutoExpandDelay(500)
        self.pane_is_visible = False
        self.search_icon = QIcon(I('search.png'))
        self.search_copy_icon = QIcon(I("search_copy_saved.png"))
        self.user_category_icon = QIcon(I('tb_folder.png'))
        self.edit_metadata_icon = QIcon(I('edit_input.png'))
        self.delete_icon = QIcon(I('list_remove.png'))
        self.rename_icon = QIcon(I('edit-undo.png'))
        self.plus_icon = QIcon(I('plus.png'))
        self.minus_icon = QIcon(I('minus.png'))

        self._model = TagsModel(self)
        self._model.search_item_renamed.connect(self.search_item_renamed)
        self._model.refresh_required.connect(self.refresh_required,
                type=Qt.QueuedConnection)
        self._model.tag_item_renamed.connect(self.tag_item_renamed)
        self._model.restriction_error.connect(self.restriction_error)
        self._model.user_categories_edited.connect(self.user_categories_edited,
                type=Qt.QueuedConnection)
        self._model.drag_drop_finished.connect(self.drag_drop_finished)
        self.set_look_and_feel(first=True)
        QApplication.instance().palette_changed.connect(self.set_style_sheet, type=Qt.QueuedConnection)

    def set_style_sheet(self):
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
                    padding-top:PADex;
                    padding-bottom:PADex;
                }

                QTreeView::item:hover {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #e7effd, stop: 1 #cbdaf1);
                    border: 1px solid #bfcde4;
                    border-radius: 6px;
                }
        '''.replace('PAD', unicode_type(gprefs['tag_browser_item_padding'])) + (
            '' if gprefs['tag_browser_old_look'] else stylish_tb))

    def set_look_and_feel(self, first=False):
        self.set_style_sheet()
        self.setAlternatingRowColors(gprefs['tag_browser_old_look'])
        self.itemDelegate().old_look = gprefs['tag_browser_old_look']

        if gprefs['tag_browser_allow_keyboard_focus']:
            self.setFocusPolicy(Qt.StrongFocus)
        else:
            self.setFocusPolicy(Qt.NoFocus)
        # Ensure the TB doesn't keep the focus it might already have. When this
        # method is first called during GUI initialization not everything is
        # set up, in which case don't try to change the focus.
        # Note: this process has the side effect of moving the focus to the
        # library view whenever a look & feel preference is changed.
        if not first:
            try:
                from calibre.gui2.ui import get_gui
                get_gui().shift_esc()
            except:
                traceback.print_exc()

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
        hide_empty_categories = self.model().prefs['tag_browser_hide_empty_categories']
        crmap = self._model.category_row_map()
        for category in self._model.category_nodes:
            if (category.category_key in self.hidden_categories or (
                hide_empty_categories and len(category.child_tags()) == 0)):
                continue
            row = crmap.get(category.category_key)
            if row is not None:
                index = self._model.index(row, 0, QModelIndex())
                if self.isExpanded(index):
                    expanded_categories.append(category.category_key)
            states = [c.tag.state for c in category.child_tags()]
            names = [(c.tag.name, c.tag.category) for c in category.child_tags()]
            state_map[category.category_key] = dict(zip(names, states))
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
        self.collapsed.connect(self.collapse_node_and_children)

    def keyPressEvent(self, event):
        if (gprefs['tag_browser_allow_keyboard_focus'] and event.key() == Qt.Key_Return and self.state() != self.EditingState and
                # I don't see how current_index can ever be not valid, but ...
                self.currentIndex().isValid()):
            self.toggle_current_index()
            return
        QTreeView.keyPressEvent(self, event)

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
        return (self.alter_tb and self.alter_tb.match_menu.actions()[1].isChecked())

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

    def mousePressEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.possible_drag_start = event.pos()
        return QTreeView.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        dex = self.indexAt(event.pos())
        if dex.isValid():
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()
        if not event.buttons() & Qt.LeftButton:
            return
        if not dex.isValid():
            QTreeView.mouseMoveEvent(self, event)
            return
        # don't start drag/drop until the mouse has moved a bit.
        if ((event.pos() - self.possible_drag_start).manhattanLength() <
                                    QApplication.startDragDistance()):
            QTreeView.mouseMoveEvent(self, event)
            return

        if not self._model.flags(dex) & Qt.ItemIsDragEnabled:
            QTreeView.mouseMoveEvent(self, event)
            return
        md = self._model.mimeData([dex])
        pixmap = dex.data(DRAG_IMAGE_ROLE).pixmap(self.iconSize())
        drag = QDrag(self)
        drag.setPixmap(pixmap)
        drag.setMimeData(md)
        if (self._model.is_in_user_category(dex) or
                    self._model.is_index_on_a_hierarchical_category(dex)):
            '''
            Things break if we specify MoveAction as the default, which is
            what we want for drag on hierarchical categories. Dragging user
            categories stops working. Don't know why. To avoid the problem
            we fix the action in dragMoveEvent.
            '''
            drag.exec_(Qt.CopyAction|Qt.MoveAction, Qt.CopyAction)
        else:
            drag.exec_(Qt.CopyAction)

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
            # Reset the focus back to TB if it has it before the toggle
            # Must ask this question before starting the search because
            # it changes the focus
            has_focus = self.hasFocus()
            self.tags_marked.emit(self.search_string)
            if has_focus and gprefs['tag_browser_allow_keyboard_focus']:
                # Reset the focus to the TB. Use the singleshot in case
                # some of searching is done using queued signals.
                QTimer.singleShot(0, lambda: self.setFocus())

    def conditional_clear(self, search_string):
        if search_string != self.search_string:
            self.clear()

    def context_menu_handler(self, action=None, category=None,
                             key=None, index=None, search_state=None,
                             use_vl=None, is_first_letter=False):
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
                        with open(os.path.join(d, 'icon_' + sanitize_file_name(key)+'.png'), 'wb') as f:
                            f.write(pixmap_to_data(p, format='PNG'))
                            path = os.path.basename(f.name)
                        self._model.set_custom_category_icon(key, unicode_type(path))
                        self.recount()
                except:
                    traceback.print_exc()
                return
            if action == 'clear_icon':
                self._model.set_custom_category_icon(key, None)
                self.recount()
                return

            def set_completion_data(category):
                try:
                    completion_data = self.db.new_api.all_field_names(category)
                except:
                    completion_data = None
                self.itemDelegate().set_completion_data(completion_data)

            if action == 'edit_item_no_vl':
                item = self.model().get_node(index)
                item.use_vl = False
                set_completion_data(category)
                self.edit(index)
                return
            if action == 'edit_item_in_vl':
                item = self.model().get_node(index)
                item.use_vl = True
                set_completion_data(category)
                self.edit(index)
                return
            if action == 'delete_item_in_vl':
                tag = index.tag
                id_ = tag.id if tag.is_editable else None
                children = index.child_tags()
                self.tag_item_delete.emit(key, id_, tag.original_name,
                                          self.model().get_book_ids_to_use(),
                                          children)
                return
            if action == 'delete_item_no_vl':
                tag = index.tag
                id_ = tag.id if tag.is_editable else None
                children = index.child_tags()
                self.tag_item_delete.emit(key, id_, tag.original_name,
                                          None, children)
                return
            if action == 'open_editor':
                self.tags_list_edit.emit(category, key, is_first_letter)
                return
            if action == 'manage_categories':
                self.edit_user_category.emit(category)
                return
            if action == 'search':
                self._toggle(index, set_to=search_state)
                return
            if action == "raw_search":
                from calibre.gui2.ui import get_gui
                get_gui().get_saved_search_text(search_name='search:' + key)
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
            if action == 'edit_authors':
                self.author_sort_edit.emit(self, index, False, False, is_first_letter)
                return
            if action == 'edit_author_sort':
                self.author_sort_edit.emit(self, index, True, False, is_first_letter)
                return
            if action == 'edit_author_link':
                self.author_sort_edit.emit(self, index, False, True, False)
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
            elif action == 'add_tag':
                item = self.model().get_node(index)
                if item is not None:
                    self.apply_to_selected_books(item)
                return
            elif action == 'remove_tag':
                item = self.model().get_node(index)
                if item is not None:
                    self.apply_to_selected_books(item, True)
                return
            elif action == 'edit_enum':
                self.edit_enum_values.emit(self, self.db, key)
                return
            self.db.new_api.set_pref('tag_browser_hidden_categories', list(self.hidden_categories))
            if reset_filter_categories:
                self._model.set_categories_filter(None)
            self._model.rebuild_node_tree()
        except Exception:
            traceback.print_exc()
            return

    def apply_to_selected_books(self, item, remove=False):
        if item.type != item.TAG:
            return
        tag = item.tag
        if not tag.category or not tag.original_name:
            return
        self.apply_tag_to_selected.emit(tag.category, tag.original_name, remove)

    def show_context_menu(self, point):
        def display_name(tag):
            ans = tag.name
            if tag.category == 'search':
                n = tag.name
                if len(n) > 45:
                    n = n[:45] + '...'
                ans = n
            elif tag.is_hierarchical and not tag.is_editable:
                ans = tag.original_name
            if ans:
                ans = ans.replace('&', '&&')
            return ans

        index = self.indexAt(point)
        self.context_menu = QMenu(self)
        added_show_hidden_categories = False

        def add_show_hidden_categories():
            nonlocal added_show_hidden_categories
            if self.hidden_categories and not added_show_hidden_categories:
                added_show_hidden_categories = True
                m = self.context_menu.addMenu(_('Show category'))
                for col in sorted(self.hidden_categories,
                        key=lambda x: sort_key(self.db.field_metadata[x]['name'])):
                    m.addAction(self.db.field_metadata[col]['name'],
                        partial(self.context_menu_handler, action='show', category=col))
                m.addSeparator()
                m.addAction(_('All categories'),
                        partial(self.context_menu_handler, action='defaults'))

        search_submenu = None
        if index.isValid():
            item = index.data(Qt.UserRole)
            tag = None
            tag_item = item

            if item.type == TagTreeItem.TAG:
                tag = item.tag
                while item.type != TagTreeItem.CATEGORY:
                    item = item.parent

            if item.type == TagTreeItem.CATEGORY:
                if not item.category_key.startswith('@'):
                    while item.parent != self._model.root_item:
                        item = item.parent
                category = unicode_type(item.name or '')
                key = item.category_key
                # Verify that we are working with a field that we know something about
                if key not in self.db.field_metadata:
                    return True
                fm = self.db.field_metadata[key]

                # Did the user click on a leaf node?
                if tag:
                    # If the user right-clicked on an editable item, then offer
                    # the possibility of renaming that item.
                    if tag.is_editable or tag.is_hierarchical:
                        # Add the 'rename' items to both interior and leaf nodes
                        if fm['datatype'] != 'enumeration':
                            if self.model().get_in_vl():
                                self.context_menu.addAction(self.rename_icon,
                                        _('Rename %s in Virtual library')%display_name(tag),
                                        partial(self.context_menu_handler, action='edit_item_in_vl',
                                                index=index, category=key))
                            self.context_menu.addAction(self.rename_icon,
                                        _('Rename %s')%display_name(tag),
                                        partial(self.context_menu_handler, action='edit_item_no_vl',
                                                index=index, category=key))
                        if key in ('tags', 'series', 'publisher') or \
                                self._model.db.field_metadata.is_custom_field(key):
                            if self.model().get_in_vl():
                                self.context_menu.addAction(self.delete_icon,
                                                    _('Delete %s in Virtual library')%display_name(tag),
                                partial(self.context_menu_handler, action='delete_item_in_vl',
                                    key=key, index=tag_item))

                            self.context_menu.addAction(self.delete_icon,
                                                    _('Delete %s')%display_name(tag),
                                partial(self.context_menu_handler, action='delete_item_no_vl',
                                    key=key, index=tag_item))
                    if tag.is_editable:
                        if key == 'authors':
                            self.context_menu.addAction(_('Edit sort for %s')%display_name(tag),
                                    partial(self.context_menu_handler,
                                            action='edit_author_sort', index=tag.id))
                            self.context_menu.addAction(_('Edit link for %s')%display_name(tag),
                                    partial(self.context_menu_handler,
                                            action='edit_author_link', index=tag.id))

                        # is_editable is also overloaded to mean 'can be added
                        # to a User category'
                        m = QMenu(_('Add %s to User category')%display_name(tag), self.context_menu)
                        m.setIcon(self.user_category_icon)
                        added = [False]

                        def add_node_tree(tree_dict, m, path):
                            p = path[:]
                            for k in sorted(tree_dict.keys(), key=sort_key):
                                p.append(k)
                                n = k[1:] if k.startswith('@') else k
                                m.addAction(self.user_category_icon, n,
                                    partial(self.context_menu_handler,
                                            'add_to_category',
                                            category='.'.join(p), index=tag_item))
                                added[0] = True
                                if len(tree_dict[k]):
                                    tm = m.addMenu(self.user_category_icon,
                                                   _('Children of %s')%n)
                                    add_node_tree(tree_dict[k], tm, p)
                                p.pop()
                        add_node_tree(self.model().user_category_node_tree, m, [])
                        if added[0]:
                            self.context_menu.addMenu(m)

                        # is_editable also means the tag can be applied/removed
                        # from selected books
                        if fm['datatype'] != 'rating':
                            m = self.context_menu.addMenu(self.edit_metadata_icon,
                                            _('Add/remove %s to selected books')%display_name(tag))
                            m.addAction(self.plus_icon,
                                _('Add %s to selected books') % display_name(tag),
                                partial(self.context_menu_handler, action='add_tag', index=index))
                            m.addAction(self.minus_icon,
                                _('Remove %s from selected books') % display_name(tag),
                                partial(self.context_menu_handler, action='remove_tag', index=index))

                    elif key == 'search' and tag.is_searchable:
                        self.context_menu.addAction(self.rename_icon,
                                                    _('Rename %s')%display_name(tag),
                            partial(self.context_menu_handler, action='edit_item_no_vl',
                                    index=index))
                        self.context_menu.addAction(self.delete_icon,
                                _('Delete Saved search %s')%display_name(tag),
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
                        self.context_menu.addSeparator()
                        search_submenu = self.context_menu.addMenu(_('Search'))
                        search_submenu.addAction(self.search_icon,
                                _('Search for %s')%display_name(tag),
                                partial(self.context_menu_handler, action='search',
                                        search_state=TAG_SEARCH_STATES['mark_plus'],
                                        index=index))
                        search_submenu.addAction(self.search_icon,
                                _('Search for everything but %s')%display_name(tag),
                                partial(self.context_menu_handler, action='search',
                                        search_state=TAG_SEARCH_STATES['mark_minus'],
                                        index=index))
                        if key == 'search':
                            search_submenu.addAction(self.search_copy_icon,
                                     _('Search using saved search expression'),
                                     partial(self.context_menu_handler, action='raw_search',
                                             key=tag.name))
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
                            _('Delete User category %s')%item.py_name,
                            partial(self.context_menu_handler,
                                    action='delete_user_category', key=key))
                    self.context_menu.addSeparator()
                # search by category. Some categories are not searchable, such
                # as search and news
                if item.tag.is_searchable:
                    if search_submenu is None:
                        search_submenu = self.context_menu.addMenu(_('Search'))
                        self.context_menu.addSeparator()
                    search_submenu.addAction(self.search_icon,
                            _('Search for books in category %s')%category,
                            partial(self.context_menu_handler,
                                    action='search_category',
                                    index=self._model.createIndex(item.row(), 0, item),
                                    search_state=TAG_SEARCH_STATES['mark_plus']))
                    search_submenu.addAction(self.search_icon,
                            _('Search for books not in category %s')%category,
                            partial(self.context_menu_handler,
                                    action='search_category',
                                    index=self._model.createIndex(item.row(), 0, item),
                                    search_state=TAG_SEARCH_STATES['mark_minus']))

                # Offer specific editors for tags/series/publishers/saved searches
                self.context_menu.addSeparator()
                if key in ['tags', 'publisher', 'series'] or (
                        fm['is_custom'] and fm['datatype'] != 'composite'):
                    if tag_item.type == TagTreeItem.CATEGORY and tag_item.temporary:
                        self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='open_editor',
                                    category=tag_item.name,
                                    key=key, is_first_letter=True))
                    else:
                        self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='open_editor',
                                    category=tag.original_name if tag else None,
                                    key=key))
                    if fm['datatype'] == 'enumeration':
                        self.context_menu.addAction(_('Edit permissible values for %s')%category,
                            partial(self.context_menu_handler, action='edit_enum',
                                    key=key))
                elif key == 'authors':
                    if tag_item.type == TagTreeItem.CATEGORY:
                        if tag_item.temporary:
                            self.context_menu.addAction(_('Manage %s')%category,
                                partial(self.context_menu_handler, action='edit_authors',
                                        index=tag_item.name, is_first_letter=True))
                        else:
                            self.context_menu.addAction(_('Manage %s')%category,
                                partial(self.context_menu_handler, action='edit_authors'))
                    else:
                        self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='edit_authors',
                                    index=tag.id))
                elif key == 'search':
                    self.context_menu.addAction(_('Manage Saved searches'),
                        partial(self.context_menu_handler, action='manage_searches',
                                category=tag.name if tag else None))

                # Hide/Show/Restore categories
                self.context_menu.addSeparator()
                self.context_menu.addAction(_('Hide category %s') % category,
                    partial(self.context_menu_handler, action='hide',
                            category=key))
                add_show_hidden_categories()

                if tag is None:
                    self.context_menu.addSeparator()
                    self.context_menu.addAction(_('Change category icon'),
                            partial(self.context_menu_handler, action='set_icon', key=key))
                    self.context_menu.addAction(_('Restore default icon'),
                            partial(self.context_menu_handler, action='clear_icon', key=key))

                # Always show the User categories editor
                self.context_menu.addSeparator()
                if key.startswith('@') and \
                        key[1:] in self.db.new_api.pref('user_categories', {}).keys():
                    self.context_menu.addAction(self.user_category_icon,
                            _('Manage User categories'),
                            partial(self.context_menu_handler, action='manage_categories',
                                    category=key[1:]))
                else:
                    self.context_menu.addAction(self.user_category_icon,
                            _('Manage User categories'),
                            partial(self.context_menu_handler, action='manage_categories',
                                    category=None))
        if self.hidden_categories:
            if not self.context_menu.isEmpty():
                self.context_menu.addSeparator()
            add_show_hidden_categories()

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

        # Add expand menu items
        self.context_menu.addSeparator()
        m = self.context_menu.addMenu(_('Expand or collapse'))
        try:
            node_name = self._model.get_node(index).tag.name
        except AttributeError:
            pass
        else:
            if self.has_children(index) and not self.isExpanded(index):
                m.addAction(self.plus_icon,
                            _('Expand {0}').format(node_name), partial(self.expand, index))
            if self.has_unexpanded_children(index):
                m.addAction(self.plus_icon,
                            _('Expand {0} and its children').format(node_name),
                                            partial(self.expand_node_and_children, index))

        # Add menu items to collapse parent nodes
        idx = index
        paths = []
        while True:
            # First walk up the node tree getting the displayed names of
            # expanded parent nodes
            node = self._model.get_node(idx)
            if node.type == TagTreeItem.ROOT:
                break
            if self.has_children(idx) and self.isExpanded(idx):
                # leaf nodes don't have children so can't be expanded.
                # Also the leaf node might be collapsed
                paths.append((node.tag.name, idx))
            idx = self._model.parent(idx)
        for p in paths:
            # Now add the menu items
            m.addAction(self.minus_icon,
                        _("Collapse {0}").format(p[0]), partial(self.collapse_node, p[1]))
        m.addAction(self.minus_icon, _('Collapse all'), self.collapseAll)

        if not self.context_menu.isEmpty():
            self.context_menu.popup(self.mapToGlobal(point))
        return True

    def has_children(self, idx):
        return self.model().rowCount(idx) > 0

    def collapse_node_and_children(self, idx):
        self.collapse(idx)
        for r in range(self.model().rowCount(idx)):
            self.collapse_node_and_children(idx.child(r, 0))

    def collapse_node(self, idx):
        if not idx.isValid():
            return
        self.collapse_node_and_children(idx)
        self.setCurrentIndex(idx)
        self.scrollTo(idx)

    def expand_node_and_children(self, index):
        if not index.isValid():
            return
        self.expand(index)
        for r in range(self.model().rowCount(index)):
            self.expand_node_and_children(index.child(r, 0))

    def has_unexpanded_children(self, index):
        if not index.isValid():
            return False
        for r in range(self._model.rowCount(index)):
            dex = index.child(r, 0)
            if self._model.rowCount(dex) > 0:
                if not self.isExpanded(dex):
                    return True
                return self.has_unexpanded_children(dex)
        return False

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

        if src_is_tb:
            src_json = json_loads(bytes(event.mimeData().data('application/calibre+from_tag_browser')))
            if len(src_json) > 1:
                # Should never have multiple mimedata from the tag browser
                return
        if src_is_tb:
            src_md = src_json[0]
            src_item = self._model.get_node(self._model.index_for_path(src_md[5]))
            # Check if this is an intra-hierarchical-category drag/drop
            if (src_item.type == TagTreeItem.TAG and
                    src_item.tag.category == item.tag.category and
                    not item.temporary and
                    self._model.is_key_a_hierarchical_category(src_item.tag.category)):
                event.setDropAction(Qt.MoveAction)
                self.setDropIndicatorShown(True)
                return
        # We aren't dropping an item on its own category. Check if the dest is
        # not a user category and can be dropped on. This covers drops from the
        # booklist. It is OK to drop onto virtual nodes
        if item.type == TagTreeItem.TAG and self._model.flags(index) & Qt.ItemIsDropEnabled:
            event.setDropAction(Qt.CopyAction)
            self.setDropIndicatorShown(not src_is_tb)
            return
        # Now see if we are on a user category and the source can be dropped there
        if item.type == TagTreeItem.CATEGORY and not item.is_gst:
            fm_dest = self.db.metadata_for_field(item.category_key)
            if fm_dest['kind'] == 'user':
                if src_is_tb:
                    # src_md and src_item are initialized above
                    if event.dropAction() == Qt.MoveAction:
                        # can move only from user categories
                        if (src_md[0] == TagTreeItem.TAG and
                                 (not src_md[1].startswith('@') or src_md[2])):
                            return
                    # can't copy virtual nodes into a user category
                    if src_item.tag.is_editable:
                        self.setDropIndicatorShown(True)
                    return
                md = event.mimeData()
                # Check for drag to user category from the book list. Can handle
                # only non-multiple columns, except for some unknown reason authors
                if hasattr(md, 'column_name'):
                    fm_src = self.db.metadata_for_field(md.column_name)
                    if md.column_name in ['authors', 'publisher', 'series'] or \
                            (fm_src['is_custom'] and
                             ((fm_src['datatype'] in ['series', 'text', 'enumeration'] and
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

    def recount_with_position_based_index(self):
        self._model.use_position_based_index_on_next_recount = True
        self.recount()

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
        use_pos = self._model.use_position_based_index_on_next_recount
        self._model.use_position_based_index_on_next_recount = False
        if use_pos:
            path = self._model.path_for_index(ci) if self.is_visible(ci) else None
        else:
            path = self._model.named_path_for_index(ci) if self.is_visible(ci) else None
        expanded_categories, state_map = self.get_state()
        self._model.rebuild_node_tree(state_map=state_map)
        self.blockSignals(True)
        for category in expanded_categories:
            idx = self._model.index_for_category(category)
            if idx is not None and idx.isValid():
                self.expand(idx)
        if path is not None:
            if use_pos:
                self.show_item_at_path(path)
            else:
                index = self._model.index_for_named_path(path)
                if index.isValid():
                    self.show_item_at_index(index)
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
