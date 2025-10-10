#!/usr/bin/env python
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QAbstractItemDelegate, QModelIndex, QSplitter, Qt, QTableView

from calibre.gui2 import gprefs
from calibre.gui2.library import DEFAULT_SORT
from calibre.gui2.library.delegates import (
    CcBoolDelegate,
    CcCommentsDelegate,
    CcDateDelegate,
    CcEnumDelegate,
    CcLongTextDelegate,
    CcMarkdownDelegate,
    CcNumberDelegate,
    CcSeriesDelegate,
    CcTemplateDelegate,
    CcTextDelegate,
    CompleteDelegate,
    DateDelegate,
    LanguagesDelegate,
    PubDateDelegate,
    RatingDelegate,
    SeriesDelegate,
    TextDelegate,
)


class TableView(QTableView):

    def closeEditor(self, editor, hint):
        # We want to implement our own go to next/previous cell behavior
        delta = 0
        if hint is QAbstractItemDelegate.EndEditHint.EditNextItem:
            delta = 1
        elif hint is QAbstractItemDelegate.EndEditHint.EditPreviousItem:
            delta = -1
        super().closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint if delta else hint)
        if not delta:
            return
        current = self.currentIndex()
        hdr = self.horizontalHeader()
        m = self.model()
        row = current.row()
        vdx = hdr.visualIndex(current.column())  # must work with visual indices, not logical indices
        if vdx < 0:
            return
        num_columns = hdr.count()
        idx = QModelIndex()
        while True:
            vdx = vdx + delta
            if vdx < 0:
                if row <= 0:
                    return
                row -= 1
                vdx += num_columns
            if vdx >= num_columns:
                if row >= m.rowCount(QModelIndex()) - 1:
                    return
                row += 1
                vdx -= num_columns
            if vdx < 0 or vdx >= num_columns:
                return
            ldx = hdr.logicalIndex(vdx)  # We need the logical index for the model
            if hdr.isSectionHidden(ldx):
                continue
            colname = self.column_map[ldx]
            idx = m.index(row, ldx, current.parent())
            if not idx.isValid():
                continue
            if m.is_custom_column(colname):
                if self.itemDelegateForIndex(idx).is_editable_with_tab:
                    # Don't try to open editors implemented by dialogs such as
                    # markdown, composites and comments
                    break
            elif m.flags(idx) & Qt.ItemFlag.ItemIsEditable:
                break

        if idx.isValid():
            # Tell the delegate to ignore keyboard modifiers in case
            # Shift-Tab is being used to move the cell.
            if (d := self.itemDelegateForIndex(idx)) is not None:
                d.ignore_kb_mods_on_edit = True
            self.setCurrentIndex(idx)
            self.edit(idx)

    def create_delegates(self):
        self.rating_delegate = RatingDelegate(self)
        self.half_rating_delegate = RatingDelegate(self, is_half_star=True)
        self.timestamp_delegate = DateDelegate(self)
        self.pubdate_delegate = PubDateDelegate(self)
        self.last_modified_delegate = DateDelegate(self, tweak_name='gui_last_modified_display_format')
        self.languages_delegate = LanguagesDelegate(self)
        self.tags_delegate = CompleteDelegate(self, ',', 'all_tag_names')
        self.authors_delegate = CompleteDelegate(self, '&', 'all_author_names', True)
        self.cc_names_delegate = CompleteDelegate(self, '&', 'all_custom', True)
        self.series_delegate = SeriesDelegate(self)
        self.publisher_delegate = TextDelegate(self)
        self.publisher_delegate.auto_complete_function_name = 'all_publishers'
        self.text_delegate = TextDelegate(self)
        self.cc_text_delegate = CcTextDelegate(self)
        self.cc_series_delegate = CcSeriesDelegate(self)
        self.cc_longtext_delegate = CcLongTextDelegate(self)
        self.cc_markdown_delegate = CcMarkdownDelegate(self)
        self.cc_enum_delegate = CcEnumDelegate(self)
        self.cc_bool_delegate = CcBoolDelegate(self)
        self.cc_comments_delegate = CcCommentsDelegate(self)
        self.cc_template_delegate = CcTemplateDelegate(self)
        self.cc_number_delegate = CcNumberDelegate(self)

    def set_delegates(self):
        cm = self.column_map

        def set_item_delegate(colhead, delegate):
            idx = self.column_map.index(colhead)
            self.setItemDelegateForColumn(idx, delegate)

        for colhead in cm:
            if self.model().is_custom_column(colhead):
                cc = self.model().custom_columns[colhead]
                if cc['datatype'] == 'datetime':
                    delegate = CcDateDelegate(self)
                    delegate.set_format(cc['display'].get('date_format',''))
                    set_item_delegate(colhead, delegate)
                elif cc['datatype'] == 'comments':
                    ctype = cc['display'].get('interpret_as', 'html')
                    if ctype == 'short-text':
                        set_item_delegate(colhead, self.cc_text_delegate)
                    elif ctype == 'long-text':
                        set_item_delegate(colhead, self.cc_longtext_delegate)
                    elif ctype == 'markdown':
                        set_item_delegate(colhead, self.cc_markdown_delegate)
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

    def refresh_composite_edit(self):
        self.cc_template_delegate.refresh()

    def allow_one_edit_for_f2(self):
        key = self.column_map[self.currentIndex().column()]
        db = self.model().db
        if hasattr(db, 'field_metadata') and db.field_metadata[key]['datatype'] == 'composite':
            self.cc_template_delegate.allow_one_edit()

    def keyPressEvent(self, ev):
        from calibre.gui2.library.alternate_views import handle_enter_press
        if handle_enter_press(self, ev):
            return
        if ev.key() == Qt.Key.Key_F2:
            self.allow_one_edit_for_f2()
        return super().keyPressEvent(ev)


