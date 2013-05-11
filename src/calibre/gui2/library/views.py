#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, itertools, operator
from functools import partial
from future_builtins import map
from collections import OrderedDict

from PyQt4.Qt import (QTableView, Qt, QAbstractItemView, QMenu, pyqtSignal, QFont,
    QModelIndex, QIcon, QItemSelection, QMimeData, QDrag, QApplication, QStyle,
    QPoint, QPixmap, QUrl, QImage, QPainter, QColor, QRect, QHeaderView, QStyleOptionHeader)

from calibre.gui2.library.delegates import (RatingDelegate, PubDateDelegate,
    TextDelegate, DateDelegate, CompleteDelegate, CcTextDelegate,
    CcBoolDelegate, CcCommentsDelegate, CcDateDelegate, CcTemplateDelegate,
    CcEnumDelegate, CcNumberDelegate, LanguagesDelegate)
from calibre.gui2.library.models import BooksModel, DeviceBooksModel
from calibre.utils.config import tweaks, prefs
from calibre.gui2 import error_dialog, gprefs
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

    def event(self, e):
        if e.type() in (e.HoverMove, e.HoverEnter):
            self.hover = self.logicalIndexAt(e.pos())
        elif e.type() in (e.Leave, e.HoverLeave):
            self.hover = -1
        return QHeaderView.event(self, e)

    def paintSection(self, painter, rect, logical_index):
        opt = QStyleOptionHeader()
        self.initStyleOption(opt)
        opt.rect = rect
        opt.section = logical_index
        opt.orientation = self.orientation()
        opt.textAlignment = Qt.AlignHCenter | Qt.AlignVCenter
        model = self.parent().model()
        opt.text = model.headerData(logical_index, opt.orientation, Qt.DisplayRole).toString()
        if self.isSortIndicatorShown() and self.sortIndicatorSection() == logical_index:
            opt.sortIndicator = QStyleOptionHeader.SortDown if self.sortIndicatorOrder() == Qt.AscendingOrder else QStyleOptionHeader.SortUp
        opt.text = opt.fontMetrics.elidedText(opt.text, Qt.ElideRight, rect.width() - 4)
        if self.isEnabled():
            opt.state |= QStyle.State_Enabled
            if self.window().isActiveWindow():
                opt.state |= QStyle.State_Active
                if self.hover == logical_index:
                    opt.state |= QStyle.State_MouseOver
        sm = self.selectionModel()
        if opt.orientation == Qt.Vertical:
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
        self.selected_ids = set()
        self.current_id = None
        self.preserve_hpos = preserve_hpos
        self.preserve_vpos = preserve_vpos
        self.vscroll = self.hscroll = 0

    def __enter__(self):
        try:
            self.selected_ids = self.view.get_selected_ids()
            self.current_id = self.view.current_id
            self.vscroll = self.view.verticalScrollBar().value()
            self.hscroll = self.view.horizontalScrollBar().value()
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
            if self.preserve_vpos:
                self.view.verticalScrollBar().setValue(self.vscroll)
            if self.preserve_hpos:
                self.view.horizontalScrollBar().setValue(self.hscroll)

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

