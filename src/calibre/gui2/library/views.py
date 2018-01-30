#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import itertools, operator
from functools import partial
from future_builtins import map
from collections import OrderedDict

from PyQt5.Qt import (
    QTableView, Qt, QAbstractItemView, QMenu, pyqtSignal, QFont, QModelIndex,
    QIcon, QItemSelection, QMimeData, QDrag, QStyle, QPoint, QUrl, QHeaderView,
    QStyleOptionHeader, QItemSelectionModel, QSize, QFontMetrics)

from calibre.constants import islinux
from calibre.gui2.library.delegates import (RatingDelegate, PubDateDelegate,
    TextDelegate, DateDelegate, CompleteDelegate, CcTextDelegate, CcLongTextDelegate,
    CcBoolDelegate, CcCommentsDelegate, CcDateDelegate, CcTemplateDelegate,
    CcEnumDelegate, CcNumberDelegate, LanguagesDelegate)
from calibre.gui2.library.models import BooksModel, DeviceBooksModel
from calibre.gui2.pin_columns import PinTableView
from calibre.gui2.library.alternate_views import AlternateViews, setup_dnd_interface, handle_enter_press
from calibre.gui2.gestures import GestureManager
from calibre.utils.config import tweaks, prefs
from calibre.gui2 import error_dialog, gprefs, FunctionDispatcher
from calibre.gui2.library import DEFAULT_SORT
from calibre.constants import filesystem_encoding
from calibre import force_unicode


class HeaderView(QHeaderView):  # {{{

    def __init__(self, *args):
        QHeaderView.__init__(self, *args)
        self.hover = -1
        self.current_font = QFont(self.font())
        self.current_font.setBold(True)
        self.current_font.setItalic(True)
        self.fm = QFontMetrics(self.current_font)

    def event(self, e):
        if e.type() in (e.HoverMove, e.HoverEnter):
            self.hover = self.logicalIndexAt(e.pos())
        elif e.type() in (e.Leave, e.HoverLeave):
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
        opt.text = unicode(model.headerData(logical_index, opt.orientation, Qt.DisplayRole) or '')
        if opt.orientation == Qt.Vertical:
            try:
                val = model.headerData(logical_index, opt.orientation, Qt.DecorationRole)
                if val is not None:
                    opt.icon = val
                opt.iconAlignment = Qt.AlignVCenter
            except (IndexError, ValueError, TypeError):
                pass
        if self.isSortIndicatorShown():
            opt.sortIndicator = QStyleOptionHeader.SortDown
        return self.style().sizeFromContents(QStyle.CT_HeaderSection, opt, QSize(), self)

    def paintSection(self, painter, rect, logical_index):
        opt = QStyleOptionHeader()
        self.initStyleOption(opt)
        opt.rect = rect
        opt.section = logical_index
        opt.orientation = self.orientation()
        opt.textAlignment = Qt.AlignHCenter | Qt.AlignVCenter
        opt.fontMetrics = self.fm
        model = self.parent().model()
        style = self.style()
        margin = 2 * style.pixelMetric(style.PM_HeaderMargin, None, self)
        if self.isSortIndicatorShown() and self.sortIndicatorSection() == logical_index:
            opt.sortIndicator = QStyleOptionHeader.SortDown if self.sortIndicatorOrder() == Qt.AscendingOrder else QStyleOptionHeader.SortUp
            margin += style.pixelMetric(style.PM_HeaderMarkSize, None, self)
        opt.text = unicode(model.headerData(logical_index, opt.orientation, Qt.DisplayRole) or '')
        if self.textElideMode() != Qt.ElideNone:
            opt.text = opt.fontMetrics.elidedText(opt.text, Qt.ElideRight, rect.width() - margin)
        if self.isEnabled():
            opt.state |= QStyle.State_Enabled
            if self.window().isActiveWindow():
                opt.state |= QStyle.State_Active
                if self.hover == logical_index:
                    opt.state |= QStyle.State_MouseOver
        sm = self.selectionModel()
        if opt.orientation == Qt.Vertical:
            try:
                val = model.headerData(logical_index, opt.orientation, Qt.DecorationRole)
                if val is not None:
                    opt.icon = val
                opt.iconAlignment = Qt.AlignVCenter
            except (IndexError, ValueError, TypeError):
                pass
            if sm.isRowSelected(logical_index, QModelIndex()):
                opt.state |= QStyle.State_Sunken

        painter.save()
        if (
                (opt.orientation == Qt.Horizontal and sm.currentIndex().column() == logical_index) or
                (opt.orientation == Qt.Vertical and sm.currentIndex().row() == logical_index)):
            painter.setFont(self.current_font)
        self.style().drawControl(QStyle.CE_Header, opt, painter, self)
        painter.restore()
