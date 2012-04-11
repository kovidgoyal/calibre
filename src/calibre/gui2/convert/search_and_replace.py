# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re, json

from PyQt4.QtCore import SIGNAL, Qt
from PyQt4.QtGui import QTableWidget, QTableWidgetItem, QFileDialog
from calibre.gui2.convert.search_and_replace_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2 import error_dialog

class SearchAndReplaceWidget(Widget, Ui_Form):

    TITLE = _('Search\n&\nReplace')
    HELP  = _('Modify the document text and structure using user defined patterns.')
    COMMIT_NAME = 'search_and_replace'
    ICON = I('search.png')
    STRIP_TEXT_FIELDS = False

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['search_replace']
                )
        self.db, self.book_id = db, book_id

        self.sr_search.set_msg(_('&Search Regular Expression'))
        self.sr_search.set_book_id(book_id)
        self.sr_search.set_db(db)

        self.sr_search.doc_update.connect(self.update_doc)

        proto = QTableWidgetItem()
        proto.setFlags(Qt.ItemFlags(Qt.ItemIsSelectable + Qt.ItemIsEnabled))
        self.opt_search_replace.setItemPrototype(proto)
        self.opt_search_replace.setColumnCount(2)
        self.opt_search_replace.setColumnWidth(0, 300)
        self.opt_search_replace.setColumnWidth(1, 300)
        self.opt_search_replace.setHorizontalHeaderLabels(['Search Expression', 'Replacement'])

        self.connect(self.sr_add, SIGNAL('clicked()'), self.sr_add_clicked)
        self.connect(self.sr_change, SIGNAL('clicked()'), self.sr_change_clicked)
        self.connect(self.sr_remove, SIGNAL('clicked()'), self.sr_remove_clicked)
        self.connect(self.sr_load, SIGNAL('clicked()'), self.sr_load_clicked)
        self.connect(self.sr_save, SIGNAL('clicked()'), self.sr_save_clicked)
        self.connect(self.opt_search_replace, SIGNAL('currentCellChanged(int, int, int, int)'), self.sr_currentCellChanged)

        self.initialize_options(get_option, get_help, db, book_id)

    def sr_add_clicked(self):
        if self.sr_search.regex:
            self.opt_search_replace.insertRow(0)
            newItem = self.opt_search_replace.itemPrototype().clone()
            newItem.setText(self.sr_search.regex)
            self.opt_search_replace.setItem(0,0, newItem)
            newItem = self.opt_search_replace.itemPrototype().clone()
            newItem.setText(self.sr_replace.text())
            self.opt_search_replace.setItem(0,1, newItem)
            self.opt_search_replace.setCurrentCell(0, 0)

    def sr_change_clicked(self):
        row = self.opt_search_replace.currentRow()
        if  row >= 0:
            self.opt_search_replace.item(row, 0).setText(self.sr_search.regex)
            self.opt_search_replace.item(row, 1).setText(self.sr_replace.text())
            self.opt_search_replace.setCurrentCell(row, 0)
            
    def sr_remove_clicked(self):
        row = self.opt_search_replace.currentRow()
        if  row >= 0:
            self.opt_search_replace.removeRow(row)
            self.opt_search_replace.setCurrentCell(row-1, 0)

    def sr_load_clicked(self):
        filename = QFileDialog.getOpenFileName(self, 'Load Calibre Search-Replace definitions file', '.', 'Calibre Search-Replace definitions file (*.csr)')
        if filename:
            with open(filename, 'r') as f:
                val = f.read()
                self.set_value(self.opt_search_replace, val)
            
    def sr_save_clicked(self):
        filename = QFileDialog.getSaveFileName(self, 'Save Calibre Search-Replace definitions file', '.', 'Calibre Search-Replace definitions file (*.csr)')
        if filename:
            with open(filename, 'w') as f:
                val = self.get_value(self.opt_search_replace)
                f.write(val)
        
    def sr_currentCellChanged(self, row, column, previousRow, previousColumn) :
        if row >= 0:
            self.sr_change.setEnabled(True)
            self.sr_remove.setEnabled(True)
            self.sr_search.set_regex(self.opt_search_replace.item(row, 0).text())
            self.sr_replace.setText(self.opt_search_replace.item(row, 1).text())
        else:
            self.sr_change.setEnabled(False)
            self.sr_remove.setEnabled(False)
        
    def break_cycles(self):
        Widget.break_cycles(self)

        def d(x):
            try:
                x.disconnect()
            except:
                pass

        d(self.sr_search)

        self.sr_search.break_cycles()

    def update_doc(self, doc):
        self.sr_search.set_doc(doc)

    def pre_commit_check(self):
        for row in xrange(0, self.opt_search_replace.rowCount()):
            try:
                pat = unicode(self.opt_search_replace.item(row,0).text())
                re.compile(pat)
            except Exception as err:
                error_dialog(self, _('Invalid regular expression'),
                             _('Invalid regular expression: %s')%err, show=True)
                return False
        return True


    # Options handling

    def connect_gui_obj_handler(self, g, slot):
        if isinstance(g, QTableWidget):
            g.cellChanged.connect(slot)

    def get_value_handler(self, g):
        ans = []
        for row in xrange(0, g.rowCount()):
            colItems = []
            for col in xrange(0, g.columnCount()):
                colItems.append(unicode(g.item(row, col).text()))
            ans.append(colItems)
        return json.dumps(ans)

    def set_value_handler(self, g, val):
        try:
            rowItems = json.loads(val)
            if not isinstance(rowItems, list):
                rowItems = []
        except:
            rowItems = []

        g.setRowCount(len(rowItems))
           
        for row, colItems in enumerate(rowItems):
            for col, cellValue in enumerate(colItems):
                newItem = g.itemPrototype().clone()
                newItem.setText(cellValue)
                g.setItem(row,col, newItem)
        return True
