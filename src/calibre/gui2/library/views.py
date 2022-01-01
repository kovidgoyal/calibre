#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import itertools, operator
from functools import partial
from collections import OrderedDict

from qt.core import (
    QTableView, Qt, QAbstractItemView, QMenu, pyqtSignal, QFont, QModelIndex,
    QIcon, QItemSelection, QMimeData, QDrag, QStyle, QPoint, QUrl, QHeaderView, QEvent,
    QStyleOptionHeader, QItemSelectionModel, QSize, QFontMetrics, QApplication)

from calibre.constants import islinux
from calibre.gui2.dialogs.enum_values_edit import EnumValuesEdit
from calibre.gui2.library.delegates import (RatingDelegate, PubDateDelegate,
    TextDelegate, DateDelegate, CompleteDelegate, CcTextDelegate, CcLongTextDelegate,
    CcBoolDelegate, CcCommentsDelegate, CcDateDelegate, CcTemplateDelegate,
    CcEnumDelegate, CcNumberDelegate, LanguagesDelegate, SeriesDelegate, CcSeriesDelegate)
from calibre.gui2.library.models import BooksModel, DeviceBooksModel
from calibre.gui2.pin_columns import PinTableView
from calibre.gui2.library.alternate_views import AlternateViews, setup_dnd_interface, handle_enter_press
from calibre.gui2.gestures import GestureManager
from calibre.utils.config import tweaks, prefs
from calibre.gui2 import error_dialog, gprefs, FunctionDispatcher
from calibre.gui2.library import DEFAULT_SORT
from calibre.constants import filesystem_encoding
from calibre import force_unicode
from calibre.utils.icu import primary_sort_key
from polyglot.builtins import iteritems


def restrict_column_width(self, col, old_size, new_size):
    # arbitrary: scroll bar + header + some
    sw = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
    hw = self.verticalHeader().width() if self.verticalHeader().isVisible() else 0
    max_width = max(200, self.width() - (sw + hw + 10))
    if new_size > max_width:
        self.column_header.blockSignals(True)
        self.setColumnWidth(col, max_width)
        self.column_header.blockSignals(False)


class HeaderView(QHeaderView):  # {{{

    def __init__(self, *args):
        QHeaderView.__init__(self, *args)
        if self.orientation() == Qt.Orientation.Horizontal:
            self.setSectionsMovable(True)
            self.setSectionsClickable(True)
            self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hover = -1
        self.current_font = QFont(self.font())
        self.current_font.setBold(True)
        self.current_font.setItalic(True)
        self.fm = QFontMetrics(self.current_font)

    def event(self, e):
        if e.type() in (QEvent.Type.HoverMove, QEvent.Type.HoverEnter):
            self.hover = self.logicalIndexAt(e.position().toPoint())
        elif e.type() in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            self.hover = -1
        return QHeaderView.event(self, e)

    def sectionSizeFromContents(self, logical_index):
        self.ensurePolished()
        opt = QStyleOptionHeader()
        self.initStyleOption(opt)
        opt.section = logical_index
        opt.orientation = self.orientation()
        opt.fontMetrics = self.fm
        model = self.parent().model()
        opt.text = str(model.headerData(logical_index, opt.orientation, Qt.ItemDataRole.DisplayRole) or '')
        if opt.orientation == Qt.Orientation.Vertical:
            try:
                val = model.headerData(logical_index, opt.orientation, Qt.ItemDataRole.DecorationRole)
                if val is not None:
                    opt.icon = val
                opt.iconAlignment = Qt.AlignmentFlag.AlignVCenter
            except (IndexError, ValueError, TypeError):
                pass
        if self.isSortIndicatorShown():
            opt.sortIndicator = QStyleOptionHeader.SortIndicator.SortDown
        return self.style().sizeFromContents(QStyle.ContentsType.CT_HeaderSection, opt, QSize(), self)

    def paintSection(self, painter, rect, logical_index):
        opt = QStyleOptionHeader()
        self.initStyleOption(opt)
        opt.rect = rect
        opt.section = logical_index
        opt.orientation = self.orientation()
        opt.textAlignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        opt.fontMetrics = self.fm
        model = self.parent().model()
        style = self.style()
        margin = 2 * style.pixelMetric(QStyle.PixelMetric.PM_HeaderMargin, None, self)
        if self.isSortIndicatorShown() and self.sortIndicatorSection() == logical_index:
            opt.sortIndicator = QStyleOptionHeader.SortIndicator.SortDown if \
                self.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder else QStyleOptionHeader.SortIndicator.SortUp
            margin += style.pixelMetric(QStyle.PixelMetric.PM_HeaderMarkSize, None, self)
        opt.text = str(model.headerData(logical_index, opt.orientation, Qt.ItemDataRole.DisplayRole) or '')
        if self.textElideMode() != Qt.TextElideMode.ElideNone:
            opt.text = opt.fontMetrics.elidedText(opt.text, Qt.TextElideMode.ElideRight, rect.width() - margin)
        if self.isEnabled():
            opt.state |= QStyle.StateFlag.State_Enabled
            if self.window().isActiveWindow():
                opt.state |= QStyle.StateFlag.State_Active
                if self.hover == logical_index:
                    opt.state |= QStyle.StateFlag.State_MouseOver
        sm = self.selectionModel()
        if opt.orientation == Qt.Orientation.Vertical:
            try:
                val = model.headerData(logical_index, opt.orientation, Qt.ItemDataRole.DecorationRole)
                if val is not None:
                    opt.icon = val
                opt.iconAlignment = Qt.AlignmentFlag.AlignVCenter
            except (IndexError, ValueError, TypeError):
                pass
            if sm.isRowSelected(logical_index, QModelIndex()):
                opt.state |= QStyle.StateFlag.State_Sunken

        painter.save()
        if (
                (opt.orientation == Qt.Orientation.Horizontal and sm.currentIndex().column() == logical_index) or (
                    opt.orientation == Qt.Orientation.Vertical and sm.currentIndex().row() == logical_index)):
            painter.setFont(self.current_font)
        self.style().drawControl(QStyle.ControlElement.CE_Header, opt, painter, self)
        painter.restore()
# }}}


class PreserveViewState:  # {{{

    '''
    Save the set of selected books at enter time. If at exit time there are no
    selected books, restore the previous selection, the previous current index
    and dont affect the scroll position.
    '''

    def __init__(self, view, preserve_hpos=True, preserve_vpos=True,
            require_selected_ids=True):
        self.view = view
        self.require_selected_ids = require_selected_ids
        self.preserve_hpos = preserve_hpos
        self.preserve_vpos = preserve_vpos
        self.init_vals()

    def init_vals(self):
        self.selected_ids = set()
        self.current_id = None
        self.vscroll = self.hscroll = 0
        self.original_view = None

    def __enter__(self):
        self.init_vals()
        try:
            view = self.original_view = self.view.alternate_views.current_view
            self.selected_ids = self.view.get_selected_ids()
            self.current_id = self.view.current_id
            self.vscroll = view.verticalScrollBar().value()
            self.hscroll = view.horizontalScrollBar().value()
        except:
            import traceback
            traceback.print_exc()

    def __exit__(self, *args):
        if self.selected_ids or not self.require_selected_ids:
            if self.current_id is not None:
                self.view.current_id = self.current_id
            if self.selected_ids:
                self.view.select_rows(self.selected_ids, using_ids=True,
                        scroll=False, change_current=self.current_id is None)
            view = self.original_view
            if self.view.alternate_views.current_view is view:
                if self.preserve_vpos:
                    if hasattr(view, 'restore_vpos'):
                        view.restore_vpos(self.vscroll)
                    else:
                        view.verticalScrollBar().setValue(self.vscroll)
                if self.preserve_hpos:
                    if hasattr(view, 'restore_hpos'):
                        view.restore_hpos(self.hscroll)
                    else:
                        view.horizontalScrollBar().setValue(self.hscroll)
        self.init_vals()

    @property
    def state(self):
        self.__enter__()
        return {x:getattr(self, x) for x in ('selected_ids', 'current_id',
            'vscroll', 'hscroll')}

    @state.setter
    def state(self, state):
        for k, v in iteritems(state):
            setattr(self, k, v)
        self.__exit__()

