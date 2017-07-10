#!/usr/bin/env  python2
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import (
    Qt, QDialog, QAbstractItemView, QTableWidgetItem, QIcon, QListWidgetItem,
    QCoreApplication, QEvent, QObject, QApplication, pyqtSignal, QByteArray)

from calibre.customize.ui import find_plugin
from calibre.gui2 import gprefs
from calibre.gui2.dialogs.quickview_ui import Ui_Quickview
from calibre.utils.icu import sort_key


class TableItem(QTableWidgetItem):

    '''
    A QTableWidgetItem that sorts on a separate string and uses ICU rules
    '''

    def __init__(self, val, sort, idx=0):
        self.sort = sort
        self.sort_idx = idx
        QTableWidgetItem.__init__(self, val)
        self.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)

    def __ge__(self, other):
        l = sort_key(self.sort)
        r = sort_key(other.sort)
        if l > r:
            return 1
        if l == r:
            return self.sort_idx >= other.sort_idx
        return 0

    def __lt__(self, other):
        l = sort_key(self.sort)
        r = sort_key(other.sort)
        if l < r:
            return 1
        if l == r:
            return self.sort_idx < other.sort_idx
        return 0


IN_WIDGET_ITEMS = 0
IN_WIDGET_BOOKS = 1
IN_WIDGET_LOCK = 2
IN_WIDGET_DOCK = 3
IN_WIDGET_SEARCH = 4
IN_WIDGET_CLOSE = 5


class BooksTableFilter(QObject):

    return_pressed_signal = pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Return:
            self.return_pressed_signal.emit()
            return True
        return False


class WidgetFocusFilter(QObject):

    focus_entered_signal = pyqtSignal(object)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn:
            self.focus_entered_signal.emit(obj)
        return False


class WidgetTabFilter(QObject):

    def __init__(self, attach_to_Class, which_widget, tab_signal):
        QObject.__init__(self, attach_to_Class)
        self.tab_signal = tab_signal
        self.which_widget = which_widget

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Tab:
                self.tab_signal.emit(self.which_widget, True)
                return True
            if event.key() == Qt.Key_Backtab:
                self.tab_signal.emit(self.which_widget, False)
                return True
        return False


