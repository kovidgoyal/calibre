#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'


import traceback
from functools import partial

from PyQt5.Qt import (
    Qt, QDialog, QAbstractItemView, QTableWidgetItem, QIcon, QListWidgetItem,
    QCoreApplication, QEvent, QObject, QApplication, pyqtSignal, QByteArray, QMenu,
    QShortcut)

from calibre.customize.ui import find_plugin
from calibre.gui2 import gprefs
from calibre.gui2.dialogs.quickview_ui import Ui_Quickview
from calibre.utils.date import timestampfromdt
from calibre.utils.icu import sort_key
from calibre.utils.iso8601 import UNDEFINED_DATE
from polyglot.builtins import unicode_type


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
        if self.sort is None:
            if other.sort is None:
                # None == None therefore >=
                return True
            # self is None, other is not None therefore self < other
            return False
        if other.sort is None:
            # self is not None and other is None therefore self >= other
            return True

        if isinstance(self.sort, (bytes, unicode_type)):
            l = sort_key(self.sort)
            r = sort_key(other.sort)
        else:
            l = self.sort
            r = other.sort
        if l > r:
            return 1
        if l == r:
            return self.sort_idx >= other.sort_idx
        return 0

    def __lt__(self, other):
        if self.sort is None:
            if other.sort is None:
                # None == None therefore not <
                return False
            # self is None, other is not None therefore self < other
            return True
        if other.sort is None:
            # self is not None therefore self > other
            return False

        if isinstance(self.sort, (bytes, unicode_type)):
            l = sort_key(self.sort)
            r = sort_key(other.sort)
        else:
            l = self.sort
            r = other.sort
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

    def __init__(self, gui, row, toggle_shortcut):
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
        else:
            self.setWindowIcon(self.windowIcon())

        self.books_table_column_widths = None
        try:
            self.books_table_column_widths = \
                        gprefs.get('quickview_dialog_books_table_widths', None)
            if not self.is_pane:
                geom = gprefs.get('quickview_dialog_geometry', None)
                if geom:
                    QApplication.instance().safe_restore_geometry(self, QByteArray(geom))
        except:
            pass

        self.view = gui.library_view
        self.db = self.view.model().db
        self.gui = gui
        self.is_closed = False
        self.current_book_id = None  # the db id of the book used to fill the lh pane
        self.current_column = None   # current logical column in books list
        self.current_key = None      # current lookup key in books list
        self.last_search = None
        self.no_valid_items = False
        self.follow_library_view = True

        self.apply_vls.setCheckState(Qt.Checked if gprefs['qv_respects_vls']
                                        else Qt.Unchecked)
        self.apply_vls.stateChanged.connect(self.vl_box_changed)

        self.fm = self.db.field_metadata

        self.items.setSelectionMode(QAbstractItemView.SingleSelection)
        self.items.currentTextChanged.connect(self.item_selected)
        self.items.setProperty('highlight_current_item', 150)
        self.items.itemDoubleClicked.connect(self.item_doubleclicked)
        self.items.setContextMenuPolicy(Qt.CustomContextMenu)
        self.items.customContextMenuRequested.connect(self.show_item_context_menu)

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
        self.refresh_button.clicked.connect(self.refill)

        self.tab_order_widgets = [self.items, self.books_table, self.lock_qv,
                          self.dock_button, self.refresh_button,
                          self.close_button]
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
        self.view.model().new_bookdisplay_data.connect(self.book_was_changed)

        self.close_button.setDefault(False)
        self.close_button_tooltip = _('The Quickview shortcut ({0}) shows/hides the Quickview panel')
        if self.is_pane:
            self.dock_button.setText(_('Undock'))
            self.dock_button.setToolTip(_('Show the Quickview panel in its own floating window'))
            self.dock_button.setIcon(QIcon(I('arrow-up.png')))
            # Remove the ampersands from the buttons because shortcuts exist.
            self.lock_qv.setText(_('Lock Quickview contents'))
            self.refresh_button.setText(_('Refresh'))
            self.gui.quickview_splitter.add_quickview_dialog(self)
            self.close_button.setVisible(False)
        else:
            self.dock_button.setToolTip(_('Embed the quickview panel into the main calibre window'))
            self.dock_button.setIcon(QIcon(I('arrow-down.png')))
        self.set_focus()

        self.books_table.horizontalHeader().sectionResized.connect(self.section_resized)
        self.dock_button.clicked.connect(self.show_as_pane_changed)
        self.view.model().search_done.connect(self.check_for_no_items)

        # Enable the refresh button only when QV is locked
        self.refresh_button.setEnabled(False)
        self.lock_qv.stateChanged.connect(self.lock_qv_changed)

        self.view_icon = QIcon(I('view.png'))
        self.view_plugin = self.gui.iactions['View']
        self.edit_metadata_icon = QIcon(I('edit_input.png'))
        self.quickview_icon = QIcon(I('quickview.png'))
        self.select_book_icon = QIcon(I('library.png'))
        self.search_icon = QIcon(I('search.png'))
        self.books_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.books_table.customContextMenuRequested.connect(self.show_context_menu)

        # Add the quickview toggle as a shortcut for the close button
        # Don't add it if it identical to the current &X shortcut because that
        # breaks &X
        if (not self.is_pane and toggle_shortcut and
                             self.close_button.shortcut() != toggle_shortcut):
            toggle_sc = QShortcut(toggle_shortcut, self.close_button)
            toggle_sc.activated.connect(lambda: self.close_button_clicked())
            toggle_sc.setEnabled(True)
            self.close_button.setToolTip(_('Alternate shortcut: ') +
                                         toggle_shortcut.toString())

    def item_doubleclicked(self, item):
        tb = self.gui.stack.tb_widget
        tb.set_focus_to_find_box()
        tb.item_search.lineEdit().setText(self.current_key + ':=' + item.text())
        tb.do_find()

    def show_item_context_menu(self, point):
        item = self.items.currentItem()
        self.context_menu = QMenu(self)
        self.context_menu.addAction(self.search_icon, _('Search for item in the Tag browser'),
                                partial(self.item_doubleclicked, item))
        self.context_menu.addAction(self.search_icon, _('Search for item in the library'),
                                partial(self.do_search, follow_library_view=False))
        self.context_menu.popup(self.items.mapToGlobal(point))
        self.context_menu = QMenu(self)

    def show_context_menu(self, point):
        index = self.books_table.indexAt(point)
        row = index.row()
        column = index.column()
        item = self.books_table.item(index.row(), 0)
        if item is None:
            return False
        book_id = int(item.data(Qt.UserRole))
        book_displayed = self.book_displayed_in_library_view(book_id)
        m = self.context_menu = QMenu(self)
        a = m.addAction(self.select_book_icon, _('Select this book in the library'),
                                partial(self.select_book, book_id))
        a.setEnabled(book_displayed)
        m.addAction(self.search_icon, _('Search for item in the library'),
                        partial(self.do_search, follow_library_view=False))
        a = m.addAction(self.edit_metadata_icon, _('Edit book metadata'),
                        partial(self.edit_metadata, book_id, follow_library_view=False))
        a.setEnabled(book_displayed)
        a = m.addAction(self.quickview_icon, _('Quickview this cell'),
                        partial(self.quickview_item, row, column))
        a.setEnabled(self.is_category(self.column_order[column]) and
                     book_displayed and not self.lock_qv.isChecked())
        m.addSeparator()
        m.addAction(self.view_icon, _('Open book in the E-book viewer'),
                        partial(self.view_plugin._view_calibre_books, [book_id]))
        self.context_menu.popup(self.books_table.mapToGlobal(point))
        return True

    def lock_qv_changed(self, state):
        self.refresh_button.setEnabled(state)

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
            Refill the table in case the columns displayed changes
        '''
        self.add_columns_to_widget()
        self.refresh(self.view.currentIndex(), ignore_lock=True)

    def set_search_text(self, txt):
        self.last_search = txt

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
    def do_search(self, follow_library_view=True):
        if self.no_valid_items:
            return
        if self.last_search is not None:
            try:
                self.follow_library_view = follow_library_view
                self.gui.search.set_search_string(self.last_search)
            finally:
                self.follow_library_view = True

    def book_was_changed(self, mi):
        '''
        Called when book information is changed in the library view. Make that
        book info current. This means that prev and next in edit metadata will move
        the current book and change quickview
        '''
        if self.is_closed or self.current_column is None or not self.follow_library_view:
            return
        # There is an ordering problem when libraries are changed. The library
        # view is changed, triggering a book_was_changed signal. Unfortunately
        # this happens before the library_changed actions are run, meaning we
        # still have the old database. To avoid the problem we just ignore the
        # operation if we get an exception. The "close" will come
        # eventually.
        try:
            self.refresh(self.view.model().index(self.db.row(mi.id), self.current_column))
        except:
            pass

    # clicks on the items listWidget
    def item_selected(self, txt):
        if self.no_valid_items:
            return
        self.fill_in_books_box(unicode_type(txt))
        self.set_search_text(self.current_key + ':"=' + txt.replace('"', '\\"') + '"')

    def vl_box_changed(self):
        gprefs['qv_respects_vls'] = self.apply_vls.isChecked()
        self._refresh(self.current_book_id, self.current_key)

    def refresh(self, idx, ignore_lock=False):
        '''
        Given a cell in the library view, display the information. This method
        converts the index into the lookup key
        '''
        if (not ignore_lock and self.lock_qv.isChecked()):
            return
        if not idx.isValid():
            from calibre.constants import DEBUG
            if DEBUG:
                from calibre import prints
                prints('QuickView: current index is not valid')
            return

        try:
            self.current_column = (
                self.view.column_map.index('authors') if (
                    self.current_column is None and self.view.column_map[idx.column()] == 'title'
                ) else idx.column())
            key = self.view.column_map[self.current_column]
            book_id = self.view.model().id(idx.row())
            if self.current_book_id == book_id and self.current_key == key:
                return
            self._refresh(book_id, key)
        except:
            traceback.print_exc()
            self.indicate_no_items()

    def is_category(self, key):
        return key is not None and self.fm[key]['is_category']

    def _refresh(self, book_id, key):
        '''
        Actually fill in the left-hand panel from the information in the
        selected column of the selected book
        '''
        # Only show items for categories
        if not self.is_category(key):
            if self.current_key is None:
                self.indicate_no_items()
                return
            key = self.current_key
        label_text = _('&Item: {0} ({1})')
        if self.is_pane:
            label_text = label_text.replace('&', '')

        self.items.blockSignals(True)
        self.items.clear()
        self.books_table.setRowCount(0)

        mi = self.db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
        vals = mi.get(key, None)

        try:
            # Check if we are in the GridView and there are no values for the
            # selected column. In this case switch the column to 'authors'
            # because there isn't an easy way to switch columns in GridView
            # when the QV box is empty.
            if not vals:
                is_grid_view = (self.gui.current_view().alternate_views.current_view !=
                                self.gui.current_view().alternate_views.main_view)
                if is_grid_view:
                    key = 'authors'
                    vals = mi.get(key, None)
        except:
            traceback.print_exc()

        self.current_book_id = book_id
        self.current_key = key
        self.items_label.setText(label_text.format(self.fm[key]['name'], key))

        if vals:
            self.no_valid_items = False
            if self.fm[key]['datatype'] == 'rating':
                if self.fm[key]['display'].get('allow_half_stars', False):
                    vals = unicode_type(vals/2.0)
                else:
                    vals = unicode_type(vals//2)
            if not isinstance(vals, list):
                vals = [vals]
            vals.sort(key=sort_key)

            for v in vals:
                a = QListWidgetItem(v)
                a.setToolTip(
                    '<p>' + _(
                        'Click to show only books with this item. '
                        'Double click to search for this item in the Tag browser') + '</p>')
                self.items.addItem(a)
            self.items.setCurrentRow(0)

            self.fill_in_books_box(vals[0])
        else:
            self.indicate_no_items()
        self.items.blockSignals(False)

    def check_for_no_items(self):
        if not self.is_closed and self.view.model().count() == 0:
            self.indicate_no_items()

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
        if self.apply_vls.isChecked():
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
        tt = ('<p>' + _(
              'Double click on a book to change the selection in the library view or '
              'change the column shown in the left-hand panel. '
              'Shift- or Ctrl- double click to edit the metadata of a book, '
              'which also changes the selected book.'
              ) + '</p>')
        for row, b in enumerate(books):
            mi = self.db.new_api.get_proxy_metadata(b)
            for col in self.column_order:
                try:
                    if col == 'title':
                        a = TableItem(mi.title, mi.title_sort)
                        if b == self.current_book_id:
                            select_item = a
                    elif col == 'authors':
                        a = TableItem(' & '.join(mi.authors), mi.author_sort)
                    elif col == 'series':
                        series = mi.format_field('series')[1]
                        if series is None:
                            a = TableItem('', '', 0)
                        else:
                            a = TableItem(series, mi.series, mi.series_index)
                    elif col == 'size':
                        v = mi.get('book_size')
                        if v is not None:
                            a = TableItem('{:n}'.format(v), v)
                            a.setTextAlignment(Qt.AlignRight)
                        else:
                            a = TableItem(' ', None)
                    elif self.fm[col]['datatype'] == 'series':
                        v = mi.format_field(col)[1]
                        a = TableItem(v, mi.get(col), mi.get(col+'_index'))
                    elif self.fm[col]['datatype'] == 'datetime':
                        v = mi.format_field(col)[1]
                        d = mi.get(col)
                        if d is None:
                            d = UNDEFINED_DATE
                        a = TableItem(v, timestampfromdt(d))
                    elif self.fm[col]['datatype'] in ('float', 'int'):
                        v = mi.format_field(col)[1]
                        sort_val = mi.get(col)
                        a = TableItem(v, sort_val)
                    else:
                        v = mi.format_field(col)[1]
                        a = TableItem(v, v)
                except:
                    traceback.print_exc()
                    a = TableItem(_('Something went wrong while filling in the table'), '')
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
            w //= self.books_table.columnCount()
            for c in range(0, self.books_table.columnCount()):
                self.books_table.setColumnWidth(c, w)
        self.save_state()

    def key_to_table_widget_column(self, key):
        return self.column_order.index(key)

    def return_pressed(self):
        row = self.books_table.currentRow()
        if gprefs['qv_retkey_changes_column']:
            self.select_book_and_qv(row, self.books_table.currentColumn())
        else:
            self.select_book_and_qv(row, self.key_to_table_widget_column(self.current_key))

    def book_not_in_view_error(self):
        from calibre.gui2 import error_dialog
        error_dialog(self, _('Quickview: Book not in library view'),
                     _('The book you selected is not currently displayed in '
                       'the library view, perhaps because of a search or a '
                       'Virtual library, so Quickview cannot select it.'),
                     show=True,
                     show_copy_button=False)

    def book_displayed_in_library_view(self, book_id):
        try:
            self.db.data.index(book_id)
            return True
        except:
            return False

    def quickview_item(self, row, column):
        self.select_book_and_qv(row, column)

    def book_doubleclicked(self, row, column):
        if self.no_valid_items:
            return
        try:
            if gprefs['qv_dclick_changes_column']:
                self.quickview_item(row, column)
            else:
                self.quickview_item(row, self.key_to_table_widget_column(self.current_key))
        except:
            self.book_not_in_view_error()

    def edit_metadata(self, book_id, follow_library_view=True):
        try:
            self.follow_library_view = follow_library_view
            self.view.select_rows([book_id])
            em = find_plugin('Edit Metadata')
            if em and em.actual_plugin_:
                em.actual_plugin_.edit_metadata(None)
        finally:
            self.follow_library_view = True

    def select_book(self, book_id):
        '''
        Select a book in the library view without changing the QV lists
        '''
        try:
            self.follow_library_view = False
            self.view.select_cell(self.db.data.id_to_index(book_id),
                                  self.current_column)
        finally:
            self.follow_library_view = True

    def select_book_and_qv(self, row, column):
        '''
        row and column both refer the qv table. In particular, column is not
        the logical column in the book list.
        '''
        item = self.books_table.item(row, column)
        if item is None:
            return
        book_id = int(self.books_table.item(row, column).data(Qt.UserRole))
        if not self.book_displayed_in_library_view(book_id):
            self.book_not_in_view_error()
            return
        key = self.column_order[column]
        modifiers = int(QApplication.keyboardModifiers())
        if modifiers in (Qt.CTRL, Qt.SHIFT):
            self.edit_metadata(book_id)
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
        if self.follow_library_view and gprefs['qv_follows_column']:
            self.slave(current)

    def slave(self, current):
        '''
        called when a book is clicked on the library view
        '''
        if self.is_closed or not self.follow_library_view:
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