class PinTableView(TableView):

    disable_save_state = False

    def __init__(self, books_view, parent=None):
        QTableView.__init__(self, parent)
        self.books_view = books_view
        self.verticalHeader().close()
        self.splitter = None

    @property
    def column_map(self):
        return self.books_view.column_map

    def set_context_menu(self, menu):
        self.context_menu = menu

    def contextMenuEvent(self, event):
        self.books_view.show_context_menu(self.context_menu, event)

    def get_default_state(self):
        old_state = {
            'hidden_columns': ['last_modified', 'languages'],
            'sort_history':[DEFAULT_SORT],
            'column_positions': {},
            'column_sizes': {},
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

    def apply_state(self, state):
        self.disable_save_state = True  # moveSection() can cause save_state() to be called
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
        for i in range(h.count()):
            val = h.isSectionHidden(i)
            h.setSectionHidden(i, not val)
            h.setSectionHidden(i, val)

        sizes = state.get('column_sizes', {})
        for col, size in sizes.items():
            if col in cmap:
                sz = size
                if sz < 3:
                    sz = h.sectionSizeHint(cmap[col])
                h.resizeSection(cmap[col], sz)

        for i in range(h.count()):
            if not h.isSectionHidden(i) and h.sectionSize(i) < 3:
                sz = h.sectionSizeHint(i)
                h.resizeSection(i, sz)
        self.disable_save_state = False

    def get_state(self):
        h = self.column_header
        cm = self.column_map
        state = {}
        state['hidden_columns'] = [cm[i] for i in range(h.count())
                if h.isSectionHidden(i) and cm[i] != 'ondevice']
        state['column_positions'] = {}
        state['column_sizes'] = {}
        for i in range(h.count()):
            name = cm[i]
            state['column_positions'][name] = h.visualIndex(i)
            if name != 'ondevice':
                state['column_sizes'][name] = h.sectionSize(i)
        return state

    def save_state(self):
        db = getattr(self.model(), 'db', None)
        if db is not None and not self.disable_save_state:
            state = self.get_state()
            db.new_api.set_pref('books view split pane state', state)
            if self.splitter is not None:
                self.splitter.save_state()

    def restore_state(self):
        db = getattr(self.model(), 'db', None)
        if db is not None:
            state = db.new_api.pref('books view split pane state', None)
            if self.splitter is not None:
                self.splitter.restore_state()
            if state:
                self.apply_state(state)


class PinContainer(QSplitter):

    def __init__(self, books_view, parent=None):
        super().__init__(parent)
        self.setChildrenCollapsible(False)
        self.books_view = books_view
        self.addWidget(books_view)
        self.addWidget(books_view.pin_view)
        books_view.pin_view.splitter = self

    @property
    def splitter_state(self):
        return bytearray(self.saveState())

    @splitter_state.setter
    def splitter_state(self, val):
        if val is not None:
            self.restoreState(val)

    def save_state(self):
        gprefs['book_list_pin_splitter_state'] = self.splitter_state

    def restore_state(self):
        val = gprefs.get('book_list_pin_splitter_state', None)
        self.splitter_state = val