class BooksView(QTableView):  # {{{

    files_dropped = pyqtSignal(object)
    add_column_signal = pyqtSignal()

    def viewportEvent(self, event):
        if (event.type() == event.ToolTip and not gprefs['book_list_tooltips']):
            return False
        return QTableView.viewportEvent(self, event)

    def __init__(self, parent, modelcls=BooksModel, use_edit_metadata_dialog=True):
        QTableView.__init__(self, parent)
        self.row_sizing_done = False

        if not tweaks['horizontal_scrolling_per_column']:
            self.setHorizontalScrollMode(self.ScrollPerPixel)

        self.setEditTriggers(self.EditKeyPressed)
        if tweaks['doubleclick_on_library_view'] == 'edit_cell':
            self.setEditTriggers(self.DoubleClicked|self.editTriggers())
        elif tweaks['doubleclick_on_library_view'] == 'open_viewer':
            self.setEditTriggers(self.SelectedClicked|self.editTriggers())
            self.doubleClicked.connect(parent.iactions['View'].view_triggered)
        elif tweaks['doubleclick_on_library_view'] == 'edit_metadata':
            # Must not enable single-click to edit, or the field will remain
            # open in edit mode underneath the edit metadata dialog
            if use_edit_metadata_dialog:
                self.doubleClicked.connect(
                        partial(parent.iactions['Edit Metadata'].edit_metadata,
                                checked=False))
            else:
                self.setEditTriggers(self.DoubleClicked|self.editTriggers())

        self.drag_allowed = True
        self.setDragEnabled(True)
        self.setDragDropOverwriteMode(False)
        self.setDragDropMode(self.DragDrop)
        self.drag_start_pos = None
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(self.SelectRows)
        self.setShowGrid(False)
        self.setWordWrap(False)

        self.rating_delegate = RatingDelegate(self)
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
        self.cc_enum_delegate = CcEnumDelegate(self)
        self.cc_bool_delegate = CcBoolDelegate(self)
        self.cc_comments_delegate = CcCommentsDelegate(self)
        self.cc_template_delegate = CcTemplateDelegate(self)
        self.cc_number_delegate = CcNumberDelegate(self)
        self.display_parent = parent
        self._model = modelcls(self)
        self.setModel(self._model)
        self._model.count_changed_signal.connect(self.do_row_sizing,
                                                 type=Qt.QueuedConnection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)
        self.selectionModel().currentRowChanged.connect(self._model.current_changed)
        self.preserve_state = partial(PreserveViewState, self)

        # {{{ Column Header setup
        self.can_add_columns = True
        self.was_restored = False
        self.column_header = HeaderView(Qt.Horizontal, self)
        self.setHorizontalHeader(self.column_header)
        self.column_header.setMovable(True)
        self.column_header.setClickable(True)
        self.column_header.sectionMoved.connect(self.save_state)
        self.column_header.setContextMenuPolicy(Qt.CustomContextMenu)
        self.column_header.customContextMenuRequested.connect(self.show_column_header_context_menu)
        self.column_header.sectionResized.connect(self.column_resized, Qt.QueuedConnection)
        self.row_header = HeaderView(Qt.Vertical, self)
        self.setVerticalHeader(self.row_header)
        # }}}

        self._model.database_changed.connect(self.database_changed)
        hv = self.verticalHeader()
        hv.setClickable(True)
        hv.setCursor(Qt.PointingHandCursor)
        self.selected_ids = []
        self._model.about_to_be_sorted.connect(self.about_to_be_sorted)
        self._model.sorting_done.connect(self.sorting_done,
                type=Qt.QueuedConnection)

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
            h.setSectionHidden(idx, True)
        elif action == 'show':
            h.setSectionHidden(idx, False)
            if h.sectionSize(idx) < 3:
                sz = h.sectionSizeHint(idx)
                h.resizeSection(idx, sz)
        elif action == 'ascending':
            self.sortByColumn(idx, Qt.AscendingOrder)
        elif action == 'descending':
            self.sortByColumn(idx, Qt.DescendingOrder)
        elif action == 'defaults':
            self.apply_state(self.get_default_state())
        elif action == 'addcustcol':
            self.add_column_signal.emit()
        elif action.startswith('align_'):
            alignment = action.partition('_')[-1]
            self._model.change_alignment(column, alignment)
        elif action == 'quickview':
            from calibre.customize.ui import find_plugin
            qv = find_plugin('Show Quickview')
            if qv:
                rows = self.selectionModel().selectedRows()
                if len(rows) > 0:
                    current_row = rows[0].row()
                    current_col = self.column_map.index(column)
                    index = self.model().index(current_row, current_col)
                    qv.actual_plugin_.change_quickview_column(index)

        self.save_state()

    def show_column_header_context_menu(self, pos):
        idx = self.column_header.logicalIndexAt(pos)
        if idx > -1 and idx < len(self.column_map):
            col = self.column_map[idx]
            name = unicode(self.model().headerData(idx, Qt.Horizontal,
                    Qt.DisplayRole).toString())
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
                            Qt.DisplayRole).toString())
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

            self.column_header_context_menu.popup(self.column_header.mapToGlobal(pos))
    # }}}

    # Sorting {{{
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
            if order:
                self.sortByColumn(idx, Qt.AscendingOrder)
            else:
                self.sortByColumn(idx, Qt.DescendingOrder)
        else:
            self._model.sort_by_named_field(field, order, reset)

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
            hdrs = self.horizontalHeader()
            try:
                hdrs.setSortIndicator(col, dir)
            except:
                pass
    # }}}

    # Ondevice column {{{
    def set_ondevice_column_visibility(self):
        m  = self._model
        self.column_header.setSectionHidden(m.column_map.index('ondevice'),
                not m.device_connected)

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
            self.cleanup_sort_history(self.model().sort_history)
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
            db.prefs.set(name + ' books view state', state)

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
            if col == 'date':
                col = 'timestamp'
            if ignore_column_map or col in self.column_map:
                if (not history or history[-1][0] != col):
                    history.append([col, order])
        return history

    def apply_sort_history(self, saved_history, max_sort_levels=3):
        if not saved_history:
            return
        for col, order in reversed(self.cleanup_sort_history(
                saved_history)[:max_sort_levels]):
            self.sortByColumn(self.column_map.index(col),
                              Qt.AscendingOrder if order else Qt.DescendingOrder)

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
                        db.prefs[name] = ans
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
                        db.prefs[name] = ans
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
            self.resizeRowToContents(0)
            self.verticalHeader().setDefaultSectionSize(self.rowHeight(0) +
                                            gprefs['extra_row_spacing'])
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
        self.save_state()
        self._model.set_database(db)
        self.tags_delegate.set_database(db)
        self.cc_names_delegate.set_database(db)
        self.authors_delegate.set_database(db)
        self.series_delegate.set_auto_complete_function(db.all_series)
        self.publisher_delegate.set_auto_complete_function(db.all_publishers)

    def database_changed(self, db):
        for i in range(self.model().columnCount(None)):
            if self.itemDelegateForColumn(i) in (self.rating_delegate,
                    self.timestamp_delegate, self.pubdate_delegate,
                    self.last_modified_delegate, self.languages_delegate):
                self.setItemDelegateForColumn(i, self.itemDelegate())

        cm = self.column_map

        for colhead in cm:
            if self._model.is_custom_column(colhead):
                cc = self._model.custom_columns[colhead]
                if cc['datatype'] == 'datetime':
                    delegate = CcDateDelegate(self)
                    delegate.set_format(cc['display'].get('date_format',''))
                    self.setItemDelegateForColumn(cm.index(colhead), delegate)
                elif cc['datatype'] == 'comments':
                    self.setItemDelegateForColumn(cm.index(colhead), self.cc_comments_delegate)
                elif cc['datatype'] == 'text':
                    if cc['is_multiple']:
                        if cc['display'].get('is_names', False):
                            self.setItemDelegateForColumn(cm.index(colhead),
                                                          self.cc_names_delegate)
                        else:
                            self.setItemDelegateForColumn(cm.index(colhead),
                                                          self.tags_delegate)
                    else:
                        self.setItemDelegateForColumn(cm.index(colhead), self.cc_text_delegate)
                elif cc['datatype'] == 'series':
                    self.setItemDelegateForColumn(cm.index(colhead), self.cc_text_delegate)
                elif cc['datatype'] in ('int', 'float'):
                    self.setItemDelegateForColumn(cm.index(colhead), self.cc_number_delegate)
                elif cc['datatype'] == 'bool':
                    self.setItemDelegateForColumn(cm.index(colhead), self.cc_bool_delegate)
                elif cc['datatype'] == 'rating':
                    self.setItemDelegateForColumn(cm.index(colhead), self.rating_delegate)
                elif cc['datatype'] == 'composite':
                    self.setItemDelegateForColumn(cm.index(colhead), self.cc_template_delegate)
                elif cc['datatype'] == 'enumeration':
                    self.setItemDelegateForColumn(cm.index(colhead), self.cc_enum_delegate)
            else:
                dattr = colhead+'_delegate'
                delegate = colhead if hasattr(self, dattr) else 'text'
                self.setItemDelegateForColumn(cm.index(colhead), getattr(self,
                    delegate+'_delegate'))

        self.restore_state()
        self.set_ondevice_column_visibility()
        #}}}

    # Context Menu {{{
    def set_context_menu(self, menu, edit_collections_action):
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.context_menu = menu
        self.edit_collections_action = edit_collections_action

    def contextMenuEvent(self, event):
        self.context_menu.popup(event.globalPos())
        event.accept()
    # }}}

    # Drag 'n Drop {{{
    @classmethod
    def paths_from_event(cls, event):
        '''
        Accept a drop event and return a list of paths that can be read from
        and represent files with extensions.
        '''
        md = event.mimeData()
        if md.hasFormat('text/uri-list') and not \
                md.hasFormat('application/calibre+from_library'):
            urls = [unicode(u.toLocalFile()) for u in md.urls()]
            return [u for u in urls if os.path.splitext(u)[1] and
                    os.path.exists(u)]

    def drag_icon(self, cover, multiple):
        cover = cover.scaledToHeight(120, Qt.SmoothTransformation)
        if multiple:
            base_width = cover.width()
            base_height = cover.height()
            base = QImage(base_width+21, base_height+21,
                    QImage.Format_ARGB32_Premultiplied)
            base.fill(QColor(255, 255, 255, 0).rgba())
            p = QPainter(base)
            rect = QRect(20, 0, base_width, base_height)
            p.fillRect(rect, QColor('white'))
            p.drawRect(rect)
            rect.moveLeft(10)
            rect.moveTop(10)
            p.fillRect(rect, QColor('white'))
            p.drawRect(rect)
            rect.moveLeft(0)
            rect.moveTop(20)
            p.fillRect(rect, QColor('white'))
            p.save()
            p.setCompositionMode(p.CompositionMode_SourceAtop)
            p.drawImage(rect.topLeft(), cover)
            p.restore()
            p.drawRect(rect)
            p.end()
            cover = base
        return QPixmap.fromImage(cover)

    def drag_data(self):
        m = self.model()
        db = m.db
        rows = self.selectionModel().selectedRows()
        selected = list(map(m.id, rows))
        ids = ' '.join(map(str, selected))
        md = QMimeData()
        md.setData('application/calibre+from_library', ids)
        fmt = prefs['output_format']

        def url_for_id(i):
            try:
                ans = db.format_path(i, fmt, index_is_id=True)
            except:
                ans = None
            if ans is None:
                fmts = db.formats(i, index_is_id=True)
                if fmts:
                    fmts = fmts.split(',')
                else:
                    fmts = []
                for f in fmts:
                    try:
                        ans = db.format_path(i, f, index_is_id=True)
                    except:
                        ans = None
            if ans is None:
                ans = db.abspath(i, index_is_id=True)
            return QUrl.fromLocalFile(ans)

        md.setUrls([url_for_id(i) for i in selected])
        drag = QDrag(self)
        col = self.selectionModel().currentIndex().column()
        md.column_name = self.column_map[col]
        drag.setMimeData(md)
        cover = self.drag_icon(m.cover(self.currentIndex().row()),
                len(selected) > 1)
        drag.setHotSpot(QPoint(-15, -15))
        drag.setPixmap(cover)
        return drag

    def event_has_mods(self, event=None):
        mods = event.modifiers() if event is not None else \
                QApplication.keyboardModifiers()
        return mods & Qt.ControlModifier or mods & Qt.ShiftModifier

    def mousePressEvent(self, event):
        ep = event.pos()
        if self.indexAt(ep) in self.selectionModel().selectedIndexes() and \
                event.button() == Qt.LeftButton and not self.event_has_mods():
            self.drag_start_pos = ep
        return QTableView.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        if not self.drag_allowed:
            return
        if self.drag_start_pos is None:
            return QTableView.mouseMoveEvent(self, event)

        if self.event_has_mods():
            self.drag_start_pos = None
            return

        if not (event.buttons() & Qt.LeftButton) or \
                (event.pos() - self.drag_start_pos).manhattanLength() \
                      < QApplication.startDragDistance():
            return

        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        drag = self.drag_data()
        drag.exec_(Qt.CopyAction)
        self.drag_start_pos = None

    def dragEnterEvent(self, event):
        if int(event.possibleActions() & Qt.CopyAction) + \
           int(event.possibleActions() & Qt.MoveAction) == 0:
            return
        paths = self.paths_from_event(event)

        if paths:
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self.paths_from_event(event)
        event.setDropAction(Qt.CopyAction)
        event.accept()
        self.files_dropped.emit(paths)

    # }}}

    @property
    def column_map(self):
        return self._model.column_map

    def refresh_book_details(self):
        idx = self.currentIndex()
        if idx.isValid():
            self._model.current_changed(idx, idx)

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

    def set_current_row(self, row=0, select=True):
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
            self.setCurrentIndex(index)
            if select:
                sm = self.selectionModel()
                sm.select(index, sm.ClearAndSelect|sm.Rows)

    def keyPressEvent(self, ev):
        val = self.horizontalScrollBar().value()
        ret = super(BooksView, self).keyPressEvent(ev)
        if ev.isAccepted() and ev.key() in (Qt.Key_Home, Qt.Key_End
                                            ) and ev.modifiers() & Qt.ControlModifier:
            self.horizontalScrollBar().setValue(val)
        return ret

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
        self._model.search(txt)
        id_to_select = self._model.get_current_highlighted_id()
        if id_to_select is not None:
            self.select_rows([id_to_select], using_ids=True)
        elif self._model.highlight_only:
            self.clearSelection()
        self.setFocus(Qt.OtherFocusReason)

    def connect_to_search_box(self, sb, search_done):
        sb.search.connect(self.search_proxy)
        self._search_done = search_done
        self._model.searched.connect(self.search_done)

    def connect_to_book_display(self, bd):
        self._model.new_bookdisplay_data.connect(bd)

    def search_done(self, ok):
        self._search_done(self, ok)

    def row_count(self):
        return self._model.count()

# }}}

class DeviceBooksView(BooksView):  # {{{

    def __init__(self, parent):
        BooksView.__init__(self, parent, DeviceBooksModel,
                           use_edit_metadata_dialog=False)
        self._model.resize_rows.connect(self.do_row_sizing,
                                                 type=Qt.QueuedConnection)
        self.can_add_columns = False
        self.columns_resized = False
        self.resize_on_select = False
        self.rating_delegate = None
        for i in range(10):
            self.setItemDelegateForColumn(i, TextDelegate(self))
        self.setDragDropMode(self.NoDragDrop)
        self.setAcceptDrops(False)

    def drag_data(self):
        m = self.model()
        rows = self.selectionModel().selectedRows()
        paths = [force_unicode(p, enc=filesystem_encoding) for p in m.paths(rows) if p]
        md = QMimeData()
        md.setData('application/calibre+from_device', 'dummy')
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

    def resizeColumnsToContents(self):
        QTableView.resizeColumnsToContents(self)
        self.columns_resized = True

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

