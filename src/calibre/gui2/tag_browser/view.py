#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import re
import traceback
from collections import defaultdict
from contextlib import suppress
from functools import partial

from qt.core import (
    QAbstractItemView,
    QApplication,
    QBrush,
    QColor,
    QCursor,
    QDialog,
    QDrag,
    QFont,
    QIcon,
    QLinearGradient,
    QMenu,
    QModelIndex,
    QPalette,
    QPen,
    QPoint,
    QPointF,
    QRect,
    QSize,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    Qt,
    QTimer,
    QToolTip,
    QTreeView,
    pyqtSignal,
)

from calibre import sanitize_file_name
from calibre.constants import config_dir
from calibre.ebooks.metadata import rating_to_stars
from calibre.gui2 import FunctionDispatcher, choose_files, config, empty_index, gprefs, pixmap_to_data, question_dialog, rating_font, safe_open_url
from calibre.gui2.complete2 import EditWithComplete
from calibre.gui2.dialogs.edit_category_notes import EditNoteDialog
from calibre.gui2.tag_browser.model import COUNT_ROLE, DRAG_IMAGE_ROLE, TAG_SEARCH_STATES, TagsModel, TagTreeItem, rename_only_in_vl_question
from calibre.gui2.widgets import EnLineEdit
from calibre.utils.icu import sort_key
from calibre.utils.serialize import json_loads


class TagDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, tags_view):
        QStyledItemDelegate.__init__(self, tags_view)
        self.old_look = False
        self.rating_pat = re.compile(r'[%s]' % rating_to_stars(3, True))
        self.rating_font = QFont(rating_font())
        self.tags_view = tags_view
        self.links_icon = QIcon.ic('external-link.png')
        self.notes_icon = QIcon.ic('notes.png')
        self.blank_icon = QIcon()

    def draw_average_rating(self, item, style, painter, option, widget):
        rating = item.average_rating
        if rating is None:
            return
        r = style.subElementRect(QStyle.SubElement.SE_ItemViewItemDecoration, option, widget)
        icon = option.icon
        painter.save()
        nr = r.adjusted(0, 0, 0, 0)
        nr.setBottom(r.bottom()-int(r.height()*(rating/5.0)))
        painter.setClipRect(nr)
        bg = option.palette.window()
        if self.old_look:
            bg = option.palette.alternateBase() if option.features&QStyleOptionViewItem.ViewItemFeature.Alternate else option.palette.base()
        painter.fillRect(r, bg)
        style.proxy().drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, widget)
        painter.setOpacity(0.3)
        icon.paint(painter, r, option.decorationAlignment, QIcon.Mode.Normal, QIcon.State.On)
        painter.restore()

    def draw_icon(self, style, painter, option, widget):
        r = style.subElementRect(QStyle.SubElement.SE_ItemViewItemDecoration, option, widget)
        icon = option.icon
        icon.paint(painter, r, option.decorationAlignment, QIcon.Mode.Normal, QIcon.State.On)

    def paint_text(self, painter, rect, flags, text, hover, option):
        painter.save()
        pen = painter.pen()
        if QApplication.instance().is_dark_theme:
            if hover:
                pen.setColor(QColor(Qt.GlobalColor.black))
            else:
                pen.setColor(option.palette.color(QPalette.ColorRole.WindowText))
        painter.setPen(pen)
        painter.drawText(rect, flags, text)
        painter.restore()

    def draw_text(self, style, painter, option, widget, index, item):
        tr = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, option, widget)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        flags = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextSingleLine
        lr = QRect(tr)
        lr.setRight(lr.right() * 2)
        text_rec = painter.boundingRect(lr, flags, text)
        hover = option.state & QStyle.StateFlag.State_MouseOver
        is_search = (True if item.type == TagTreeItem.TAG and
                            item.tag.category == 'search' else False)

        def render_count():
            if not is_search and (hover or gprefs['tag_browser_show_counts']):
                count = str(index.data(COUNT_ROLE))
                width = painter.fontMetrics().boundingRect(count).width()
                r = QRect(tr)
                r.setRight(r.right() - 1), r.setLeft(r.right() - width - 4)
                self.paint_text(painter, r, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, count, hover, option)
                tr.setRight(r.left() - 1)
            else:
                tr.setRight(tr.right() - 1)

        if item.type == TagTreeItem.TAG:
            category = item.tag.category
            name = item.tag.original_name
            tv = self.tags_view
            m = tv._model
            positions = {'links': (-1, -1), 'notes': (-1, -1)}

            # The icons fits in a rectangle height/2 + 4 x height/2 + 4. This
            # ensures they are a 'pleasant' size compared to the text.
            icon_width = int(tr.height()/2) + 4

            def render_link_icon():
                icon = self.links_icon if m.item_has_link(category, name) else self.blank_icon
                r = QRect(tr)
                r.setRight(r.right() - 1)
                r.setLeft(r.right() - icon_width)
                positions['links'] = (r.left(), r.left()+r.width())
                icon.paint(painter, r, option.decorationAlignment, QIcon.Mode.Normal, QIcon.State.On)
                tr.setRight(r.left() - 1)
            def render_note_icon():
                icon = self.notes_icon if m.item_has_note(category, name) else self.blank_icon
                r = QRect(tr)
                r.setRight(r.right() - 1)
                r.setLeft(r.right() - icon_width)
                positions['notes'] = (r.left(), r.left()+r.width())
                icon.paint(painter, r, option.decorationAlignment, QIcon.Mode.Normal, QIcon.State.On)
                tr.setRight(r.left() - 1)

            if gprefs['icons_on_right_in_tag_browser']:
                # Icons go far right, in columns after the counts
                show_note_icon = gprefs['show_notes_in_tag_browser'] and m.category_has_notes(category)
                show_link_icon = gprefs['show_links_in_tag_browser'] and m.category_has_links(category)
                if show_link_icon:
                    render_link_icon()
                if show_note_icon:
                    render_note_icon()
                render_count()
            else:
                # Icons go after the text to the left of the counts, not in columns
                show_note_icon = gprefs['show_notes_in_tag_browser'] and m.item_has_note(category, name)
                show_link_icon = gprefs['show_links_in_tag_browser'] and m.item_has_link(category, name)

                render_count()
                # The link icon has a margin of 1 px on each side. Account for
                # this when computing the width of the icons. If you change the
                # order of the icons then you must change this calculation
                w = (int(show_link_icon) * (icon_width + 2)) + (int(show_note_icon) * icon_width)
                # Leave a 5 px margin between the text and the icon.
                tr.setWidth(min(tr.width(), text_rec.width() + 5 + w))
                if show_link_icon:
                    render_link_icon()
                if show_note_icon:
                    render_note_icon()
            tv.category_button_positions[category][name] = positions
        else:
            render_count()

        is_rating = item.type == TagTreeItem.TAG and not self.rating_pat.sub('', text)
        if is_rating:
            painter.setFont(self.rating_font)
        if text_rec.width() > tr.width():
            g = QLinearGradient(QPointF(tr.topLeft()), QPointF(tr.topRight()))
            c = option.palette.color(QPalette.ColorRole.WindowText)
            g.setColorAt(0, c), g.setColorAt(0.8, c)
            c = QColor(c)
            c.setAlpha(0)
            g.setColorAt(1, c)
            pen = QPen()
            pen.setBrush(QBrush(g))
            painter.setPen(pen)
        self.paint_text(painter, tr, flags, text, hover, option)

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, empty_index)
        widget = self.parent()
        style = QApplication.style() if widget is None else widget.style()
        self.initStyleOption(option, index)
        item = index.data(Qt.ItemDataRole.UserRole)
        self.draw_icon(style, painter, option, widget)
        painter.save()
        self.draw_text(style, painter, option, widget, index, item)
        painter.restore()
        if item.boxed:
            r = style.subElementRect(QStyle.SubElement.SE_ItemViewItemFocusRect, option,
                    widget)
            painter.drawLine(r.bottomLeft(), r.bottomRight())
        if item.type == TagTreeItem.TAG and item.tag.state == 0 and config['show_avg_rating']:
            self.draw_average_rating(item, style, painter, option, widget)

    def createEditor(self, parent, option, index):
        item = self.tags_view.model().get_node(index)
        if not item.ignore_vl:
            if item.use_vl is None:
                if self.tags_view.model().get_in_vl():
                    item.use_vl = rename_only_in_vl_question(self.tags_view)
                else:
                    item.use_vl = False
            elif not item.use_vl and self.tags_view.model().get_in_vl():
                item.use_vl = not question_dialog(self.tags_view,
                                    _('Rename in Virtual library'), '<p>' +
                                    _('A Virtual library is active but you are renaming '
                                      'the item in all books in your library. Is '
                                      'this really what you want to do?') + '</p>',
                                    yes_text=_('Yes, apply in entire library'),
                                    no_text=_('No, apply only in Virtual library'),
                                    skip_dialog_name='tag_item_rename_in_entire_library')
        key, completion_data = '', None
        if item.type == TagTreeItem.CATEGORY:
            key = item.category_key
        elif item.type == TagTreeItem.TAG:
            key = getattr(item.tag, 'category', '')
        if key:
            from calibre.gui2.ui import get_gui
            with suppress(Exception):
                completion_data = get_gui().current_db.new_api.all_field_names(key)
        if completion_data:
            editor = EditWithComplete(parent)
            editor.set_separator(None)
            editor.update_items_cache(completion_data)
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
    restriction_error       = pyqtSignal(object)
    tag_item_delete         = pyqtSignal(object, object, object, object, object)
    tag_identifier_delete   = pyqtSignal(object, object)
    apply_tag_to_selected   = pyqtSignal(object, object, object)
    edit_enum_values        = pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent=None)
        self.possible_drag_start = None
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
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDropIndicatorShown(True)
        self.setAutoExpandDelay(500)
        self.pane_is_visible = False
        self.search_icon = QIcon.ic('search.png')
        self.search_copy_icon = QIcon.ic("search_copy_saved.png")
        self.user_category_icon = QIcon.ic('tb_folder.png')
        self.edit_metadata_icon = QIcon.ic('edit_input.png')
        self.delete_icon = QIcon.ic('list_remove.png')
        self.rename_icon = QIcon.ic('edit-undo.png')
        self.plus_icon = QIcon.ic('plus.png')
        self.minus_icon = QIcon.ic('minus.png')

        # Dict for recording the positions of the fake buttons for category tag
        # lines. It is recorded per category because we can't guarantee the
        # order that items are painted. The numbers get updated whenever an item
        # is painted, which deals with resizing.
        self.category_button_positions = defaultdict(dict)

        self._model = TagsModel(self)
        self._model.search_item_renamed.connect(self.search_item_renamed)
        self._model.refresh_required.connect(self.refresh_required,
                type=Qt.ConnectionType.QueuedConnection)
        self._model.tag_item_renamed.connect(self.tag_item_renamed)
        self._model.restriction_error.connect(self.restriction_error)
        self._model.user_categories_edited.connect(self.user_categories_edited,
                type=Qt.ConnectionType.QueuedConnection)
        self._model.drag_drop_finished.connect(self.drag_drop_finished)
        self._model.convert_requested.connect(self.convert_requested)
        self.set_look_and_feel(first=True)
        QApplication.instance().palette_changed.connect(self.set_style_sheet, type=Qt.ConnectionType.QueuedConnection)
        self.marked_change_listener = FunctionDispatcher(self.recount_on_mark_change)

    def convert_requested(self, book_ids, to_fmt):
        from calibre.gui2.ui import get_gui
        get_gui().iactions['Convert Books'].convert_ebooks_to_format(book_ids, to_fmt)

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

        '''.replace('PAD', str(gprefs['tag_browser_item_padding'])) + (
            '' if gprefs['tag_browser_old_look'] else stylish_tb) + QApplication.instance().palette_manager.tree_view_hover_style()
        )
        self.setProperty('hovered_item_is_highlighted', True)

    def set_look_and_feel(self, first=False):
        self.set_style_sheet()
        self.setAlternatingRowColors(gprefs['tag_browser_old_look'])
        self.itemDelegate().old_look = gprefs['tag_browser_old_look']

        if gprefs['tag_browser_allow_keyboard_focus']:
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        else:
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        pop = self.db.CATEGORY_SORTS.index(config['sort_tags_by'])
        self.alter_tb.sort_menu.actions()[pop].setChecked(True)
        try:
            match_pop = self.db.MATCH_TYPE.index(config['match_tags_type'])
        except ValueError:
            match_pop = 0
        self.alter_tb.match_menu.actions()[match_pop].setChecked(True)
        if not self.made_connections:
            self.clicked.connect(self.toggle_on_mouse_click)
            self.customContextMenuRequested.connect(self.show_context_menu)
            self.refresh_required.connect(self.recount, type=Qt.ConnectionType.QueuedConnection)
            self.alter_tb.sort_menu.triggered.connect(self.sort_changed)
            self.alter_tb.match_menu.triggered.connect(self.match_changed)
            self.made_connections = True
        self.refresh_signal_processed = True
        db.add_listener(self.database_changed)
        self.expanded.connect(self.item_expanded)
        self.collapsed.connect(self.collapse_node_and_children)
        db.data.add_marked_listener(self.marked_change_listener)

    def keyPressEvent(self, event):

        def on_last_visible_item(dex, check_children):
            model = self._model
            if model.get_node(dex) == model.root_item:
                # Got to root. There can't be any more children to show
                return True
            if check_children and self.isExpanded(dex):
                # We are on a node with expanded children so there is a node to go to.
                # We don't check children if we are moving up the parent hierarchy
                return False
            parent = model.parent(dex)
            if dex.row() < model.rowCount(parent) - 1:
                # Node has more nodes after it
                return False
            # Last node. Check the parent for further to see if there are more nodes
            return on_last_visible_item(parent, False)

        # I don't see how current_index can ever be not valid, but ...
        if self.currentIndex().isValid():
            key = event.key()
            if gprefs['tag_browser_allow_keyboard_focus']:
                if key == Qt.Key.Key_Return and self.state() != QAbstractItemView.State.EditingState:
                    self.toggle_current_index()
                    return
                # Check if we are moving the focus and we are at the beginning or the
                # end of the list. The goal is to prevent moving focus away from the
                # tag browser.
                if key == Qt.Key.Key_Tab:
                    if not on_last_visible_item(self.currentIndex(), True):
                        QTreeView.keyPressEvent(self, event)
                    return
                if key == Qt.Key.Key_Backtab:
                    if self.model().get_node(self.currentIndex()) != self._model.root_item.children[0]:
                        QTreeView.keyPressEvent(self, event)
                    return
            # If this is an edit request, mark the node to request whether to use VLs
            # As far as I can tell, F2 is used across all platforms
            if key == Qt.Key.Key_F2:
                node = self.model().get_node(self.currentIndex())
                if node.type == TagTreeItem.TAG:
                    # Saved search nodes don't use the VL test/dialog
                    node.use_vl = None
                    node.ignore_vl = node.tag.category == 'search'
                else:
                    # Don't open the editor for non-editable items
                    if not node.category_key.startswith('@') or node.is_gst:
                        return
                    # Category nodes don't use the VL test/dialog
                    node.use_vl = False
                    node.ignore_vl = True
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
        if event.buttons() & Qt.MouseButton.LeftButton:
            # Record the press point for processing during the clicked signal
            self.mouse_clicked_point = event.pos()
            # Only remember a possible drag start if the item is drag enabled
            dex = self.indexAt(event.pos())
            if self._model.flags(dex) & Qt.ItemFlag.ItemIsDragEnabled:
                self.possible_drag_start = event.pos()
            else:
                self.possible_drag_start = None
        return QTreeView.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        dex = self.indexAt(event.pos())
        if dex.isValid():
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return
        if not dex.isValid():
            QTreeView.mouseMoveEvent(self, event)
            return
        # don't start drag/drop until the mouse has moved a bit.
        if (self.possible_drag_start is None or
            (event.pos() - self.possible_drag_start).manhattanLength() <
                                    QApplication.startDragDistance()):
            QTreeView.mouseMoveEvent(self, event)
            return

        if not self._model.flags(dex) & Qt.ItemFlag.ItemIsDragEnabled:
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
            drag.exec(Qt.DropAction.CopyAction|Qt.DropAction.MoveAction, Qt.DropAction.CopyAction)
        else:
            drag.exec(Qt.DropAction.CopyAction)

    def mouseDoubleClickEvent(self, event):
        # swallow these to avoid toggling and editing at the same time
        pass

    @property
    def search_string(self):
        tokens = self._model.tokens()
        joiner = ' and ' if self.match_all else ' or '
        return joiner.join(tokens)

    def click_in_button_range(self, val, category, item_name, kind):
        range_tuple = self.category_button_positions[category].get(item_name, {}).get(kind)
        return range_tuple and range_tuple[0] <= val <= range_tuple[1]

    def toggle_current_index(self):
        ci = self.currentIndex()
        if ci.isValid():
            self.toggle(ci)

    def toggle_on_mouse_click(self, index):
        # Check if one of the link or note icons was clicked. If so, deal with
        # it here and don't do the real toggle
        t = self._model.data(index, Qt.UserRole)
        if t.type == TagTreeItem.TAG:
            db = self._model.db.new_api
            category = t.tag.category
            orig_name = t.tag.original_name
            x = self.mouse_clicked_point.x()
            if self.click_in_button_range(x, category, orig_name, 'notes'):
                from calibre.gui2.dialogs.show_category_note import ShowNoteDialog
                item_id = db.get_item_id(category, orig_name, case_sensitive=True)
                if db.notes_for(category, item_id):
                    ShowNoteDialog(category, item_id, db, parent=self).show()
                    return
            if self.click_in_button_range(x, category, orig_name, 'links'):
                link = db.get_link_map(category).get(orig_name)
                if link:
                    safe_open_url(link)
                    return
        self._toggle(index, None)

    def toggle(self, index):
        self._toggle(index, None)

    def _toggle(self, index, set_to):
        '''
        set_to: if None, advance the state. Otherwise must be one of the values
        in TAG_SEARCH_STATES
        '''
        exclusive = QApplication.keyboardModifiers() not in (Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier)
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
                             is_first_letter=False, ignore_vl=False,
                             extra=None):
        if not action:
            return
        from calibre.gui2.ui import get_gui
        try:
            if action == 'edit_note':
                if EditNoteDialog(category, extra, self.db).exec() == QDialog.DialogCode.Accepted:
                    get_gui().do_field_item_value_changed()
                return
            if action == 'dont_collapse_category':
                if key not in extra:
                    extra.append(key)
                self.db.prefs.set('tag_browser_dont_collapse', extra)
                self.recount()
                return
            if action == 'collapse_category':
                if key in extra:
                    extra.remove(key)
                self.db.prefs.set('tag_browser_dont_collapse', extra)
                self.recount()
                return
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
                        self._model.set_custom_category_icon(key, str(path))
                        self.recount()
                except:
                    traceback.print_exc()
                return
            if action == 'clear_icon':
                self._model.set_custom_category_icon(key, None)
                self.recount()
                return

            if action == 'edit_item_no_vl':
                item = self.model().get_node(index)
                item.use_vl = False
                item.ignore_vl = ignore_vl
                self.edit(index)
                return
            if action == 'edit_item_in_vl':
                item = self.model().get_node(index)
                item.use_vl = True
                item.ignore_vl = ignore_vl
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
            if action == 'delete_identifier':
                self.tag_identifier_delete.emit(index.tag.name, False)
                return
            if action == 'delete_identifier_in_vl':
                self.tag_identifier_delete.emit(index.tag.name, True)
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
                if not question_dialog(
                    self,
                    title=_('Delete Saved search'),
                    msg='<p>'+ _('Delete the saved search: {}?').format(key),
                    skip_dialog_name='tb_delete_saved_search',
                    skip_dialog_msg=_('Show this confirmation again')
                ):
                    return
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
            if action == 'remove_format':
                gui = get_gui()
                gui.iactions['Remove Books'].remove_format_from_selected_books(key)
                return
            if action == 'edit_open_with_apps':
                from calibre.gui2.open_with import edit_programs
                edit_programs(key, self)
                return
            if action == 'add_open_with_apps':
                from calibre.gui2.open_with import choose_program
                choose_program(key, self)
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
        key = None

        def add_show_hidden_categories():
            nonlocal added_show_hidden_categories
            if self.hidden_categories and not added_show_hidden_categories:
                added_show_hidden_categories = True
                m = self.context_menu.addMenu(_('Show category'))
                m.setIcon(QIcon.ic('plus.png'))
                # The search category can disappear from field_metadata. Perhaps
                # other dynamic categories can as well. The implication is that
                # dynamic categories are being removed, but how that would
                # happen is a mystery. I suspect a plugin is operating on the
                # "real" field_metadata instead of a copy, thereby changing the
                # dict used by the rest of calibre.
                #
                # As it can happen, to avoid key errors check that a category
                # exists before offering to unhide it.
                for col in sorted((c for c in self.hidden_categories if c in self.db.field_metadata),
                        key=lambda x: sort_key(self.db.field_metadata[x]['name'])):
                    ac = m.addAction(self.db.field_metadata[col]['name'],
                        partial(self.context_menu_handler, action='show', category=col))
                    ic = self.model().category_custom_icons.get(col)
                    if ic:
                        ac.setIcon(QIcon.ic(ic))
                m.addSeparator()
                m.addAction(_('All categories'),
                        partial(self.context_menu_handler, action='defaults')).setIcon(QIcon.ic('plusplus.png'))

        search_submenu = None
        if index.isValid():
            item = index.data(Qt.ItemDataRole.UserRole)
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
                category = str(item.name or '')
                key = item.category_key
                # Verify that we are working with a field that we know something about
                if key not in self.db.field_metadata:
                    return True
                fm = self.db.field_metadata[key]

                # Did the user click on a leaf node?
                if tag:
                    # If the user right-clicked on an editable item, then offer
                    # the possibility of renaming that item.
                    if (fm['datatype'] != 'composite' and
                            (tag.is_editable or tag.is_hierarchical) and
                            key != 'search'):
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
                                            action='edit_author_sort', index=tag.id)).setIcon(QIcon.ic('auto_author_sort.png'))
                            self.context_menu.addAction(_('Edit link for %s')%display_name(tag),
                                    partial(self.context_menu_handler,
                                            action='edit_author_link', index=tag.id)).setIcon(QIcon.ic('insert-link.png'))
                        elif self.db.new_api.has_link_map(key):
                            self.context_menu.addAction(_('Edit link for %s')%display_name(tag),
                                    partial(self.context_menu_handler, action='open_editor',
                                            category=tag.original_name if tag else None,
                                            key=key))

                        if self.db.new_api.field_supports_notes(key):
                            item_id = self.db.new_api.get_item_id(tag.category, tag.original_name, case_sensitive=True)
                            has_note = self._model.item_has_note(key, tag.original_name)
                            self.context_menu.addAction(self.edit_metadata_icon,
                                (_('Edit note for %s') if has_note else _('Create note for %s'))%display_name(tag),
                                partial(self.context_menu_handler, action='edit_note',
                                        index=index, extra=item_id, category=tag.category))

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
                                    index=index, ignore_vl=True))
                        self.context_menu.addAction(self.delete_icon,
                                _('Delete Saved search %s')%display_name(tag),
                                partial(self.context_menu_handler,
                                        action='delete_search', key=tag.original_name))
                    elif key == 'identifiers':
                        if self.model().get_in_vl():
                            self.context_menu.addAction(self.delete_icon,
                                    _('Delete %s in Virtual Library')%display_name(tag),
                                    partial(self.context_menu_handler,
                                            action='delete_identifier_in_vl',
                                            key=key, index=tag_item))
                        else:
                            self.context_menu.addAction(self.delete_icon,
                                    _('Delete %s')%display_name(tag),
                                    partial(self.context_menu_handler,
                                            action='delete_identifier',
                                            key=key, index=tag_item))

                    if key.startswith('@') and not item.is_gst:
                        self.context_menu.addAction(self.user_category_icon,
                            _('Remove {item} from category: {cat}').format(item=display_name(tag), cat=item.py_name),
                            partial(self.context_menu_handler, action='delete_item_from_user_category', key=key, index=tag_item))
                    if tag.is_searchable:
                        # Add the search for value items. All leaf nodes are searchable
                        self.context_menu.addSeparator()
                        search_submenu = self.context_menu.addMenu(_('Search for'))
                        search_submenu.setIcon(QIcon.ic('search.png'))
                        search_submenu.addAction(self.search_icon,
                                '%s'%display_name(tag),
                                partial(self.context_menu_handler, action='search',
                                        search_state=TAG_SEARCH_STATES['mark_plus'],
                                        index=index))
                        add_child_search = (tag.is_hierarchical == '5state' and
                                            len(tag_item.children))
                        if add_child_search:
                            search_submenu.addAction(self.search_icon,
                                    _('%s and its children')%display_name(tag),
                                    partial(self.context_menu_handler, action='search',
                                            search_state=TAG_SEARCH_STATES['mark_plusplus'],
                                            index=index))
                        search_submenu.addAction(self.search_icon,
                                _('Everything but %s')%display_name(tag),
                                partial(self.context_menu_handler, action='search',
                                        search_state=TAG_SEARCH_STATES['mark_minus'],
                                        index=index))
                        if add_child_search:
                            search_submenu.addAction(self.search_icon,
                                    _('Everything but %s and its children')%display_name(tag),
                                    partial(self.context_menu_handler, action='search',
                                            search_state=TAG_SEARCH_STATES['mark_minusminus'],
                                            index=index))
                        if key == 'search':
                            search_submenu.addAction(self.search_copy_icon,
                                     _('The saved search expression'),
                                     partial(self.context_menu_handler, action='raw_search',
                                             key=tag.original_name))
                    self.context_menu.addSeparator()
                elif key.startswith('@') and not item.is_gst:
                    if item.can_be_edited:
                        self.context_menu.addAction(self.rename_icon,
                            _('Rename %s')%item.py_name.replace('&', '&&'),
                            partial(self.context_menu_handler, action='edit_item_no_vl',
                                    index=index, ignore_vl=True))
                    self.context_menu.addAction(self.user_category_icon,
                            _('Add sub-category to %s')%item.py_name.replace('&', '&&'),
                            partial(self.context_menu_handler,
                                    action='add_subcategory', key=key))
                    self.context_menu.addAction(self.delete_icon,
                            _('Delete User category %s')%item.py_name.replace('&', '&&'),
                            partial(self.context_menu_handler,
                                    action='delete_user_category', key=key))
                    self.context_menu.addSeparator()
                # Add searches for temporary first letter nodes
                if self._model.collapse_model == 'first letter' and \
                        tag_item.temporary and not key.startswith('@'):
                    self.context_menu.addSeparator()
                    search_submenu = self.context_menu.addMenu(_('Search for'))
                    search_submenu.setIcon(QIcon.ic('search.png'))
                    search_submenu.addAction(self.search_icon,
                            '%s'%display_name(tag_item.tag),
                            partial(self.context_menu_handler, action='search',
                                    search_state=TAG_SEARCH_STATES['mark_plus'],
                                    index=index))
                    search_submenu.addAction(self.search_icon,
                            _('Everything but %s')%display_name(tag_item.tag),
                            partial(self.context_menu_handler, action='search',
                                    search_state=TAG_SEARCH_STATES['mark_minus'],
                                    index=index))
                # search by category. Some categories are not searchable, such
                # as search and news
                if item.tag.is_searchable:
                    if search_submenu is None:
                        search_submenu = self.context_menu.addMenu(_('Search for'))
                        search_submenu.setIcon(QIcon.ic('search.png'))
                        self.context_menu.addSeparator()
                    else:
                        search_submenu.addSeparator()
                    search_submenu.addAction(self.search_icon,
                            _('Books in category %s')%category,
                            partial(self.context_menu_handler,
                                    action='search_category',
                                    index=self._model.createIndex(item.row(), 0, item),
                                    search_state=TAG_SEARCH_STATES['mark_plus']))
                    search_submenu.addAction(self.search_icon,
                            _('Books not in category %s')%category,
                            partial(self.context_menu_handler,
                                    action='search_category',
                                    index=self._model.createIndex(item.row(), 0, item),
                                    search_state=TAG_SEARCH_STATES['mark_minus']))

                # Offer specific editors for tags/series/publishers/saved searches
                self.context_menu.addSeparator()
                if key in ['tags', 'publisher', 'series'] or (
                        fm['is_custom'] and fm['datatype'] != 'composite'):
                    if tag_item.type == TagTreeItem.CATEGORY and tag_item.temporary:
                        ac = self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='open_editor',
                                    category=tag_item.name,
                                    key=key, is_first_letter=True))
                    else:
                        ac = self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='open_editor',
                                    category=tag.original_name if tag else None,
                                    key=key))
                    ic = self.model().category_custom_icons.get(key)
                    if ic:
                        ac.setIcon(QIcon.ic(ic))
                    if fm['datatype'] == 'enumeration':
                        self.context_menu.addAction(_('Edit permissible values for %s')%category,
                            partial(self.context_menu_handler, action='edit_enum',
                                    key=key))
                elif key == 'authors':
                    if tag_item.type == TagTreeItem.CATEGORY:
                        if tag_item.temporary:
                            ac = self.context_menu.addAction(_('Manage %s')%category,
                                partial(self.context_menu_handler, action='edit_authors',
                                        index=tag_item.name, is_first_letter=True))
                        else:
                            ac = self.context_menu.addAction(_('Manage %s')%category,
                                partial(self.context_menu_handler, action='edit_authors'))
                    else:
                        ac = self.context_menu.addAction(_('Manage %s')%category,
                            partial(self.context_menu_handler, action='edit_authors',
                                    index=tag.id))
                    ic = self.model().category_custom_icons.get(key)
                    if ic:
                        ac.setIcon(QIcon.ic(ic))
                elif key == 'search':
                    self.context_menu.addAction(_('Manage Saved searches'),
                        partial(self.context_menu_handler, action='manage_searches',
                                category=tag.name if tag else None))
                elif key == 'formats' and tag is not None:
                    self.context_menu.addAction(_('Remove the {} format from selected books').format(tag.name),
                             partial(self.context_menu_handler, action='remove_format', key=tag.name))
                    self.context_menu.addSeparator()
                    self.context_menu.addAction(_('Add other application for %s files') % format(tag.name.upper()),
                             partial(self.context_menu_handler, action='add_open_with_apps', key=tag.name))
                    self.context_menu.addAction(_('Edit Open with applications for {} files').format(tag.name),
                             partial(self.context_menu_handler, action='edit_open_with_apps', key=tag.name))

                # Hide/Show/Restore categories
                self.context_menu.addSeparator()
                # Because of the strange way hierarchy works in user categories
                # where child nodes actually exist we must limit hiding to top-
                # level categories, which will hide that category and children
                if not key.startswith('@') or '.' not in key:
                    self.context_menu.addAction(_('Hide category %s') % category.replace('&', '&&'),
                        partial(self.context_menu_handler, action='hide',
                            category=key)).setIcon(QIcon.ic('minus.png'))
                add_show_hidden_categories()

                if tag is None:
                    cm = self.context_menu
                    cm.addSeparator()
                    acategory = category.replace('&', '&&')
                    sm = cm.addAction(_('Change {} category icon').format(acategory),
                                      partial(self.context_menu_handler, action='set_icon',
                                              key=key, category=category))
                    sm.setIcon(QIcon.ic('icon_choose.png'))
                    sm = cm.addAction(_('Restore {} category default icon').format(acategory),
                                      partial(self.context_menu_handler, action='clear_icon',
                                              key=key, category=category))
                    sm.setIcon(QIcon.ic('edit-clear.png'))
                    if key == 'search' and 'search' in self.db.new_api.pref('categories_using_hierarchy', ()):
                        sm = cm.addAction(_('Change Saved searches folder icon'),
                                          partial(self.context_menu_handler, action='set_icon',
                                                  key='search_folder:', category=_('Saved searches folder')))
                        sm.setIcon(QIcon.ic('icon_choose.png'))
                        sm = cm.addAction(_('Restore Saved searches folder default icon'),
                             partial(self.context_menu_handler, action='clear_icon',
                                     key='search_folder:', category=_('Saved searches folder')))
                        sm.setIcon(QIcon.ic('edit-clear.png'))

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

        # partitioning. If partitioning is active, provide a way to turn it on or
        # off for this category.
        if gprefs['tags_browser_partition_method'] != 'disable' and key is not None:
            m = self.context_menu
            p = self.db.prefs.get('tag_browser_dont_collapse', gprefs['tag_browser_dont_collapse'])
            if key in p:
                a = m.addAction(_('Sub-categorize {}').format(category),
                                partial(self.context_menu_handler, action='collapse_category',
                                        category=category, key=key, extra=p))
            else:
                a = m.addAction(_("Don't sub-categorize {}").format(category),
                                partial(self.context_menu_handler, action='dont_collapse_category',
                                        category=category, key=key, extra=p))
            a.setIcon(QIcon.ic('config.png'))
        # Set the partitioning scheme
        m = self.context_menu.addMenu(_('Change sub-categorization scheme'))
        m.setIcon(QIcon.ic('config.png'))
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

        # Ask plugins if they have any actions to add to the context menu
        from calibre.gui2.ui import get_gui
        first = True
        for ac in get_gui().iactions.values():
            try:
                for context_action in ac.tag_browser_context_action(index):
                    if first:
                        self.context_menu.addSeparator()
                        first = False
                    self.context_menu.addAction(context_action)
            except Exception:
                import traceback
                traceback.print_exc()

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
        item = index.data(Qt.ItemDataRole.UserRole)
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
                event.setDropAction(Qt.DropAction.MoveAction)
                self.setDropIndicatorShown(True)
                return
        # We aren't dropping an item on its own category. Check if the dest is
        # not a user category and can be dropped on. This covers drops from the
        # booklist. It is OK to drop onto virtual nodes
        if item.type == TagTreeItem.TAG and self._model.flags(index) & Qt.ItemFlag.ItemIsDropEnabled:
            event.setDropAction(Qt.DropAction.CopyAction)
            self.setDropIndicatorShown(not src_is_tb)
            return
        # Now see if we are on a user category and the source can be dropped there
        if item.type == TagTreeItem.CATEGORY and not item.is_gst:
            fm_dest = self.db.metadata_for_field(item.category_key)
            if fm_dest['kind'] == 'user':
                if src_is_tb:
                    # src_md and src_item are initialized above
                    if event.dropAction() == Qt.DropAction.MoveAction:
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
        item = idx.data(Qt.ItemDataRole.UserRole)
        if getattr(item, 'type', None) == TagTreeItem.TAG:
            idx = idx.parent()
        return self.isExpanded(idx)

    def recount_on_mark_change(self, *args):
        # Let other marked listeners run before we do the recount
        QTimer.singleShot(0, self.recount)

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
                          position=QAbstractItemView.ScrollHint.PositionAtCenter):
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
                           position=QAbstractItemView.ScrollHint.PositionAtCenter):
        if idx.isValid() and idx.data(Qt.ItemDataRole.UserRole) is not self._model.root_item:
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