# }}}


@setup_dnd_interface
class BooksView(QTableView):  # {{{

    files_dropped = pyqtSignal(object)
    books_dropped = pyqtSignal(object)
    selection_changed = pyqtSignal()
    add_column_signal = pyqtSignal()
    is_library_view = True

    def viewportEvent(self, event):
        if (event.type() == QEvent.Type.ToolTip and not gprefs['book_list_tooltips']):
            return False
        try:
            ret = self.gesture_manager.handle_event(event)
        except AttributeError:
            ret = None
        if ret is not None:
            return ret
        return QTableView.viewportEvent(self, event)

    def __init__(self, parent, modelcls=BooksModel, use_edit_metadata_dialog=True):
        QTableView.__init__(self, parent)
        self.pin_view = PinTableView(self, parent)
        self.gesture_manager = GestureManager(self)
        self.default_row_height = self.verticalHeader().defaultSectionSize()
        self.gui = parent
        self.setProperty('highlight_current_item', 150)
        self.pin_view.setProperty('highlight_current_item', 150)
        self.row_sizing_done = False
        self.alternate_views = AlternateViews(self)

        for wv in self, self.pin_view:
            if not tweaks['horizontal_scrolling_per_column']:
                wv.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            if not tweaks['vertical_scrolling_per_row']:
                wv.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

            wv.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
            tval = tweaks['doubleclick_on_library_view']
            if tval == 'edit_cell':
                wv.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked|wv.editTriggers())
            elif tval == 'open_viewer':
                wv.setEditTriggers(QAbstractItemView.EditTrigger.SelectedClicked|wv.editTriggers())
                wv.doubleClicked.connect(parent.iactions['View'].view_triggered)
            elif tval == 'show_book_details':
                wv.setEditTriggers(QAbstractItemView.EditTrigger.SelectedClicked|wv.editTriggers())
                wv.doubleClicked.connect(parent.iactions['Show Book Details'].show_book_info)
            elif tval == 'edit_metadata':
                # Must not enable single-click to edit, or the field will remain
                # open in edit mode underneath the edit metadata dialog
                if use_edit_metadata_dialog:
                    wv.doubleClicked.connect(
                            partial(parent.iactions['Edit Metadata'].edit_metadata,
                                    checked=False))
                else:
                    wv.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked|wv.editTriggers())

        setup_dnd_interface(self)
        for wv in self, self.pin_view:
            wv.setAlternatingRowColors(True)
            wv.setWordWrap(False)
        self.refresh_grid()

        self.rating_delegate = RatingDelegate(self)
        self.half_rating_delegate = RatingDelegate(self, is_half_star=True)
        self.timestamp_delegate = DateDelegate(self)
        self.pubdate_delegate = PubDateDelegate(self)
        self.last_modified_delegate = DateDelegate(self,
                tweak_name='gui_last_modified_display_format')
        self.languages_delegate = LanguagesDelegate(self)
        self.tags_delegate = CompleteDelegate(self, ',', 'all_tag_names')
        self.authors_delegate = CompleteDelegate(self, '&', 'all_author_names', True)
        self.cc_names_delegate = CompleteDelegate(self, '&', 'all_custom', True)
        self.series_delegate = SeriesDelegate(self)
        self.publisher_delegate = TextDelegate(self)
        self.text_delegate = TextDelegate(self)
        self.cc_text_delegate = CcTextDelegate(self)
        self.cc_series_delegate = CcSeriesDelegate(self)
        self.cc_longtext_delegate = CcLongTextDelegate(self)
        self.cc_enum_delegate = CcEnumDelegate(self)
        self.cc_bool_delegate = CcBoolDelegate(self)
        self.cc_comments_delegate = CcCommentsDelegate(self)
        self.cc_template_delegate = CcTemplateDelegate(self)
        self.cc_number_delegate = CcNumberDelegate(self)
        self.display_parent = parent
        self._model = modelcls(self)
        self.setModel(self._model)
        self.pin_view.setModel(self._model)
        self._model.count_changed_signal.connect(self.do_row_sizing,
                                                 type=Qt.ConnectionType.QueuedConnection)
        for wv in self, self.pin_view:
            wv.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            wv.setSortingEnabled(True)
        self.selectionModel().currentRowChanged.connect(self._model.current_changed)
        self.selectionModel().selectionChanged.connect(self.selection_changed.emit)
        self.preserve_state = partial(PreserveViewState, self)
        self.marked_changed_listener = FunctionDispatcher(self.marked_changed)

        # {{{ Column Header setup
        self.can_add_columns = True
        self.was_restored = False
        self.allow_save_state = True
        self.column_header = HeaderView(Qt.Orientation.Horizontal, self)
        self.pin_view.column_header = HeaderView(Qt.Orientation.Horizontal, self.pin_view)
        self.setHorizontalHeader(self.column_header)
        self.pin_view.setHorizontalHeader(self.pin_view.column_header)
        self.column_header.sectionMoved.connect(self.save_state)
        self.column_header.sortIndicatorChanged.disconnect()
        self.column_header.sortIndicatorChanged.connect(self.user_sort_requested)
        self.pin_view.column_header.sortIndicatorChanged.disconnect()
        self.pin_view.column_header.sortIndicatorChanged.connect(self.pin_view_user_sort_requested)
        self.column_header.customContextMenuRequested.connect(partial(self.show_column_header_context_menu, view=self))
        self.column_header.sectionResized.connect(self.column_resized, Qt.ConnectionType.QueuedConnection)
        if self.is_library_view:
            self.pin_view.column_header.sectionResized.connect(self.pin_view_column_resized, Qt.ConnectionType.QueuedConnection)
            self.pin_view.column_header.sectionMoved.connect(self.pin_view.save_state)
            self.pin_view.column_header.customContextMenuRequested.connect(partial(self.show_column_header_context_menu, view=self.pin_view))
        self.row_header = HeaderView(Qt.Orientation.Vertical, self)
        self.row_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.row_header.customContextMenuRequested.connect(self.show_row_header_context_menu)
        self.setVerticalHeader(self.row_header)
        # }}}

        self._model.database_changed.connect(self.database_changed)
        hv = self.verticalHeader()
        hv.setSectionsClickable(True)
        hv.setCursor(Qt.CursorShape.PointingHandCursor)
        self.selected_ids = []
        self._model.about_to_be_sorted.connect(self.about_to_be_sorted)
        self._model.sorting_done.connect(self.sorting_done,
                type=Qt.ConnectionType.QueuedConnection)
        self.set_row_header_visibility()
        self.allow_mirroring = True
        if self.is_library_view:
            self.set_pin_view_visibility(gprefs['book_list_split'])
            for wv in self, self.pin_view:
                wv.selectionModel().currentRowChanged.connect(partial(self.mirror_selection_between_views, wv))
                wv.selectionModel().selectionChanged.connect(partial(self.mirror_selection_between_views, wv))
                wv.verticalScrollBar().valueChanged.connect(partial(self.mirror_vscroll, wv))
                wv.verticalScrollBar().rangeChanged.connect(partial(self.mirror_vscroll, wv))
        else:
            self.pin_view.setVisible(False)

    # Pin view {{{
    def set_pin_view_visibility(self, visible=False):
        self.pin_view.setVisible(visible)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff if visible else Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mirror_selection_between_views(self)

    def mirror_selection_between_views(self, src):
        if self.allow_mirroring:
            dest = self.pin_view if src is self else self
            if dest is self.pin_view and not dest.isVisible():
                return
            self.allow_mirroring = False
            dest.selectionModel().select(src.selectionModel().selection(), QItemSelectionModel.SelectionFlag.ClearAndSelect)
            ci = dest.currentIndex()
            nci = src.selectionModel().currentIndex()
            # Save/restore horz scroll.  ci column may be scrolled out of view.
            hpos = dest.horizontalScrollBar().value()
            if ci.isValid():
                nci = dest.model().index(nci.row(), ci.column())
            dest.selectionModel().setCurrentIndex(nci, QItemSelectionModel.SelectionFlag.NoUpdate)
            dest.horizontalScrollBar().setValue(hpos)
            self.allow_mirroring = True

    def mirror_vscroll(self, src, *a):
        if self.allow_mirroring:
            dest = self.pin_view if src is self else self
            if dest is self.pin_view and not dest.isVisible():
                return
            self.allow_mirroring = False
            s, d = src.verticalScrollBar(), dest.verticalScrollBar()
            d.setRange(s.minimum(), s.maximum()), d.setValue(s.value())
            self.allow_mirroring = True
    # }}}

    # Column Header Context Menu {{{
    def column_header_context_handler(self, action=None, column=None, view=None):
        if action == 'split':
            self.set_pin_view_visibility(not self.pin_view.isVisible())
            gprefs['book_list_split'] = self.pin_view.isVisible()
            self.save_state()
            return
        if not action or not column or not view:
            return
        try:
            idx = self.column_map.index(column)
        except:
            return
        h = view.column_header

        if action == 'hide':
            if h.hiddenSectionCount() >= h.count():
                return error_dialog(self, _('Cannot hide all columns'), _(
                    'You must not hide all columns'), show=True)
            h.setSectionHidden(idx, True)
        elif action == 'show':
            h.setSectionHidden(idx, False)
            if h.sectionSize(idx) < 3:
                sz = h.sectionSizeHint(idx)
                h.resizeSection(idx, sz)
        elif action == 'ascending':
            self.sort_by_column_and_order(idx, True)
        elif action == 'descending':
            self.sort_by_column_and_order(idx, False)
        elif action == 'defaults':
            view.apply_state(view.get_default_state())
        elif action == 'addcustcol':
            self.add_column_signal.emit()
        elif action.startswith('align_'):
            alignment = action.partition('_')[-1]
            self._model.change_alignment(column, alignment)
        elif action.startswith('font_'):
            self._model.change_column_font(column, action[len('font_'):])
        elif action == 'quickview':
            from calibre.gui2.actions.show_quickview import get_quickview_action_plugin
            qv = get_quickview_action_plugin()
            if qv:
                rows = self.selectionModel().selectedRows()
                if len(rows) > 0:
                    current_row = rows[0].row()
                    current_col = self.column_map.index(column)
                    index = self.model().index(current_row, current_col)
                    qv.change_quickview_column(index)
        elif action == 'remember_ondevice_width':
            gprefs.set('ondevice_column_width', self.columnWidth(idx))
        elif action == 'reset_ondevice_width':
            gprefs.set('ondevice_column_width', 0)
            self.resizeColumnToContents(idx)
        elif action == 'edit_enum':
            EnumValuesEdit(self, self._model.db, column).exec()
        self.save_state()

    def create_context_menu(self, col, name, view):
        ans = QMenu(view)
        handler = partial(self.column_header_context_handler, view=view, column=col)
        if col not in ('ondevice', 'inlibrary'):
            ans.addAction(QIcon.ic('minus.png'), _('Hide column %s') % name, partial(handler, action='hide'))
        m = ans.addMenu(_('Sort on %s')  % name)
        m.setIcon(QIcon.ic('sort.png'))
        a = m.addAction(_('Ascending'), partial(handler, action='ascending'))
        d = m.addAction(_('Descending'), partial(handler, action='descending'))
        if self._model.sorted_on[0] == col:
            ac = a if self._model.sorted_on[1] else d
            ac.setCheckable(True)
            ac.setChecked(True)
        if col not in ('ondevice', 'inlibrary') and \
                (not self.model().is_custom_column(col) or
                 (self._model.custom_columns[col]['datatype'] != 'bool' or
                  self._model.custom_columns[col]['display'].get('bools_show_text', False))):
            m = ans.addMenu(_('Change text alignment for %s') % name)
            m.setIcon(QIcon.ic('format-justify-center.png'))
            al = self._model.alignment_map.get(col, 'left')
            for x, t in (('left', _('Left')), ('right', _('Right')), ('center', _('Center'))):
                a = m.addAction(QIcon.ic(f'format-justify-{x}.png'), t, partial(handler, action='align_'+x))
                if al == x:
                    a.setCheckable(True)
                    a.setChecked(True)
            if not isinstance(view, DeviceBooksView):
                col_font = self._model.styled_columns.get(col)
                m = ans.addMenu(_('Change font style for %s') % name)
                m.setIcon(QIcon.ic('format-text-bold.png'))
                for x, t, f in (
                        ('normal', _('Normal font'), None), ('bold', _('Bold font'), self._model.bold_font),
                        ('italic', _('Italic font'), self._model.italic_font), ('bi', _('Bold and Italic font'), self._model.bi_font),
                ):
                    a = m.addAction(t, partial(handler, action='font_' + x))
                    if x in ('bold', 'italic'):
                        a.setIcon(QIcon.ic(f'format-text-{x}.png'))
                    if f is col_font:
                        a.setCheckable(True)
                        a.setChecked(True)

        if self.is_library_view:
            if self._model.db.field_metadata[col]['is_category']:
                act = ans.addAction(QIcon.ic('quickview.png'), _('Quickview column %s') % name,
                                    partial(handler, action='quickview'))
                rows = self.selectionModel().selectedRows()
                if len(rows) > 1:
                    act.setEnabled(False)
            if self._model.db.field_metadata[col]['datatype'] == 'enumeration':
                ans.addAction(QIcon.ic('edit_input.png'), _('Edit permissible values for %s') % name,
                              partial(handler, action='edit_enum'))

        hidden_cols = {self.column_map[i]: i for i in range(view.column_header.count())
                       if view.column_header.isSectionHidden(i) and self.column_map[i] not in ('ondevice', 'inlibrary')}

        ans.addSeparator()
        if hidden_cols:
            m = ans.addMenu(_('Show column'))
            m.setIcon(QIcon.ic('plus.png'))
            hcols = [(hcol, str(self.model().headerData(hidx, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or ''))
                     for hcol, hidx in iteritems(hidden_cols)]
            hcols.sort(key=lambda x: primary_sort_key(x[1]))
            for hcol, hname in hcols:
                m.addAction(hname.replace('&', '&&'), partial(handler, action='show', column=hcol))
        ans.addSeparator()
        if col == 'ondevice':
            ans.addAction(_('Remember On Device column width'),
                partial(handler, action='remember_ondevice_width'))
            ans.addAction(_('Reset On Device column width to default'),
                partial(handler, action='reset_ondevice_width'))
        ans.addAction(_('Shrink column if it is too wide to fit'),
                partial(self.resize_column_to_fit, view, col))
        ans.addAction(_('Resize column to fit contents'),
                partial(self.fit_column_to_contents, view, col))
        ans.addAction(_('Restore default layout'), partial(handler, action='defaults'))
        if self.can_add_columns:
            ans.addAction(
                    QIcon(I('column.png')), _('Add your own columns'), partial(handler, action='addcustcol'))
        return ans

    def show_row_header_context_menu(self, pos):
        menu = QMenu(self)
        # Even when hidden, row numbers show if any marks show, which is why it makes
        # sense to offer "show row numbers" here. Saves having to go to Preferences
        # Look & feel, assuming you know the trick.
        if gprefs['row_numbers_in_book_list']:
            menu.addAction(_('Hide row numbers'), partial(self.hide_row_numbers, show=False))
        else:
            menu.addAction(_('Show row numbers'), partial(self.hide_row_numbers, show=True))
        db = self._model.db
        row = self.row_header.logicalIndexAt(pos)
        if row >= 0 and row < len(db.data):
            book_id_col = db.field_metadata['id']['rec_index']
            book_id = db.data[row][book_id_col]
            m = menu.addAction(_('Toggle mark for book'), lambda: db.data.toggle_marked_ids({book_id,}))
            ic = QIcon.ic('marked.png')
            m.setIcon(ic)
            from calibre.gui2.actions.mark_books import mark_books_with_text
            m = menu.addAction(_('Mark book with text label'), partial(mark_books_with_text, {book_id,}))
            m.setIcon(ic)
        menu.popup(self.mapToGlobal(pos))

    # Probably should change the method name, but leave it for compatibility
    def hide_row_numbers(self, show=False):
        gprefs['row_numbers_in_book_list'] = show
        self.set_row_header_visibility()

    def show_column_header_context_menu(self, pos, view=None):
        view = view or self
        idx = view.column_header.logicalIndexAt(pos)
        col = None
        if idx > -1 and idx < len(self.column_map):
            col = self.column_map[idx]
            name = str(self.model().headerData(idx, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or '')
            view.column_header_context_menu = self.create_context_menu(col, name, view)
        has_context_menu = hasattr(view, 'column_header_context_menu')
        if self.is_library_view and has_context_menu:
            view.column_header_context_menu.addSeparator()
            if not hasattr(view.column_header_context_menu, 'bl_split_action'):
                view.column_header_context_menu.bl_split_action = view.column_header_context_menu.addAction(
                        QIcon.ic('split.png'), 'xxx', partial(self.column_header_context_handler, action='split', column='title'))
            ac = view.column_header_context_menu.bl_split_action
            if self.pin_view.isVisible():
                ac.setText(_('Un-split the book list'))
            else:
                ac.setText(_('Split the book list'))
        if has_context_menu:
            view.column_header_context_menu.popup(view.column_header.mapToGlobal(pos))
    # }}}

    # Sorting {{{

    def set_sort_indicator(self, logical_idx, ascending):
        views = [self, self.pin_view] if self.is_library_view else [self]
        for v in views:
            ch = v.column_header
            ch.blockSignals(True)
            ch.setSortIndicator(logical_idx, Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder)
            ch.blockSignals(False)

    def sort_by_column_and_order(self, col, ascending):
        order = Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder
        self.column_header.blockSignals(True)
        self.column_header.setSortIndicator(col, order)
        self.column_header.blockSignals(False)
        self.model().sort(col, order)
        if self.is_library_view:
            self.set_sort_indicator(col, ascending)

    def user_sort_requested(self, col, order=Qt.SortOrder.AscendingOrder):
        if 0 <= col < len(self.column_map):
            field = self.column_map[col]
            self.intelligent_sort(field, order == Qt.SortOrder.AscendingOrder)

    def pin_view_user_sort_requested(self, col, order=Qt.SortOrder.AscendingOrder):
        if col < len(self.column_map) and col >= 0:
            field = self.column_map[col]
            self.intelligent_sort(field, order == Qt.SortOrder.AscendingOrder)

    def intelligent_sort(self, field, ascending):
        m = self.model()
        pname = 'previous_sort_order_' + self.__class__.__name__
        previous = gprefs.get(pname, {})
        if field == m.sorted_on[0] or field not in previous:
            self.sort_by_named_field(field, ascending)
            previous[field] = ascending
            gprefs[pname] = previous
            return
        previous[m.sorted_on[0]] = m.sorted_on[1]
        gprefs[pname] = previous
        self.sort_by_named_field(field, previous[field])

    def about_to_be_sorted(self, idc):
        selected_rows = [r.row() for r in self.selectionModel().selectedRows()]
        self.selected_ids = [idc(r) for r in selected_rows]

    def sorting_done(self, indexc):
        pos = self.horizontalScrollBar().value()
        self.select_rows(self.selected_ids, using_ids=True, change_current=True,
            scroll=True)
        self.selected_ids = []
        self.horizontalScrollBar().setValue(pos)

    def sort_by_named_field(self, field, order, reset=True):
        if field in self.column_map:
            idx = self.column_map.index(field)
            self.sort_by_column_and_order(idx, order)
        else:
            self._model.sort_by_named_field(field, order, reset)
            self.set_sort_indicator(-1, True)

    def multisort(self, fields, reset=True, only_if_different=False):
        if len(fields) == 0:
            return
        sh = self.cleanup_sort_history(self._model.sort_history,
                                       ignore_column_map=True)
        if only_if_different and len(sh) >= len(fields):
            ret=True
            for i,t in enumerate(fields):
                if t[0] != sh[i][0]:
                    ret = False
                    break
            if ret:
                return

        for n,d in reversed(fields):
            if n in list(self._model.db.field_metadata.keys()):
                sh.insert(0, (n, d))
        sh = self.cleanup_sort_history(sh, ignore_column_map=True)
        self._model.sort_history = [tuple(x) for x in sh]
        self._model.resort(reset=reset)
        col = fields[0][0]
        ascending = fields[0][1]
        try:
            idx = self.column_map.index(col)
        except Exception:
            idx = -1
        self.set_sort_indicator(idx, ascending)

    def resort(self):
        with self.preserve_state(preserve_vpos=False, require_selected_ids=False):
            self._model.resort(reset=True)

    def reverse_sort(self):
        with self.preserve_state(preserve_vpos=False, require_selected_ids=False):
            m = self.model()
            try:
                sort_col, order = m.sorted_on
            except TypeError:
                sort_col, order = 'date', True
            self.sort_by_named_field(sort_col, not order)
    # }}}

    # Ondevice column {{{
    def set_ondevice_column_visibility(self):
        col = self._model.column_map.index('ondevice')
        self.column_header.setSectionHidden(col, not self._model.device_connected)
        w = gprefs.get('ondevice_column_width', 0)
        if w > 0:
            self.setColumnWidth(col, w)
        if self.is_library_view:
            self.pin_view.column_header.setSectionHidden(col, True)

    def set_device_connected(self, is_connected):
        self._model.set_device_connected(is_connected)
        self.set_ondevice_column_visibility()
    # }}}

    # Save/Restore State {{{
    def get_state(self):
        h = self.column_header
        cm = self.column_map
        state = {}
        state['hidden_columns'] = [cm[i] for i in range(h.count())
                if h.isSectionHidden(i) and cm[i] != 'ondevice']
        state['last_modified_injected'] = True
        state['languages_injected'] = True
        state['sort_history'] = \
            self.cleanup_sort_history(self.model().sort_history, ignore_column_map=self.is_library_view)
        state['column_positions'] = {}
        state['column_sizes'] = {}
        state['column_alignment'] = self._model.alignment_map
        for i in range(h.count()):
            name = cm[i]
            state['column_positions'][name] = h.visualIndex(i)
            if name != 'ondevice':
                state['column_sizes'][name] = h.sectionSize(i)
        return state

    def write_state(self, state):
        db = getattr(self.model(), 'db', None)
        name = str(self.objectName())
        if name and db is not None:
            db.new_api.set_pref(name + ' books view state', state)

    def save_state(self):
        # Only save if we have been initialized (set_database called)
        if len(self.column_map) > 0 and self.was_restored and self.allow_save_state:
            state = self.get_state()
            self.write_state(state)
            if self.is_library_view:
                self.pin_view.save_state()

    def cleanup_sort_history(self, sort_history, ignore_column_map=False):
        history = []

        for col, order in sort_history:
            if not isinstance(order, bool):
                continue
            col = {'date':'timestamp', 'sort':'title'}.get(col, col)
            if ignore_column_map or col in self.column_map:
                if (not history or history[-1][0] != col):
                    history.append([col, order])
        return history

    def apply_sort_history(self, saved_history, max_sort_levels=3):
        if not saved_history:
            return
        if self.is_library_view:
            for col, order in reversed(self.cleanup_sort_history(
                    saved_history, ignore_column_map=True)[:max_sort_levels]):
                try:
                    self.sort_by_named_field(col, order)
                except KeyError:
                    pass
        else:
            for col, order in reversed(self.cleanup_sort_history(
                    saved_history)[:max_sort_levels]):
                self.sort_by_column_and_order(self.column_map.index(col), order)

    def apply_state(self, state, max_sort_levels=3, save_state=True):
        # set save_state=False if you will save the state yourself after calling
        # this method.
        h = self.column_header
        cmap = {}
        hidden = state.get('hidden_columns', [])
        for i, c in enumerate(self.column_map):
            cmap[c] = i
            if c != 'ondevice':
                h.setSectionHidden(i, c in hidden)

        positions = state.get('column_positions', {})
        pmap = {}
        for col, pos in positions.items():
            if col in cmap:
                pmap[pos] = col
        need_save_state = False
        # Resetting column positions triggers a save state. There can be a lot
        # of these. Batch them up and do it at the end.
        # Can't use blockSignals() because that prevents needed processing somewhere
        self.allow_save_state = False
        for pos in sorted(pmap.keys()):
            col = pmap[pos]
            idx = cmap[col]
            current_pos = h.visualIndex(idx)
            if current_pos != pos:
                need_save_state = True
                h.moveSection(current_pos, pos)
        self.allow_save_state = True
        if need_save_state and save_state:
            self.save_state()
        # Because of a bug in Qt 5 we have to ensure that the header is actually
        # relaid out by changing this value, without this sometimes ghost
        # columns remain visible when changing libraries
        for i in range(h.count()):
            val = h.isSectionHidden(i)
            h.setSectionHidden(i, not val)
            h.setSectionHidden(i, val)

        sizes = state.get('column_sizes', {})
        for col, size in sizes.items():
            if col in cmap:
                sz = sizes[col]
                if sz < 3:
                    sz = h.sectionSizeHint(cmap[col])
                h.resizeSection(cmap[col], sz)

        self.apply_sort_history(state.get('sort_history', None),
                max_sort_levels=max_sort_levels)

        for col, alignment in state.get('column_alignment', {}).items():
            self._model.change_alignment(col, alignment)

        for i in range(h.count()):
            if not h.isSectionHidden(i) and h.sectionSize(i) < 3:
                sz = h.sectionSizeHint(i)
                h.resizeSection(i, sz)

    def get_default_state(self):
        old_state = {
                'hidden_columns': ['last_modified', 'languages'],
                'sort_history':[DEFAULT_SORT],
                'column_positions': {},
                'column_sizes': {},
                'column_alignment': {
                    'size':'center',
                    'timestamp':'center',
                    'pubdate':'center'},
                'last_modified_injected': True,
                'languages_injected': True,
                }
        h = self.column_header
        cm = self.column_map
        for i in range(h.count()):
            name = cm[i]
            old_state['column_positions'][name] = i
            if name != 'ondevice':
                old_state['column_sizes'][name] = \
                    min(350, max(self.sizeHintForColumn(i),
                        h.sectionSizeHint(i)))
                if name in ('timestamp', 'last_modified'):
                    old_state['column_sizes'][name] += 12
        return old_state

    def get_old_state(self):
        ans = None
        name = str(self.objectName())
        if name:
            name += ' books view state'
            db = getattr(self.model(), 'db', None)
            if db is not None:
                ans = db.new_api.pref(name)
                if ans is None:
                    ans = gprefs.get(name, None)
                    try:
                        del gprefs[name]
                    except:
                        pass
                    if ans is not None:
                        db.new_api.set_pref(name, ans)
                else:
                    injected = False
                    if not ans.get('last_modified_injected', False):
                        injected = True
                        ans['last_modified_injected'] = True
                        hc = ans.get('hidden_columns', [])
                        if 'last_modified' not in hc:
                            hc.append('last_modified')
                    if not ans.get('languages_injected', False):
                        injected = True
                        ans['languages_injected'] = True
                        hc = ans.get('hidden_columns', [])
                        if 'languages' not in hc:
                            hc.append('languages')
                    if injected:
                        db.new_api.set_pref(name, ans)
        return ans

    def restore_state(self):
        old_state = self.get_old_state()
        if old_state is None:
            old_state = self.get_default_state()
        max_levels = 3

        if tweaks['sort_columns_at_startup'] is not None:
            sh = []
            try:
                for c,d in tweaks['sort_columns_at_startup']:
                    if not isinstance(d, bool):
                        d = True if d == 0 else False
                    sh.append((c, d))
            except:
                # Ignore invalid tweak values as users seem to often get them
                # wrong
                print('Ignoring invalid sort_columns_at_startup tweak, with error:')
                import traceback
                traceback.print_exc()
            old_state['sort_history'] = sh
            max_levels = max(3, len(sh))

        if self.is_library_view:
            self.pin_view.restore_state()

        self.column_header.blockSignals(True)
        self.apply_state(old_state, max_sort_levels=max_levels)
        self.column_header.blockSignals(False)

        self.do_row_sizing()

        self.was_restored = True

    def refresh_composite_edit(self):
        self.cc_template_delegate.refresh()

    def refresh_row_sizing(self):
        self.row_sizing_done = False
        self.do_row_sizing()

    def refresh_grid(self):
        for wv in self, self.pin_view:
            wv.setShowGrid(bool(gprefs['booklist_grid']))

    def do_row_sizing(self):
        # Resize all rows to have the correct height
        if not self.row_sizing_done and self.model().rowCount(QModelIndex()) > 0:
            vh = self.verticalHeader()
            h = max(vh.minimumSectionSize(), self.default_row_height + gprefs['book_list_extra_row_spacing'])
            vh.setDefaultSectionSize(h)
            if self.is_library_view:
                self.pin_view.verticalHeader().setDefaultSectionSize(h)
            self._model.set_row_height(self.rowHeight(0))
            self.row_sizing_done = True

    def resize_column_to_fit(self, view, column):
        col = self.column_map.index(column)
        w = view.columnWidth(col)
        restrict_column_width(view, col, w, w)

    def fit_column_to_contents(self, view, column):
        col = self.column_map.index(column)
        view.resizeColumnToContents(col)

    def column_resized(self, col, old_size, new_size):
        restrict_column_width(self, col, old_size, new_size)

    def pin_view_column_resized(self, col, old_size, new_size):
        restrict_column_width(self.pin_view, col, old_size, new_size)

    # }}}

    # Initialization/Delegate Setup {{{

    def set_database(self, db):
        self.alternate_views.set_database(db)
        self.save_state()
        self._model.set_database(db)
        self.tags_delegate.set_database(db)
        self.cc_names_delegate.set_database(db)
        self.authors_delegate.set_database(db)
        self.series_delegate.set_auto_complete_function(db.all_series)
        self.publisher_delegate.set_auto_complete_function(db.all_publishers)
        self.alternate_views.set_database(db, stage=1)

    def marked_changed(self, old_marked, current_marked):
        self.alternate_views.marked_changed(old_marked, current_marked)
        if bool(old_marked) == bool(current_marked):
            changed = old_marked | current_marked
            i = self.model().db.data.id_to_index

            def f(x):
                try:
                    return i(x)
                except ValueError:
                    pass
            sections = tuple(x for x in map(f, changed) if x is not None)
            if sections:
                self.row_header.headerDataChanged(Qt.Orientation.Vertical, min(sections), max(sections))
                # This is needed otherwise Qt does not always update the
                # viewport correctly. See https://bugs.launchpad.net/bugs/1404697
                self.row_header.viewport().update()
                # refresh the rows because there might be a composite that uses marked_books()
                self.model().refresh_rows(sections)
        else:
            # Marked items have either appeared or all been removed
            self.model().set_row_decoration(current_marked)
            self.row_header.headerDataChanged(Qt.Orientation.Vertical, 0, self.row_header.count()-1)
            self.row_header.geometriesChanged.emit()
            self.set_row_header_visibility()
            # refresh rows for the ids because there might be a composite that uses marked_books()
            self.model().refresh_ids(current_marked)

    def set_row_header_visibility(self):
        visible = self.model().row_decoration is not None or gprefs['row_numbers_in_book_list']
        self.row_header.setVisible(visible)

    def database_changed(self, db):
        db.data.add_marked_listener(self.marked_changed_listener)
        for i in range(self.model().columnCount(None)):
            for vw in self, self.pin_view:
                if vw.itemDelegateForColumn(i) in (
                        self.rating_delegate, self.timestamp_delegate, self.pubdate_delegate,
                        self.last_modified_delegate, self.languages_delegate, self.half_rating_delegate):
                    vw.setItemDelegateForColumn(i, vw.itemDelegate())

        cm = self.column_map

        def set_item_delegate(colhead, delegate):
            idx = cm.index(colhead)
            self.setItemDelegateForColumn(idx, delegate)
            self.pin_view.setItemDelegateForColumn(idx, delegate)

        for colhead in cm:
            if self._model.is_custom_column(colhead):
                cc = self._model.custom_columns[colhead]
                if cc['datatype'] == 'datetime':
                    delegate = CcDateDelegate(self)
                    delegate.set_format(cc['display'].get('date_format',''))
                    set_item_delegate(colhead, delegate)
                elif cc['datatype'] == 'comments':
                    ctype = cc['display'].get('interpret_as', 'html')
                    if ctype == 'short-text':
                        set_item_delegate(colhead, self.cc_text_delegate)
                    elif ctype in ('long-text', 'markdown'):
                        set_item_delegate(colhead, self.cc_longtext_delegate)
                    else:
                        set_item_delegate(colhead, self.cc_comments_delegate)
                elif cc['datatype'] == 'text':
                    if cc['is_multiple']:
                        if cc['display'].get('is_names', False):
                            set_item_delegate(colhead, self.cc_names_delegate)
                        else:
                            set_item_delegate(colhead, self.tags_delegate)
                    else:
                        set_item_delegate(colhead, self.cc_text_delegate)
                elif cc['datatype'] == 'series':
                    set_item_delegate(colhead, self.cc_series_delegate)
                elif cc['datatype'] in ('int', 'float'):
                    set_item_delegate(colhead, self.cc_number_delegate)
                elif cc['datatype'] == 'bool':
                    set_item_delegate(colhead, self.cc_bool_delegate)
                elif cc['datatype'] == 'rating':
                    d = self.half_rating_delegate if cc['display'].get('allow_half_stars', False) else self.rating_delegate
                    set_item_delegate(colhead, d)
                elif cc['datatype'] == 'composite':
                    set_item_delegate(colhead, self.cc_template_delegate)
                elif cc['datatype'] == 'enumeration':
                    set_item_delegate(colhead, self.cc_enum_delegate)
            else:
                dattr = colhead+'_delegate'
                delegate = colhead if hasattr(self, dattr) else 'text'
                set_item_delegate(colhead, getattr(self, delegate+'_delegate'))

        self.restore_state()
        self.set_ondevice_column_visibility()
        # in case there were marked books
        self.model().set_row_decoration(set())
        self.row_header.headerDataChanged(Qt.Orientation.Vertical, 0, self.row_header.count()-1)
        self.row_header.geometriesChanged.emit()
        # }}}

    # Context Menu {{{
    def set_context_menu(self, menu, edit_collections_action):
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.context_menu = menu
        self.alternate_views.set_context_menu(menu)
        self.edit_collections_action = edit_collections_action

    def show_context_menu(self, menu, event):
        from calibre.gui2.main_window import clone_menu
        m = clone_menu(menu) if islinux else menu
        m.popup(event.globalPos())
        event.accept()

    def contextMenuEvent(self, event):
        self.show_context_menu(self.context_menu, event)
    # }}}

    def handle_mouse_press_event(self, ev):
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            # Shift-Click in QTableView is badly behaved.
            index = self.indexAt(ev.pos())
            if not index.isValid():
                return QTableView.mousePressEvent(self, ev)
            ci = self.currentIndex()
            if not ci.isValid():
                return QTableView.mousePressEvent(self, ev)
            clicked_row = index.row()
            current_row = ci.row()
            sm = self.selectionModel()
            if clicked_row == current_row:
                sm.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
                return
            sr = sm.selectedRows()
            if not len(sr):
                sm.select(
                    index,
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Clear |
                    QItemSelectionModel.SelectionFlag.Current | QItemSelectionModel.SelectionFlag.Rows)
                return

            m = self.model()

            def new_selection(upper, lower):
                top_left = m.index(upper, 0)
                bottom_right = m.index(lower, m.columnCount(None) - 1)
                return QItemSelection(top_left, bottom_right)

            currently_selected = tuple(x.row() for x in sr)
            min_row = min(currently_selected)
            max_row = max(currently_selected)
            outside_current_selection = clicked_row < min_row or clicked_row > max_row
            existing_selection = sm.selection()
            if outside_current_selection:
                # We simply extend the current selection
                if clicked_row < min_row:
                    upper, lower = clicked_row, min_row
                else:
                    upper, lower = max_row, clicked_row
                existing_selection.merge(new_selection(upper, lower), QItemSelectionModel.SelectionFlag.Select)
            else:
                if current_row < clicked_row:
                    upper, lower = current_row, clicked_row
                else:
                    upper, lower  = clicked_row, current_row
                existing_selection.merge(new_selection(upper, lower), QItemSelectionModel.SelectionFlag.Toggle)
            sm.select(existing_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            sm.setCurrentIndex(
                # ensure clicked row is always selected
                index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        else:
            return QTableView.mousePressEvent(self, ev)

    @property
    def column_map(self):
        return self._model.column_map

    @property
    def visible_columns(self):
        h = self.horizontalHeader()
        logical_indices = (x for x in range(h.count()) if not h.isSectionHidden(x))
        rmap = {i:x for i, x in enumerate(self.column_map)}
        return (rmap[h.visualIndex(x)] for x in logical_indices if h.visualIndex(x) > -1)

    def refresh_book_details(self, force=False):
        idx = self.currentIndex()
        if not idx.isValid() and force:
            idx = self.model().index(0, 0)
        if idx.isValid():
            self._model.current_changed(idx, idx)
            return True
        return False

    def indices_for_merge(self, resolved=False):
        if not resolved:
            return self.alternate_views.current_view.indices_for_merge(resolved=True)
        return self.selectionModel().selectedRows()

    def scrollContentsBy(self, dx, dy):
        # Needed as Qt bug causes headerview to not always update when scrolling
        QTableView.scrollContentsBy(self, dx, dy)
        if dy != 0:
            self.column_header.update()

    def scroll_to_row(self, row):
        if row > -1:
            h = self.horizontalHeader()
            for i in range(h.count()):
                if not h.isSectionHidden(i) and h.sectionViewportPosition(i) >= 0:
                    self.scrollTo(self.model().index(row, i), QAbstractItemView.ScrollHint.PositionAtCenter)
                    break

    @property
    def current_book(self):
        ci = self.currentIndex()
        if ci.isValid():
            try:
                return self.model().db.data.index_to_id(ci.row())
            except (IndexError, ValueError, KeyError, TypeError, AttributeError):
                pass

    def current_book_state(self):
        return self.current_book, self.horizontalScrollBar().value(), self.pin_view.horizontalScrollBar().value()

    def restore_current_book_state(self, state):
        book_id, hpos, pv_hpos = state
        try:
            row = self.model().db.data.id_to_index(book_id)
        except (IndexError, ValueError, KeyError, TypeError, AttributeError):
            return
        self.set_current_row(row)
        self.scroll_to_row(row)
        self.horizontalScrollBar().setValue(hpos)
        if self.pin_view.isVisible():
            self.pin_view.horizontalScrollBar().setValue(pv_hpos)

    def set_current_row(self, row=0, select=True, for_sync=False, book_id=None):
        if book_id is not None:
            row = self.model().db.data.id_to_index(book_id)
        if row > -1 and row < self.model().rowCount(QModelIndex()):
            h = self.horizontalHeader()
            logical_indices = list(range(h.count()))
            logical_indices = [x for x in logical_indices if not
                    h.isSectionHidden(x)]
            pairs = [(x, h.visualIndex(x)) for x in logical_indices if
                    h.visualIndex(x) > -1]
            if not pairs:
                pairs = [(0, 0)]
            pairs.sort(key=lambda x: x[1])
            i = pairs[0][0]
            index = self.model().index(row, i)
            if for_sync:
                sm = self.selectionModel()
                sm.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            else:
                self.setCurrentIndex(index)
                if select:
                    sm = self.selectionModel()
                    sm.select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect|QItemSelectionModel.SelectionFlag.Rows)

    def select_cell(self, row_number=0, logical_column=0):
        if row_number > -1 and row_number < self.model().rowCount(QModelIndex()):
            index = self.model().index(row_number, logical_column)
            self.setCurrentIndex(index)
            sm = self.selectionModel()
            sm.select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect|QItemSelectionModel.SelectionFlag.Rows)
            sm.select(index, QItemSelectionModel.SelectionFlag.Current)
            self.clicked.emit(index)

    def row_at_top(self):
        pos = 0
        while pos < 100:
            ans = self.rowAt(pos)
            if ans > -1:
                return ans
            pos += 5

    def row_at_bottom(self):
        pos = self.viewport().height()
        limit = pos - 100
        while pos > limit:
            ans = self.rowAt(pos)
            if ans > -1:
                return ans
            pos -= 5

    def moveCursor(self, action, modifiers):
        orig = self.currentIndex()
        action = QAbstractItemView.CursorAction(action)
        index = QTableView.moveCursor(self, action, modifiers)
        if action == QAbstractItemView.CursorAction.MovePageDown:
            moved = index.row() - orig.row()
            try:
                rows = self.row_at_bottom() - self.row_at_top()
            except TypeError:
                rows = moved
            if moved > rows:
                index = self.model().index(orig.row() + rows, index.column())
        elif action == QAbstractItemView.CursorAction.MovePageUp:
            moved = orig.row() - index.row()
            try:
                rows = self.row_at_bottom() - self.row_at_top()
            except TypeError:
                rows = moved
            if moved > rows:
                index = self.model().index(orig.row() - rows, index.column())
        elif action == QAbstractItemView.CursorAction.MoveHome and modifiers & Qt.KeyboardModifier.ControlModifier:
            return self.model().index(0, orig.column())
        elif action == QAbstractItemView.CursorAction.MoveEnd and modifiers & Qt.KeyboardModifier.ControlModifier:
            return self.model().index(self.model().rowCount(QModelIndex()) - 1, orig.column())
        return index

    def selectionCommand(self, index, event):
        if event and event.type() == QEvent.Type.KeyPress and event.key() in (
                Qt.Key.Key_Home, Qt.Key.Key_End) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
        return super().selectionCommand(index, event)

    def keyPressEvent(self, ev):
        if handle_enter_press(self, ev):
            return
        if ev.key() == Qt.Key.Key_F2:
            key = self.column_map[self.currentIndex().column()]
            if self._model.db.field_metadata[key]['datatype'] == 'composite':
                self.cc_template_delegate.allow_one_edit()
        return QTableView.keyPressEvent(self, ev)

    def ids_to_rows(self, ids):
        row_map = OrderedDict()
        ids = frozenset(ids)
        m = self.model()
        for row in range(m.rowCount(QModelIndex())):
            if len(row_map) >= len(ids):
                break
            c = m.id(row)
            if c in ids:
                row_map[c] = row
        return row_map

    def select_rows(self, identifiers, using_ids=True, change_current=True,
            scroll=True):
        '''
        Select rows identified by identifiers. identifiers can be a set of ids,
        row numbers or QModelIndexes.
        '''
        rows = {x.row() if hasattr(x, 'row') else x for x in
            identifiers}
        if using_ids:
            rows = set()
            identifiers = set(identifiers)
            m = self.model()
            for row in range(m.rowCount(QModelIndex())):
                if m.id(row) in identifiers:
                    rows.add(row)
        rows = list(sorted(rows))
        if rows:
            row = rows[0]
            if change_current:
                self.set_current_row(row, select=False)
            if scroll:
                self.scroll_to_row(row)
        sm = self.selectionModel()
        sel = QItemSelection()
        m = self.model()
        max_col = m.columnCount(QModelIndex()) - 1
        # Create a range based selector for each set of contiguous rows
        # as supplying selectors for each individual row causes very poor
        # performance if a large number of rows has to be selected.
        for k, g in itertools.groupby(enumerate(rows), lambda i_x:i_x[0]-i_x[1]):
            group = list(map(operator.itemgetter(1), g))
            sel.merge(QItemSelection(m.index(min(group), 0),
                m.index(max(group), max_col)), QItemSelectionModel.SelectionFlag.Select)
        sm.select(sel, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        return rows

    def get_selected_ids(self, as_set=False):
        ans = []
        seen = set()
        m = self.model()
        for idx in self.selectedIndexes():
            r = idx.row()
            i = m.id(r)
            if i not in seen:
                ans.append(i)
                seen.add(i)
        return seen if as_set else ans

    @property
    def current_id(self):
        try:
            return self.model().id(self.currentIndex())
        except:
            pass
        return None

    @current_id.setter
    def current_id(self, val):
        if val is None:
            return
        m = self.model()
        for row in range(m.rowCount(QModelIndex())):
            if m.id(row) == val:
                self.set_current_row(row, select=False)
                break

    def show_next_book(self):
        ci = self.currentIndex()
        if not ci.isValid():
            self.set_current_row()
            return
        n = (ci.row() + 1) % self.model().rowCount(QModelIndex())
        self.set_current_row(n)

    @property
    def next_id(self):
        '''
        Return the id of the 'next' row (i.e. the first unselected row after
        the current row).
        '''
        ci = self.currentIndex()
        if not ci.isValid():
            return None
        selected_rows = frozenset(i.row() for i in self.selectedIndexes() if
            i.isValid())
        column = ci.column()

        for i in range(ci.row()+1, self.row_count()):
            if i in selected_rows:
                continue
            try:
                return self.model().id(self.model().index(i, column))
            except:
                pass

        # No unselected rows after the current row, look before
        for i in range(ci.row()-1, -1, -1):
            if i in selected_rows:
                continue
            try:
                return self.model().id(self.model().index(i, column))
            except:
                pass
        return None

    def close(self):
        self._model.close()

    def set_editable(self, editable, supports_backloading):
        self._model.set_editable(editable)

    def move_highlighted_row(self, forward):
        rows = self.selectionModel().selectedRows()
        if len(rows) > 0:
            current_row = rows[0].row()
        else:
            current_row = None
        id_to_select = self._model.get_next_highlighted_id(current_row, forward)
        if id_to_select is not None:
            self.select_rows([id_to_select], using_ids=True)

    def search_proxy(self, txt):
        if self.is_library_view:
            # Save the current book before doing the search, after the search
            # is completed, this book will become the current book and be
            # scrolled to if it is present in the search results
            self.alternate_views.save_current_book_state()
        self._model.search(txt)
        id_to_select = self._model.get_current_highlighted_id()
        if id_to_select is not None:
            self.select_rows([id_to_select], using_ids=True)
        elif self._model.highlight_only:
            self.clearSelection()
        if self.isVisible() and getattr(txt, 'as_you_type', False) is not True:
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    def connect_to_search_box(self, sb, search_done):
        sb.search.connect(self.search_proxy)
        self._search_done = search_done
        self._model.searched.connect(self.search_done)
        if self.is_library_view:
            self._model.search_done.connect(self.alternate_views.restore_current_book_state)

    def connect_to_book_display(self, bd):
        self._model.new_bookdisplay_data.connect(bd)

    def search_done(self, ok):
        self._search_done(self, ok)

    def row_count(self):
        return self._model.count()

# }}}


class DeviceBooksView(BooksView):  # {{{

    is_library_view = False

    def __init__(self, parent):
        BooksView.__init__(self, parent, DeviceBooksModel,
                           use_edit_metadata_dialog=False)
        self._model.resize_rows.connect(self.do_row_sizing,
                                                 type=Qt.ConnectionType.QueuedConnection)
        self.can_add_columns = False
        self.resize_on_select = False
        self.rating_delegate = None
        self.half_rating_delegate = None
        for i in range(10):
            self.setItemDelegateForColumn(i, TextDelegate(self))
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setAcceptDrops(False)
        self.set_row_header_visibility()

    def set_row_header_visibility(self):
        self.row_header.setVisible(gprefs['row_numbers_in_book_list'])

    def drag_data(self):
        m = self.model()
        rows = self.selectionModel().selectedRows()
        paths = [force_unicode(p, enc=filesystem_encoding) for p in m.paths(rows) if p]
        md = QMimeData()
        md.setData('application/calibre+from_device', b'dummy')
        md.setUrls([QUrl.fromLocalFile(p) for p in paths])
        drag = QDrag(self)
        drag.setMimeData(md)
        cover = self.drag_icon(m.cover(self.currentIndex().row()), len(paths) > 1)
        drag.setHotSpot(QPoint(-15, -15))
        drag.setPixmap(cover)
        return drag

    def contextMenuEvent(self, event):
        edit_collections = callable(getattr(self._model.db, 'supports_collections', None)) and \
            self._model.db.supports_collections() and \
            prefs['manage_device_metadata'] == 'manual'

        self.edit_collections_action.setVisible(edit_collections)
        self.context_menu.popup(event.globalPos())
        event.accept()

    def get_old_state(self):
        ans = None
        name = str(self.objectName())
        if name:
            name += ' books view state'
            ans = gprefs.get(name, None)
        return ans

    def write_state(self, state):
        name = str(self.objectName())
        if name:
            gprefs.set(name + ' books view state', state)

    def set_database(self, db):
        self._model.set_database(db)
        self.restore_state()

    def connect_dirtied_signal(self, slot):
        self._model.booklist_dirtied.connect(slot)

    def connect_upload_collections_signal(self, func=None, oncard=None):
        self._model.upload_collections.connect(partial(func, view=self, oncard=oncard))

    def dropEvent(self, *args):
        error_dialog(self, _('Not allowed'),
        _('Dropping onto a device is not supported. First add the book to the calibre library.')).exec()

    def set_editable(self, editable, supports_backloading):
        self._model.set_editable(editable)
        self.drag_allowed = supports_backloading

    def resort(self):
        h = self.horizontalHeader()
        self.model().sort(h.sortIndicatorSection(), h.sortIndicatorOrder())

    def reverse_sort(self):
        h = self.horizontalHeader()
        h.setSortIndicator(
            h.sortIndicatorSection(), Qt.SortOrder.AscendingOrder if h.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder else Qt.SortOrder.DescendingOrder)

# }}}