# }}}


class PreserveViewState(object):  # {{{

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

    @dynamic_property
    def state(self):
        def fget(self):
            self.__enter__()
            return {x:getattr(self, x) for x in ('selected_ids', 'current_id',
                'vscroll', 'hscroll')}

        def fset(self, state):
            for k, v in state.iteritems():
                setattr(self, k, v)
            self.__exit__()
        return property(fget=fget, fset=fset)

# }}}


@setup_dnd_interface
class BooksView(QTableView):  # {{{

    files_dropped = pyqtSignal(object)
    add_column_signal = pyqtSignal()
    is_library_view = True

    def viewportEvent(self, event):
        if (event.type() == event.ToolTip and not gprefs['book_list_tooltips']):
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
                wv.setHorizontalScrollMode(self.ScrollPerPixel)

            wv.setEditTriggers(self.EditKeyPressed)
            if tweaks['doubleclick_on_library_view'] == 'edit_cell':
                wv.setEditTriggers(self.DoubleClicked|wv.editTriggers())
            elif tweaks['doubleclick_on_library_view'] == 'open_viewer':
                wv.setEditTriggers(self.SelectedClicked|wv.editTriggers())
                wv.doubleClicked.connect(parent.iactions['View'].view_triggered)
            elif tweaks['doubleclick_on_library_view'] == 'edit_metadata':
                # Must not enable single-click to edit, or the field will remain
                # open in edit mode underneath the edit metadata dialog
                if use_edit_metadata_dialog:
                    wv.doubleClicked.connect(
                            partial(parent.iactions['Edit Metadata'].edit_metadata,
                                    checked=False))
                else:
                    wv.setEditTriggers(self.DoubleClicked|wv.editTriggers())

        setup_dnd_interface(self)
        for wv in self, self.pin_view:
            wv.setAlternatingRowColors(True)
            wv.setShowGrid(False)
            wv.setWordWrap(False)

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
        self.series_delegate = TextDelegate(self)
        self.publisher_delegate = TextDelegate(self)
        self.text_delegate = TextDelegate(self)
        self.cc_text_delegate = CcTextDelegate(self)
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
                                                 type=Qt.QueuedConnection)
        for wv in self, self.pin_view:
            wv.setSelectionBehavior(QAbstractItemView.SelectRows)
            wv.setSortingEnabled(True)
        self.selectionModel().currentRowChanged.connect(self._model.current_changed)
        self.preserve_state = partial(PreserveViewState, self)
        self.marked_changed_listener = FunctionDispatcher(self.marked_changed)

        # {{{ Column Header setup
        self.can_add_columns = True
        self.was_restored = False
        self.column_header = HeaderView(Qt.Horizontal, self)
        self.setHorizontalHeader(self.column_header)
        self.column_header.sortIndicatorChanged.disconnect()
        self.column_header.sortIndicatorChanged.connect(self.user_sort_requested)
        self.column_header.setSectionsMovable(True)
        self.column_header.setSectionsClickable(True)
        self.column_header.sectionMoved.connect(self.save_state)
        self.column_header.setContextMenuPolicy(Qt.CustomContextMenu)
        self.column_header.customContextMenuRequested.connect(self.show_column_header_context_menu)
        self.column_header.sectionResized.connect(self.column_resized, Qt.QueuedConnection)
        self.row_header = HeaderView(Qt.Vertical, self)
        self.row_header.setSectionResizeMode(self.row_header.Fixed)
        self.setVerticalHeader(self.row_header)
        # }}}

        self._model.database_changed.connect(self.database_changed)
        hv = self.verticalHeader()
        hv.setSectionsClickable(True)
        hv.setCursor(Qt.PointingHandCursor)
        self.selected_ids = []
        self._model.about_to_be_sorted.connect(self.about_to_be_sorted)
        self._model.sorting_done.connect(self.sorting_done,
                type=Qt.QueuedConnection)
        self.set_row_header_visibility()
        self.allow_mirroring = True
        if modelcls is not BooksModel:
            self.pin_view.setVisible(False)
        else:
            self.set_pin_view_visibility(gprefs['book_list_split'])
            self.pin_view.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)
            self.verticalScrollBar().valueChanged.connect(self.pin_view.verticalScrollBar().setValue)
            for wv in self, self.pin_view:
                wv.selectionModel().currentRowChanged.connect(partial(self.mirror_selection_between_views, wv))
                wv.selectionModel().selectionChanged.connect(partial(self.mirror_selection_between_views, wv))

    def set_pin_view_visibility(self, visible=False):
        self.pin_view.setVisible(visible)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff if visible else Qt.ScrollBarAsNeeded)

    def mirror_selection_between_views(self, src):
        if self.allow_mirroring:
            dest = self.pin_view if src is self else self
            self.allow_mirroring = False
            dest.selectionModel().select(src.selectionModel().selection(), QItemSelectionModel.ClearAndSelect)
            dest.selectionModel().setCurrentIndex(src.selectionModel().currentIndex(), QItemSelectionModel.NoUpdate)
            self.allow_mirroring = True

    # Column Header Context Menu {{{
    def column_header_context_handler(self, action=None, column=None):
        if not action or not column:
            return
        try:
            idx = self.column_map.index(column)
        except:
            return
        h = self.column_header

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
            self.apply_state(self.get_default_state())
        elif action == 'addcustcol':
            self.add_column_signal.emit()
        elif action.startswith('align_'):
            alignment = action.partition('_')[-1]
            self._model.change_alignment(column, alignment)
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
        elif action == 'split':
            self.set_pin_view_visibility(not self.pin_view.isVisible())
            gprefs['book_list_split'] = self.pin_view.isVisible()

        self.save_state()

    def show_column_header_context_menu(self, pos):
        idx = self.column_header.logicalIndexAt(pos)
        if idx > -1 and idx < len(self.column_map):
            col = self.column_map[idx]
            name = unicode(self.model().headerData(idx, Qt.Horizontal,
                    Qt.DisplayRole) or '')
            self.column_header_context_menu = QMenu(self)
            if col != 'ondevice':
                self.column_header_context_menu.addAction(_('Hide column %s') %
                        name,
                    partial(self.column_header_context_handler, action='hide',
                        column=col))
            m = self.column_header_context_menu.addMenu(
                    _('Sort on %s')  % name)
            a = m.addAction(_('Ascending'),
                    partial(self.column_header_context_handler,
                        action='ascending', column=col))
            d = m.addAction(_('Descending'),
                    partial(self.column_header_context_handler,
                        action='descending', column=col))
            if self._model.sorted_on[0] == col:
                ac = a if self._model.sorted_on[1] else d
                ac.setCheckable(True)
                ac.setChecked(True)
            if col not in ('ondevice', 'inlibrary') and \
                    (not self.model().is_custom_column(col) or
                    self.model().custom_columns[col]['datatype'] not in ('bool',
                        )):
                m = self.column_header_context_menu.addMenu(
                        _('Change text alignment for %s') % name)
                al = self._model.alignment_map.get(col, 'left')
                for x, t in (('left', _('Left')), ('right', _('Right')), ('center',
                    _('Center'))):
                        a = m.addAction(t,
                            partial(self.column_header_context_handler,
                            action='align_'+x, column=col))
                        if al == x:
                            a.setCheckable(True)
                            a.setChecked(True)

            if not isinstance(self, DeviceBooksView):
                if self._model.db.field_metadata[col]['is_category']:
                    act = self.column_header_context_menu.addAction(_('Quickview column %s') %
                            name,
                        partial(self.column_header_context_handler, action='quickview',
                            column=col))
                    rows = self.selectionModel().selectedRows()
                    if len(rows) > 1:
                        act.setEnabled(False)

            hidden_cols = [self.column_map[i] for i in
                    range(self.column_header.count()) if
                    self.column_header.isSectionHidden(i)]
            try:
                hidden_cols.remove('ondevice')
            except:
                pass
            if hidden_cols:
                self.column_header_context_menu.addSeparator()
                m = self.column_header_context_menu.addMenu(_('Show column'))
                for col in hidden_cols:
                    hidx = self.column_map.index(col)
                    name = unicode(self.model().headerData(hidx, Qt.Horizontal,
                            Qt.DisplayRole) or '')
                    m.addAction(name,
                        partial(self.column_header_context_handler,
                        action='show', column=col))

            self.column_header_context_menu.addSeparator()
            self.column_header_context_menu.addAction(
                    _('Shrink column if it is too wide to fit'),
                    partial(self.resize_column_to_fit, column=self.column_map[idx]))
            self.column_header_context_menu.addAction(
                    _('Restore default layout'),
                    partial(self.column_header_context_handler,
                        action='defaults', column=col))

            if self.can_add_columns:
                self.column_header_context_menu.addAction(
                        QIcon(I('column.png')),
                        _('Add your own columns'),
                        partial(self.column_header_context_handler,
                            action='addcustcol', column=col))

        self.column_header_context_menu.addSeparator()
        self.column_header_context_menu.addAction(
            _('Un-split the book list') if self.pin_view.isVisible() else _('Split the book list'),
            partial(self.column_header_context_handler, action='split', column=col or 'title'))
        self.column_header_context_menu.popup(self.column_header.mapToGlobal(pos))
    # }}}

    # Sorting {{{
    def sort_by_column_and_order(self, col, ascending):
        self.column_header.blockSignals(True)
        self.sortByColumn(col, Qt.AscendingOrder if ascending else Qt.DescendingOrder)
        self.column_header.blockSignals(False)

    def user_sort_requested(self, col, order=Qt.AscendingOrder):
        if col >= len(self.column_map) or col < 0:
            return QTableView.sortByColumn(self, col)
        field = self.column_map[col]
        self.intelligent_sort(field, order == Qt.AscendingOrder)

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
            self.column_header.blockSignals(True)
            self.column_header.setSortIndicator(-1, Qt.AscendingOrder)
            self.column_header.blockSignals(False)

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
            if n in self._model.db.field_metadata.keys():
                sh.insert(0, (n, d))
        sh = self.cleanup_sort_history(sh, ignore_column_map=True)
        self._model.sort_history = [tuple(x) for x in sh]
        self._model.resort(reset=reset)
        col = fields[0][0]
        dir = Qt.AscendingOrder if fields[0][1] else Qt.DescendingOrder
        if col in self.column_map:
            col = self.column_map.index(col)
            self.column_header.blockSignals(True)
            try:
                self.column_header.setSortIndicator(col, dir)
            finally:
                self.column_header.blockSignals(False)
    # }}}

    # Ondevice column {{{
    def set_ondevice_column_visibility(self):
        col, h = self._model.column_map.index('ondevice'), self.column_header
        h.setSectionHidden(col, not self._model.device_connected)

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
        name = unicode(self.objectName())
        if name and db is not None:
            db.new_api.set_pref(name + ' books view state', state)

    def save_state(self):
        # Only save if we have been initialized (set_database called)
        if len(self.column_map) > 0 and self.was_restored:
            state = self.get_state()
            self.write_state(state)

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
                self.sort_by_named_field(col, order)
        else:
            for col, order in reversed(self.cleanup_sort_history(
                    saved_history)[:max_sort_levels]):
                self.sort_by_column_and_order(self.column_map.index(col), order)

    def apply_state(self, state, max_sort_levels=3):
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
        for pos in sorted(pmap.keys()):
            col = pmap[pos]
            idx = cmap[col]
            current_pos = h.visualIndex(idx)
            if current_pos != pos:
                h.moveSection(current_pos, pos)

        # Because of a bug in Qt 5 we have to ensure that the header is actually
        # relaid out by changing this value, without this sometimes ghost
        # columns remain visible when changing libraries
        for i in xrange(h.count()):
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
        name = unicode(self.objectName())
        if name:
            name += ' books view state'
            db = getattr(self.model(), 'db', None)
            if db is not None:
                ans = db.prefs.get(name, None)
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

        self.column_header.blockSignals(True)
        self.apply_state(old_state, max_sort_levels=max_levels)
        self.column_header.blockSignals(False)

        self.do_row_sizing()

        self.was_restored = True

    def refresh_row_sizing(self):
        self.row_sizing_done = False
        self.do_row_sizing()

    def do_row_sizing(self):
        # Resize all rows to have the correct height
        if not self.row_sizing_done and self.model().rowCount(QModelIndex()) > 0:
            vh = self.verticalHeader()
            vh.setDefaultSectionSize(max(vh.minimumSectionSize(), self.default_row_height + gprefs['book_list_extra_row_spacing']))
            self._model.set_row_height(self.rowHeight(0))
            self.row_sizing_done = True

    def resize_column_to_fit(self, column):
        col = self.column_map.index(column)
        self.column_resized(col, self.columnWidth(col), self.columnWidth(col))

    def column_resized(self, col, old_size, new_size):
        # arbitrary: scroll bar + header + some
        max_width = self.width() - (self.verticalScrollBar().width() +
                                    self.verticalHeader().width() + 10)
        if max_width < 200:
            max_width = 200
        if new_size > max_width:
            self.column_header.blockSignals(True)
            self.setColumnWidth(col, max_width)
            self.column_header.blockSignals(False)

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
                self.row_header.headerDataChanged(Qt.Vertical, min(sections), max(sections))
                # This is needed otherwise Qt does not always update the
                # viewport correctly. See https://bugs.launchpad.net/bugs/1404697
                self.row_header.viewport().update()
        else:
            # Marked items have either appeared or all been removed
            self.model().set_row_decoration(current_marked)
            self.row_header.headerDataChanged(Qt.Vertical, 0, self.row_header.count()-1)
            self.row_header.geometriesChanged.emit()
            self.set_row_header_visibility()

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
                    set_item_delegate(colhead, self.cc_text_delegate)
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
        # incase there were marked books
        self.model().set_row_decoration(set())
        self.row_header.headerDataChanged(Qt.Vertical, 0, self.row_header.count()-1)
        self.row_header.geometriesChanged.emit()
        # }}}

    # Context Menu {{{
    def set_context_menu(self, menu, edit_collections_action):
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.context_menu = menu
        self.alternate_views.set_context_menu(menu)
        self.edit_collections_action = edit_collections_action

    def contextMenuEvent(self, event):
        from calibre.gui2.main_window import clone_menu
        m = clone_menu(self.context_menu) if islinux else self.context_menu
        m.popup(event.globalPos())
        event.accept()
    # }}}

    @property
    def column_map(self):
        return self._model.column_map

    @property
    def visible_columns(self):
        h = self.horizontalHeader()
        logical_indices = (x for x in xrange(h.count()) if not h.isSectionHidden(x))
        rmap = {i:x for i, x in enumerate(self.column_map)}
        return (rmap[h.visualIndex(x)] for x in logical_indices if h.visualIndex(x) > -1)

    def refresh_book_details(self):
        idx = self.currentIndex()
        if idx.isValid():
            self._model.current_changed(idx, idx)
            return True
        return False

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
                    self.scrollTo(self.model().index(row, i), self.PositionAtCenter)
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
        return self.current_book, self.horizontalScrollBar().value()

    def restore_current_book_state(self, state):
        book_id, hpos = state
        try:
            row = self.model().db.data.id_to_index(book_id)
        except (IndexError, ValueError, KeyError, TypeError, AttributeError):
            return
        self.set_current_row(row)
        self.scroll_to_row(row)
        self.horizontalScrollBar().setValue(hpos)

    def set_current_row(self, row=0, select=True, for_sync=False):
        if row > -1 and row < self.model().rowCount(QModelIndex()):
            h = self.horizontalHeader()
            logical_indices = list(range(h.count()))
            logical_indices = [x for x in logical_indices if not
                    h.isSectionHidden(x)]
            pairs = [(x, h.visualIndex(x)) for x in logical_indices if
                    h.visualIndex(x) > -1]
            if not pairs:
                pairs = [(0, 0)]
            pairs.sort(cmp=lambda x,y:cmp(x[1], y[1]))
            i = pairs[0][0]
            index = self.model().index(row, i)
            if for_sync:
                sm = self.selectionModel()
                sm.setCurrentIndex(index, sm.NoUpdate)
            else:
                self.setCurrentIndex(index)
                if select:
                    sm = self.selectionModel()
                    sm.select(index, sm.ClearAndSelect|sm.Rows)

    def select_cell(self, row_number=0, logical_column=0):
        if row_number > -1 and row_number < self.model().rowCount(QModelIndex()):
            index = self.model().index(row_number, logical_column)
            self.setCurrentIndex(index)
            sm = self.selectionModel()
            sm.select(index, sm.ClearAndSelect|sm.Rows)
            sm.select(index, sm.Current)
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
        index = QTableView.moveCursor(self, action, modifiers)
        if action == QTableView.MovePageDown:
            moved = index.row() - orig.row()
            try:
                rows = self.row_at_bottom() - self.row_at_top()
            except TypeError:
                rows = moved
            if moved > rows:
                index = self.model().index(orig.row() + rows, index.column())
        elif action == QTableView.MovePageUp:
            moved = orig.row() - index.row()
            try:
                rows = self.row_at_bottom() - self.row_at_top()
            except TypeError:
                rows = moved
            if moved > rows:
                index = self.model().index(orig.row() - rows, index.column())
        elif action == QTableView.MoveHome and modifiers & Qt.ControlModifier:
            return self.model().index(0, orig.column())
        elif action == QTableView.MoveEnd and modifiers & Qt.ControlModifier:
            return self.model().index(self.model().rowCount(QModelIndex()) - 1, orig.column())
        return index

    def selectionCommand(self, index, event):
        if event and event.type() == event.KeyPress and event.key() in (Qt.Key_Home, Qt.Key_End) and event.modifiers() & Qt.CTRL:
            return QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
        return super(BooksView, self).selectionCommand(index, event)

    def keyPressEvent(self, ev):
        if handle_enter_press(self, ev):
            return
        return QTableView.keyPressEvent(self, ev)

    def ids_to_rows(self, ids):
        row_map = OrderedDict()
        ids = frozenset(ids)
        m = self.model()
        for row in xrange(m.rowCount(QModelIndex())):
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
        rows = set([x.row() if hasattr(x, 'row') else x for x in
            identifiers])
        if using_ids:
            rows = set([])
            identifiers = set(identifiers)
            m = self.model()
            for row in xrange(m.rowCount(QModelIndex())):
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
        for k, g in itertools.groupby(enumerate(rows), lambda (i,x):i-x):
            group = list(map(operator.itemgetter(1), g))
            sel.merge(QItemSelection(m.index(min(group), 0),
                m.index(max(group), max_col)), sm.Select)
        sm.select(sel, sm.ClearAndSelect)

    def get_selected_ids(self):
        ans = []
        m = self.model()
        for idx in self.selectedIndexes():
            r = idx.row()
            i = m.id(r)
            if i not in ans:
                ans.append(i)
        return ans

    @dynamic_property
    def current_id(self):
        def fget(self):
            try:
                return self.model().id(self.currentIndex())
            except:
                pass
            return None

        def fset(self, val):
            if val is None:
                return
            m = self.model()
            for row in xrange(m.rowCount(QModelIndex())):
                if m.id(row) == val:
                    self.set_current_row(row, select=False)
                    break
        return property(fget=fget, fset=fset)

    @property
    def next_id(self):
        '''
        Return the id of the 'next' row (i.e. the first unselected row after
        the current row).
        '''
        ci = self.currentIndex()
        if not ci.isValid():
            return None
        selected_rows = frozenset([i.row() for i in self.selectedIndexes() if
            i.isValid()])
        column = ci.column()

        for i in xrange(ci.row()+1, self.row_count()):
            if i in selected_rows:
                continue
            try:
                return self.model().id(self.model().index(i, column))
            except:
                pass

        # No unselected rows after the current row, look before
        for i in xrange(ci.row()-1, -1, -1):
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
            self.setFocus(Qt.OtherFocusReason)

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
                                                 type=Qt.QueuedConnection)
        self.can_add_columns = False
        self.resize_on_select = False
        self.rating_delegate = None
        self.half_rating_delegate = None
        for i in range(10):
            self.setItemDelegateForColumn(i, TextDelegate(self))
        self.setDragDropMode(self.NoDragDrop)
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
        cover = self.drag_icon(m.cover(self.currentIndex().row()), len(paths) >
                1)
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
        name = unicode(self.objectName())
        if name:
            name += ' books view state'
            ans = gprefs.get(name, None)
        return ans

    def write_state(self, state):
        name = unicode(self.objectName())
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
        _('Dropping onto a device is not supported. First add the book to the calibre library.')).exec_()

    def set_editable(self, editable, supports_backloading):
        self._model.set_editable(editable)
        self.drag_allowed = supports_backloading

# }}}
