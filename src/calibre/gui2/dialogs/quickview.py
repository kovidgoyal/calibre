#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import (Qt, QDialog, QAbstractItemView, QTableWidgetItem,
                      QListWidgetItem, QByteArray, QCoreApplication,
                      QApplication, pyqtSignal)

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

class Quickview(QDialog, Ui_Quickview):

    change_quickview_column   = pyqtSignal(object)

    def __init__(self, gui, view, row):
        QDialog.__init__(self, gui, flags=Qt.Window)
        Ui_Quickview.__init__(self)
        self.setupUi(self)
        self.isClosed = False

        self.books_table_column_widths = None
        try:
            self.books_table_column_widths = \
                        gprefs.get('quickview_dialog_books_table_widths', None)
            geom = gprefs.get('quickview_dialog_geometry', bytearray(''))
            self.restoreGeometry(QByteArray(geom))
        except:
            pass

        # Remove the help button from the window title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.db = view.model().db
        self.view = view
        self.gui = gui
        self.is_closed = False
        self.current_book_id = None
        self.current_key = None
        self.last_search = None
        self.current_column = None
        self.current_item = None
        self.no_valid_items = False

        self.items.setSelectionMode(QAbstractItemView.SingleSelection)
        self.items.currentTextChanged.connect(self.item_selected)

        # Set up the books table columns
        self.books_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.books_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.books_table.setColumnCount(3)
        t = QTableWidgetItem(_('Title'))
        self.books_table.setHorizontalHeaderItem(0, t)
        t = QTableWidgetItem(_('Authors'))
        self.books_table.setHorizontalHeaderItem(1, t)
        t = QTableWidgetItem(_('Series'))
        self.books_table.setHorizontalHeaderItem(2, t)
        self.books_table_header_height = self.books_table.height()
        self.books_table.cellDoubleClicked.connect(self.book_doubleclicked)
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
        self.change_quickview_column.connect(self.slave)
        QCoreApplication.instance().aboutToQuit.connect(self.save_state)
        self.search_button.clicked.connect(self.do_search)
        view.model().new_bookdisplay_data.connect(self.book_was_changed)

    def set_database(self, db):
        self.db = db
        self.items.blockSignals(True)
        self.books_table.blockSignals(True)
        self.items.clear()
        self.books_table.setRowCount(0)
        self.books_table.blockSignals(False)
        self.items.blockSignals(False)

    # search button
    def do_search(self):
        if self.no_valid_items:
            return
        if self.last_search is not None:
            self.gui.search.set_search_string(self.last_search)

    # Called when book information is changed in the library view. Make that
    # book current. This means that prev and next in edit metadata will move
    # the current book.
    def book_was_changed(self, mi):
        if self.is_closed or self.current_column is None:
            return
        self.refresh(self.view.model().index(self.db.row(mi.id), self.current_column))

    # clicks on the items listWidget
    def item_selected(self, txt):
        if self.no_valid_items:
            return
        self.fill_in_books_box(unicode(txt))

    # Given a cell in the library view, display the information
    def refresh(self, idx):
        bv_row = idx.row()
        self.current_column = idx.column()
        key = self.view.model().column_map[self.current_column]
        book_id = self.view.model().id(bv_row)

        if self.current_book_id == book_id and self.current_key == key:
            return

        # Only show items for categories
        if not self.db.field_metadata[key]['is_category']:
            if self.current_key is None:
                self.indicate_no_items()
                return
            key = self.current_key
        self.items_label.setText('{0} ({1})'.format(
                                    self.db.field_metadata[key]['name'], key))

        self.items.blockSignals(True)
        self.items.clear()
        self.books_table.setRowCount(0)

        mi = self.db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
        vals = mi.get(key, None)

        if vals:
            self.no_valid_items = False
            if self.db.field_metadata[key]['datatype'] == 'rating':
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
        self.items.addItem(QListWidgetItem(_('**No items found**')))
        self.books_label.setText(_('Click in a column  in the library view '
                                   'to see the information for that book'))

    def fill_in_books_box(self, selected_item):
        self.current_item = selected_item
        # Do a bit of fix-up on the items so that the search works.
        if selected_item.startswith('.'):
            sv = '.' + selected_item
        else:
            sv = selected_item
        sv = sv.replace('"', r'\"')
        self.last_search = self.current_key+':"=' + sv + '"'
        books = self.db.search(self.last_search, return_matches=True)

        self.books_table.setRowCount(len(books))
        self.books_label.setText(_('Books with selected item "{0}": {1}').
                                 format(selected_item, len(books)))

        select_item = None
        self.books_table.setSortingEnabled(False)
        tt = ('<p>' +
            _('Double-click on a book to change the selection in the library view. '
               'Shift- or control-double-click to edit the metadata of a book')
              + '</p>')
        for row, b in enumerate(books):
            mi = self.db.get_metadata(b, index_is_id=True, get_user_categories=False)
            a = TableItem(mi.title, mi.title_sort)
            a.setData(Qt.UserRole, b)
            a.setToolTip(tt)
            self.books_table.setItem(row, 0, a)
            if b == self.current_book_id:
                select_item = a
            a = TableItem(' & '.join(mi.authors), mi.author_sort)
            a.setToolTip(tt)
            self.books_table.setItem(row, 1, a)
            series = mi.format_field('series')[1]
            if series is None:
                series = ''
            a = TableItem(series, mi.series, mi.series_index)
            a.setToolTip(tt)
            self.books_table.setItem(row, 2, a)
            self.books_table.setRowHeight(row, self.books_table_row_height)

        self.books_table.setSortingEnabled(True)
        if select_item is not None:
            self.books_table.setCurrentItem(select_item)
            self.books_table.scrollToItem(select_item, QAbstractItemView.PositionAtCenter)

    # Deal with sizing the table columns. Done here because the numbers are not
    # correct until the first paint.
    def resizeEvent(self, *args):
        QDialog.resizeEvent(self, *args)
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

    def book_doubleclicked(self, row, column):
        if self.no_valid_items:
            return
        book_id = self.books_table.item(row, 0).data(Qt.UserRole).toInt()[0]
        self.view.select_rows([book_id])
        modifiers = int(QApplication.keyboardModifiers())
        if modifiers in (Qt.CTRL, Qt.SHIFT):
            em = find_plugin('Edit Metadata')
            if em is not None:
                em.actual_plugin_.edit_metadata(None)

    # called when a book is clicked on the library view
    def slave(self, current):
        if self.is_closed:
            return
        self.refresh(current)
        self.view.activateWindow()

    def save_state(self):
        if self.is_closed:
            return
        self.books_table_column_widths = []
        for c in range(0, self.books_table.columnCount()):
            self.books_table_column_widths.append(self.books_table.columnWidth(c))
        gprefs['quickview_dialog_books_table_widths'] = self.books_table_column_widths
        gprefs['quickview_dialog_geometry'] = bytearray(self.saveGeometry())

    def close(self):
        self.save_state()
        # clean up to prevent memory leaks
        self.db = self.view = self.gui = None
        self.is_closed = True

    # called by the window system
    def closeEvent(self, *args):
        self.close()
        QDialog.closeEvent(self, *args)

    # called by the close button
    def reject(self):
        self.close()
        QDialog.reject(self)