class Quickview(QDialog, Ui_Quickview):

    reopen_after_dock_change = pyqtSignal()
    tab_pressed_signal       = pyqtSignal(object, object)
    quickview_closed         = pyqtSignal()

    def __init__(self, gui, row):
        self.is_pane = gprefs.get('quickview_is_pane', False)

        if not self.is_pane:
            QDialog.__init__(self, gui, flags=Qt.Widget)
        else:
            QDialog.__init__(self, gui)
        Ui_Quickview.__init__(self)
        self.setupUi(self)
        self.isClosed = False
        self.current_book = None
        self.closed_by_button = False

        if self.is_pane:
            self.main_grid_layout.setContentsMargins(0, 0, 0, 0)

        self.books_table_column_widths = None
        try:
            self.books_table_column_widths = \
                        gprefs.get('quickview_dialog_books_table_widths', None)
            if not self.is_pane:
                geom = gprefs.get('quickview_dialog_geometry', bytearray(''))
                self.restoreGeometry(QByteArray(geom))
        except:
            pass

        if not self.is_pane:
            # Remove the help button from the window title bar
            icon = self.windowIcon()
            self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
            self.setWindowFlags(self.windowFlags()|Qt.WindowStaysOnTopHint)
            self.setWindowIcon(icon)

        self.view = gui.library_view
        self.db = self.view.model().db
        self.gui = gui
        self.is_closed = False
        self.current_book_id = None  # the db id of the book used to fill the lh pane
        self.current_column = None   # current logical column in books list
        self.current_key = None      # current lookup key in books list
        self.last_search = None
        self.no_valid_items = False

        self.fm = self.db.field_metadata

        self.items.setSelectionMode(QAbstractItemView.SingleSelection)
        self.items.currentTextChanged.connect(self.item_selected)
        self.items.setProperty('highlight_current_item', 150)

        focus_filter = WidgetFocusFilter(self.items)
        focus_filter.focus_entered_signal.connect(self.focus_entered)
        self.items.installEventFilter(focus_filter)

        self.tab_pressed_signal.connect(self.tab_pressed)
        return_filter = BooksTableFilter(self.books_table)
        return_filter.return_pressed_signal.connect(self.return_pressed)
        self.books_table.installEventFilter(return_filter)

        focus_filter = WidgetFocusFilter(self.books_table)
        focus_filter.focus_entered_signal.connect(self.focus_entered)
        self.books_table.installEventFilter(focus_filter)

        self.close_button.clicked.connect(self.close_button_clicked)

        self.tab_order_widgets = [self.items, self.books_table, self.lock_qv,
                          self.dock_button, self.search_button, self.close_button]
        for idx,widget in enumerate(self.tab_order_widgets):
            widget.installEventFilter(WidgetTabFilter(widget, idx, self.tab_pressed_signal))

        self.books_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.books_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.books_table.setProperty('highlight_current_item', 150)

        # Set up the books table columns
        self.add_columns_to_widget()

        self.books_table_header_height = self.books_table.height()
        self.books_table.cellDoubleClicked.connect(self.book_doubleclicked)
        self.books_table.currentCellChanged.connect(self.books_table_cell_changed)
        self.books_table.cellClicked.connect(self.books_table_set_search_string)
        self.books_table.cellActivated.connect(self.books_table_set_search_string)
        self.books_table.sortByColumn(0, Qt.AscendingOrder)

        # get the standard table row height. Do this here because calling
        # resizeRowsToContents can word wrap long cell contents, creating
        # double-high rows
        self.books_table.setRowCount(1)
        self.books_table.setItem(0, 0, TableItem('A', ''))
        self.books_table.resizeRowsToContents()
        self.books_table_row_height = self.books_table.rowHeight(0)
        self.books_table.setRowCount(0)

        # Add the data
        self.refresh(row)

        self.view.clicked.connect(self.slave)
        self.view.selectionModel().currentColumnChanged.connect(self.column_slave)
        QCoreApplication.instance().aboutToQuit.connect(self.save_state)
        self.search_button.clicked.connect(self.do_search)
        self.view.model().new_bookdisplay_data.connect(self.book_was_changed)

        self.close_button.setDefault(False)
        self.close_button_tooltip = _('The Quickview shortcut ({0}) shows/hides the Quickview panel')
        self.search_button_tooltip = _('Search in the library view for the currently highlighted selection')
        self.search_button.setToolTip(self.search_button_tooltip)
        if self.is_pane:
            self.dock_button.setText(_('Undock'))
            self.dock_button.setToolTip(_('Pop up the quickview panel into its own floating window'))
            self.dock_button.setIcon(QIcon(I('arrow-up.png')))
            self.lock_qv.setText(_('Lock Quickview contents'))
            self.search_button.setText(_('Search'))
            self.gui.quickview_splitter.add_quickview_dialog(self)
            self.close_button.setVisible(False)
        else:
            self.dock_button.setToolTip(_('Embed the quickview panel into the main calibre window'))
            self.dock_button.setIcon(QIcon(I('arrow-down.png')))
        self.set_focus()

        self.books_table.horizontalHeader().sectionResized.connect(self.section_resized)
        self.dock_button.clicked.connect(self.show_as_pane_changed)
        self.gui.search.cleared.connect(self.indicate_no_items)

    def add_columns_to_widget(self):
        '''
        Get the list of columns from the preferences. Clear the current table
        and add the current column set
        '''
        self.column_order = [x[0] for x in get_qv_field_list(self.fm) if x[1]]
        self.books_table.clear()
        self.books_table.setRowCount(0)
        self.books_table.setColumnCount(len(self.column_order))
        for idx,col in enumerate(self.column_order):
            t = QTableWidgetItem(self.fm[col]['name'])
            self.books_table.setHorizontalHeaderItem(idx, t)

    def refill(self):
        '''
            Refill the table in case the book data changes
        '''
        self.add_columns_to_widget()
        self._refresh(self.current_book_id, self.current_key)

    def set_search_text(self, txt):
        if txt:
            self.search_button.setEnabled(True)
        else:
            self.search_button.setEnabled(False)
        self.last_search = txt

    def set_shortcuts(self, search_sc, qv_sc):
        if self.is_pane:
            self.search_button.setToolTip(self.search_button_tooltip + ' (' + search_sc + ')')
            self.close_button.setToolTip(self.close_button_tooltip.format(qv_sc))

    def focus_entered(self, obj):
        if obj == self.books_table:
            self.books_table_set_search_string(self.books_table.currentRow(),
                                               self.books_table.currentColumn())
        elif obj.currentItem():
            self.item_selected(obj.currentItem().text())

    def books_table_cell_changed(self, cur_row, cur_col, prev_row, prev_col):
        self.books_table_set_search_string(cur_row, cur_col)

    def books_table_set_search_string(self, current_row, current_col):
        '''
        Given the contents of a cell, compute a search string that will find
        that book and any others with identical contents in the cell.
        '''
        current = self.books_table.item(current_row, current_col)
        if current is None:
            return
        book_id = current.data(Qt.UserRole)

        if current is None:
            return
        col = self.column_order[current.column()]
        if col == 'title':
            self.set_search_text('title:="' + current.text().replace('"', '\\"') + '"')
        elif col == 'authors':
            authors = []
            for aut in [t.strip() for t in current.text().split('&')]:
                authors.append('authors:="' + aut.replace('"', '\\"') + '"')
            self.set_search_text(' and '.join(authors))
        elif self.fm[col]['datatype'] == 'series':
            mi = self.db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
            t = mi.get(col)
            if t:
                self.set_search_text(col+ ':="' + t + '"')
            else:
                self.set_search_text(None)
        else:
            if self.fm[col]['is_multiple']:
                items = [(col + ':"=' + v.strip() + '"') for v in
                         current.text().split(self.fm[col]['is_multiple']['ui_to_list'])]
                self.set_search_text(' and '.join(items))
            else:
                self.set_search_text(col + ':"=' + current.text() + '"')

    def tab_pressed(self, in_widget, isForward):
        if isForward:
            in_widget += 1
            if in_widget >= len(self.tab_order_widgets):
                in_widget = 0
        else:
            in_widget -= 1
            if in_widget < 0:
                in_widget = len(self.tab_order_widgets) - 1
        self.tab_order_widgets[in_widget].setFocus(Qt.TabFocusReason)

    def show(self):
        QDialog.show(self)
        if self.is_pane:
            self.gui.quickview_splitter.show_quickview_widget()

    def show_as_pane_changed(self):
        gprefs['quickview_is_pane'] = not gprefs.get('quickview_is_pane', False)
        self.reopen_after_dock_change.emit()

    # search button
    def do_search(self):
        if self.no_valid_items:
            return
        if self.last_search is not None:
            self.gui.search.set_search_string(self.last_search)

    def book_was_changed(self, mi):
        '''
        Called when book information is changed in the library view. Make that
        book info current. This means that prev and next in edit metadata will move
        the current book and change quickview
        '''
        if self.is_closed or self.current_column is None:
            return
        # There is an ordering problem when libraries are changed. The library
        # view is changed, triggering a book_was_changed signal. Unfortunately
        # this happens before the library_changed actions are run, meaning we
        # still have the old database. To avoid the problem we just ignore the
        # operation if we get an exception. The "close" will come
        # eventually.
        try:
            self._refresh(mi.get('id'), self.current_key)
        except:
            pass

    # clicks on the items listWidget
    def item_selected(self, txt):
        if self.no_valid_items:
            return
        self.fill_in_books_box(unicode(txt))
        self.set_search_text(self.current_key + ':"=' + txt.replace('"', '\\"') + '"')

    def refresh(self, idx):
        '''
        Given a cell in the library view, display the information. This method
        converts the index into the lookup ken
        '''
        if self.lock_qv.isChecked():
            return

        try:
            bv_row = idx.row()
            self.current_column = idx.column()
            key = self.view.column_map[self.current_column]
            book_id = self.view.model().id(bv_row)
            if self.current_book_id == book_id and self.current_key == key:
                return
            self._refresh(book_id, key)
        except:
            self.indicate_no_items()

    def _refresh(self, book_id, key):
        '''
        Actually fill in the left-hand pane from the information in the
        selected column of the selected book
        '''
        # Only show items for categories
        if key is None or not self.fm[key]['is_category']:
            if self.current_key is None:
                self.indicate_no_items()
                return
            key = self.current_key
        label_text = _('&Item: {0} ({1})')
        if self.is_pane:
            label_text = label_text.replace('&', '')
        self.items_label.setText(label_text.format(self.fm[key]['name'], key))

        self.items.blockSignals(True)
        self.items.clear()
        self.books_table.setRowCount(0)

        mi = self.db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
        vals = mi.get(key, None)

        if vals:
            self.no_valid_items = False
            if self.fm[key]['datatype'] == 'rating':
                if self.fm[key]['display'].get('allow_half_stars', False):
                    vals = unicode(vals/2.0)
                else:
                    vals = unicode(vals/2)
            if not isinstance(vals, list):
                vals = [vals]
            vals.sort(key=sort_key)

            for v in vals:
                a = QListWidgetItem(v)
                self.items.addItem(a)
            self.items.setCurrentRow(0)

            self.current_book_id = book_id
            self.current_key = key

            self.fill_in_books_box(vals[0])
        else:
            self.indicate_no_items()

        self.items.blockSignals(False)

    def indicate_no_items(self):
        self.no_valid_items = True
        self.items.clear()
        self.add_columns_to_widget()
        self.items.addItem(QListWidgetItem(_('**No items found**')))
        self.books_label.setText(_('Click in a column  in the library view '
                                   'to see the information for that book'))

    def fill_in_books_box(self, selected_item):
        '''
        Given the selected row in the left-hand box, fill in the grid with
        the books that contain that data.
        '''
        # Do a bit of fix-up on the items so that the search works.
        if selected_item.startswith('.'):
            sv = '.' + selected_item
        else:
            sv = selected_item
        sv = self.current_key + ':"=' + sv.replace('"', r'\"') + '"'
        if gprefs['qv_respects_vls']:
            books = self.db.search(sv, return_matches=True, sort_results=False)
        else:
            books = self.db.new_api.search(sv)

        self.books_table.setRowCount(len(books))
        label_text = _('&Books with selected item "{0}": {1}')
        if self.is_pane:
            label_text = label_text.replace('&', '')
        self.books_label.setText(label_text.format(selected_item, len(books)))

        select_item = None
        self.books_table.setSortingEnabled(False)
        self.books_table.blockSignals(True)
        tt = ('<p>' +
            _('Double-click on a book to change the selection in the library view or '
              'change the column shown in the left-hand pane. '
              'Shift- or control-double-click to edit the metadata of a book, '
              'which also changes the selected book.'
              ) + '</p>')
        for row, b in enumerate(books):
            mi = self.db.get_metadata(b, index_is_id=True, get_user_categories=False)
            for col in self.column_order:
                if col == 'title':
                    a = TableItem(mi.title, mi.title_sort)
                    if b == self.current_book_id:
                        select_item = a
                elif col == 'authors':
                    a = TableItem(' & '.join(mi.authors), mi.author_sort)
                elif col == 'series':
                    series = mi.format_field('series')[1]
                    if series is None:
                        series = ''
                    a = TableItem(series, mi.series, mi.series_index)
                elif self.fm[col]['datatype'] == 'series':
                    v = mi.format_field(col)[1]
                    a = TableItem(v, mi.get(col), mi.get(col+'_index'))
                else:
                    v = mi.format_field(col)[1]
                    a = TableItem(v, v)
                a.setData(Qt.UserRole, b)
                a.setToolTip(tt)
                self.books_table.setItem(row, self.key_to_table_widget_column(col), a)
                self.books_table.setRowHeight(row, self.books_table_row_height)

        self.books_table.blockSignals(False)
        self.books_table.setSortingEnabled(True)
        if select_item is not None:
            self.books_table.setCurrentItem(select_item)
            self.books_table.scrollToItem(select_item, QAbstractItemView.PositionAtCenter)
        self.set_search_text(sv)

    # Deal with sizing the table columns. Done here because the numbers are not
    # correct until the first paint.
    def resizeEvent(self, *args):
        QDialog.resizeEvent(self, *args)

        # Do this if we are resizing for the first time to reset state.
        if self.is_pane and self.height() == 0:
            self.gui.quickview_splitter.set_sizes()

        if self.books_table_column_widths is not None:
            for c,w in enumerate(self.books_table_column_widths):
                self.books_table.setColumnWidth(c, w)
        else:
            # the vertical scroll bar might not be rendered, so might not yet
            # have a width. Assume 25. Not a problem because user-changed column
            # widths will be remembered
            w = self.books_table.width() - 25 - self.books_table.verticalHeader().width()
            w /= self.books_table.columnCount()
            for c in range(0, self.books_table.columnCount()):
                self.books_table.setColumnWidth(c, w)
        self.save_state()

    def key_to_table_widget_column(self, key):
        return self.column_order.index(key)

    def return_pressed(self):
        row = self.books_table.currentRow()
        if gprefs['qv_retkey_changes_column']:
            self.select_book(row, self.books_table.currentColumn())
        else:
            self.select_book(row, self.key_to_table_widget_column(self.current_key))

    def book_doubleclicked(self, row, column):
        if self.no_valid_items:
            return
        if gprefs['qv_dclick_changes_column']:
            self.select_book(row, column)
        else:
            self.select_book(row, self.key_to_table_widget_column(self.current_key))

    def select_book(self, row, column):
        '''
        row and column both refer the qv table. In particular, column is not
        the logical column in the book list.
        '''
        item = self.books_table.item(row, column)
        if item is None:
            return
        book_id = int(self.books_table.item(row, column).data(Qt.UserRole))
        key = self.column_order[column]
        modifiers = int(QApplication.keyboardModifiers())
        if modifiers in (Qt.CTRL, Qt.SHIFT):
            self.view.select_rows([book_id])
            em = find_plugin('Edit Metadata')
            if em and em.actual_plugin_:
                em.actual_plugin_.edit_metadata(None)
        else:
            self.view.select_cell(self.db.data.id_to_index(book_id),
                                  self.view.column_map.index(key))

    def set_focus(self):
        self.activateWindow()
        self.books_table.setFocus()

    def column_slave(self, current):
        '''
        called when the column is changed on the booklist
        '''
        if gprefs['qv_follows_column']:
            self.slave(current)

    def slave(self, current):
        '''
        called when a book is clicked on the library view
        '''
        if self.is_closed:
            return
        self.refresh(current)
        self.view.activateWindow()

    def section_resized(self, logicalIndex, oldSize, newSize):
        self.save_state()

    def save_state(self):
        if self.is_closed:
            return
        self.books_table_column_widths = []
        for c in range(0, self.books_table.columnCount()):
            self.books_table_column_widths.append(self.books_table.columnWidth(c))
        gprefs['quickview_dialog_books_table_widths'] = self.books_table_column_widths
        if not self.is_pane:
            gprefs['quickview_dialog_geometry'] = bytearray(self.saveGeometry())

    def _close(self):
        self.save_state()
        # clean up to prevent memory leaks
        self.db = self.view = self.gui = None
        self.is_closed = True

    def close_button_clicked(self):
        self.closed_by_button = True
        self.quickview_closed.emit()

    def reject(self):
        if not self.closed_by_button:
            self.close_button_clicked()
        else:
            self._reject()

    def _reject(self):
        if self.is_pane:
            self.gui.quickview_splitter.hide_quickview_widget()
        self.gui.library_view.setFocus(Qt.ActiveWindowFocusReason)
        self._close()
        QDialog.reject(self)


def get_qv_field_list(fm, use_defaults=False):
    from calibre.gui2.ui import get_gui
    db = get_gui().current_db
    if use_defaults:
        src = db.prefs.defaults
    else:
        src = db.prefs
    fieldlist = list(src['qv_display_fields'])
    names = frozenset([x[0] for x in fieldlist])
    for field in fm.displayable_field_keys():
        if (field != 'comments' and fm[field]['datatype'] != 'comments' and field not in names):
            fieldlist.append((field, False))
    available = frozenset(fm.displayable_field_keys())
    return [(f, d) for f, d in fieldlist if f in available]
