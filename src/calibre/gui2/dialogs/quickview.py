#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import (Qt, QDialog, QAbstractItemView, QTableWidgetItem,
                      QListWidgetItem, QByteArray, QModelIndex)

from calibre.gui2.dialogs.quickview_ui import Ui_Quickview
from calibre.utils.icu import sort_key
from calibre.gui2 import gprefs

class tableItem(QTableWidgetItem):

    def __init__(self, val):
        QTableWidgetItem.__init__(self, val)
        self.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)

    def __ge__(self, other):
        return sort_key(unicode(self.text())) >= sort_key(unicode(other.text()))

    def __lt__(self, other):
        return sort_key(unicode(self.text())) < sort_key(unicode(other.text()))

class Quickview(QDialog, Ui_Quickview):

    def __init__(self, gui, view, row):
        QDialog.__init__(self, gui, flags=Qt.Window)
        Ui_Quickview.__init__(self)
        self.setupUi(self)
        self.isClosed = False

        try:
            geom = gprefs.get('quickview_dialog_geometry', bytearray(''))
            self.restoreGeometry(QByteArray(geom))
        except:
            pass

        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.db = view.model().db
        self.view = view
        self.gui = gui

        self.items.setSelectionMode(QAbstractItemView.SingleSelection)
        self.items.currentTextChanged.connect(self.item_selected)
#        self.items.setFixedWidth(150)

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

        self.is_closed = False
        self.current_book_id = None
        self.current_key = None
        self.use_current_key_for_next_refresh = False
        self.last_search = None

        self.refresh(row)
#        self.connect(self.view.selectionModel(), SIGNAL('currentChanged(QModelIndex,QModelIndex)'), self.slave)
        self.view.selectionModel().currentChanged[QModelIndex,QModelIndex].connect(self.slave)
        self.search_button.clicked.connect(self.do_search)

    def do_search(self):
        if self.last_search is not None:
            self.use_current_key_for_next_refresh = True
            self.gui.search.set_search_string(self.last_search)

    def item_selected(self, txt):
        self.fill_in_books_box(unicode(txt))

    def refresh(self, idx):
        bv_row = idx.row()
        key = self.view.model().column_map[idx.column()]

        book_id = self.view.model().id(bv_row)

        if self.use_current_key_for_next_refresh:
            key = self.current_key
            self.use_current_key_for_next_refresh = False
        else:
            if not self.db.field_metadata[key]['is_category']:
                if self.current_key is None:
                    return
                key = self.current_key
        self.items_label.setText('{0} ({1})'.format(
                                    self.db.field_metadata[key]['name'], key))
        self.items.clear()
        self.books_table.setRowCount(0)

        mi = self.db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
        vals = mi.get(key, None)
        if not vals:
            return

        if not isinstance(vals, list):
            vals = [vals]
        vals.sort(key=sort_key)

        self.items.blockSignals(True)
        for v in vals:
            a = QListWidgetItem(v)
            self.items.addItem(a)
        self.items.setCurrentRow(0)
        self.items.blockSignals(False)

        self.current_book_id = book_id
        self.current_key = key

        self.fill_in_books_box(vals[0])

    def fill_in_books_box(self, selected_item):
        if selected_item.startswith('.'):
            sv = '.' + selected_item
        else:
            sv = selected_item
        sv = sv.replace('"', r'\"')
        self.last_search = self.current_key+':"=' + sv + '"'
        books = self.db.search_getting_ids(self.last_search,
                                           self.db.data.search_restriction)
        self.books_table.setRowCount(len(books))
        self.books_label.setText(_('Books with selected item: {0}').format(len(books)))

        select_row = None
        self.books_table.setSortingEnabled(False)
        for row, b in enumerate(books):
            mi = self.db.get_metadata(b, index_is_id=True, get_user_categories=False)
            a = tableItem(mi.title)
            a.setData(Qt.UserRole, b)
            self.books_table.setItem(row, 0, a)
            a = tableItem(' & '.join(mi.authors))
            self.books_table.setItem(row, 1, a)
            series = mi.format_field('series')[1]
            if series is None:
                series = ''
            a = tableItem(series)
            self.books_table.setItem(row, 2, a)
            if b == self.current_book_id:
                select_row = row

        self.books_table.resizeColumnsToContents()
#        self.books_table.resizeRowsToContents()

        if select_row is not None:
            self.books_table.selectRow(select_row)
        self.books_table.setSortingEnabled(True)

    def book_doubleclicked(self, row, column):
        self.use_current_key_for_next_refresh = True
        self.view.select_rows([self.books_table.item(row, 0).data(Qt.UserRole).toInt()[0]])

    def slave(self, current, previous):
        self.refresh(current)
        self.view.activateWindow()

    def done(self, r):
        geom = bytearray(self.saveGeometry())
        gprefs['quickview_dialog_geometry'] = geom
        self.is_closed = True
        QDialog.done(self, r)
