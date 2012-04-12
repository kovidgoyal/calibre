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
                ['search_replace',
                 'sr1_search', 'sr1_replace',
                 'sr2_search', 'sr2_replace',
                 'sr3_search', 'sr3_replace']
                )
        self.db, self.book_id = db, book_id

        self.sr_search.set_msg(_('&Search Regular Expression'))
        self.sr_search.set_book_id(book_id)
        self.sr_search.set_db(db)

        self.sr_search.doc_update.connect(self.update_doc)

        proto = QTableWidgetItem()
        proto.setFlags(Qt.ItemFlags(Qt.ItemIsSelectable + Qt.ItemIsEnabled))
        self.search_replace.setItemPrototype(proto)
        self.search_replace.setColumnCount(2)
        self.search_replace.setColumnWidth(0, 300)
        self.search_replace.setColumnWidth(1, 300)
        self.search_replace.setHorizontalHeaderLabels(['Search Expression', 'Replacement'])

        self.connect(self.sr_add, SIGNAL('clicked()'), self.sr_add_clicked)
        self.connect(self.sr_change, SIGNAL('clicked()'), self.sr_change_clicked)
        self.connect(self.sr_remove, SIGNAL('clicked()'), self.sr_remove_clicked)
        self.connect(self.sr_load, SIGNAL('clicked()'), self.sr_load_clicked)
        self.connect(self.sr_save, SIGNAL('clicked()'), self.sr_save_clicked)
        self.connect(self.search_replace, SIGNAL('currentCellChanged(int, int, int, int)'), self.sr_currentCellChanged)

        self.initialize_options(get_option, get_help, db, book_id)

    def sr_add_clicked(self):
        if self.sr_search.regex:
            row = self.sr_add_row(self.sr_search.regex, self.sr_replace.text())
            self.search_replace.setCurrentCell(row, 0)
            
    def sr_add_row(self, search, replace):
        row = self.search_replace.rowCount()
        self.search_replace.setRowCount(row + 1)
        newItem = self.search_replace.itemPrototype().clone()
        newItem.setText(search)
        self.search_replace.setItem(row,0, newItem)
        newItem = self.search_replace.itemPrototype().clone()
        newItem.setText(replace)
        self.search_replace.setItem(row,1, newItem)
        return row

    def sr_change_clicked(self):
        row = self.search_replace.currentRow()
        if  row >= 0:
            self.search_replace.item(row, 0).setText(self.sr_search.regex)
            self.search_replace.item(row, 1).setText(self.sr_replace.text())
            self.search_replace.setCurrentCell(row, 0)
            
    def sr_remove_clicked(self):
        row = self.search_replace.currentRow()
        if  row >= 0:
            self.search_replace.removeRow(row)
            self.search_replace.setCurrentCell(row-1, 0)

    def sr_load_clicked(self):
        filename = QFileDialog.getOpenFileName(self, 'Load Calibre Search-Replace definitions file', '.', 'Calibre Search-Replace definitions file (*.csr)')
        if filename:
            with open(filename, 'r') as f:
                val = f.read()
                self.set_value(self.search_replace, val)
            
    def sr_save_clicked(self):
        filename = QFileDialog.getSaveFileName(self, 'Save Calibre Search-Replace definitions file', '.', 'Calibre Search-Replace definitions file (*.csr)')
        if filename:
            with open(filename, 'w') as f:
                val = self.get_value(self.search_replace)
                f.write(val)
        
    def sr_currentCellChanged(self, row, column, previousRow, previousColumn) :
        if row >= 0:
            self.sr_change.setEnabled(True)
            self.sr_remove.setEnabled(True)
            self.sr_search.set_regex(self.search_replace.item(row, 0).text())
            self.sr_replace.setText(self.search_replace.item(row, 1).text())
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
        for row in xrange(0, self.search_replace.rowCount()):
            try:
                pat = unicode(self.search_replace.item(row,0).text())
                re.compile(pat)
            except Exception as err:
                error_dialog(self, _('Invalid regular expression'),
                             _('Invalid regular expression: %s')%err, show=True)
                return False
        return True

    # Options
    @property
    def opt_search_replace(self):
        return 'search_replace'

    @property
    def opt_sr1_search(self):
        return 'sr1_search'

    @property
    def opt_sr1_replace(self):
        return 'sr1_replace'

    @property
    def opt_sr2_search(self):
        return 'sr2_search'

    @property
    def opt_sr2_replace(self):
        return 'sr2_replace'

    @property
    def opt_sr3_search(self):
        return 'sr3_search'

    @property
    def opt_sr3_replace(self):
        return 'sr3_replace'


    # Options handling

    def connect_gui_obj_handler(self, g, slot):
        if g == self.opt_search_replace:
            self.search_replace.cellChanged.connect(slot)

    def get_value_handler(self, g):
        if g != self.opt_search_replace:
            return None
        
        ans = []
        for row in xrange(0, self.search_replace.rowCount()):
            colItems = []
            for col in xrange(0, self.search_replace.columnCount()):
                colItems.append(unicode(self.search_replace.item(row, col).text()))
            ans.append(colItems)
        return json.dumps(ans)

    def set_value_handler(self, g, val):
        if g != self.opt_search_replace:
            self.handle_legacy(g, val)
            return True

        try:
            rowItems = json.loads(val)
            if not isinstance(rowItems, list):
                rowItems = []
        except:
            rowItems = []

        if len(rowItems) == 0:
            return True

        self.search_replace.setRowCount(len(rowItems))
           
        for row, colItems in enumerate(rowItems):
            for col, cellValue in enumerate(colItems):
                newItem = self.search_replace.itemPrototype().clone()
                newItem.setText(cellValue)
                self.search_replace.setItem(row,col, newItem)
        return True

    def handle_legacy(self, g, val):
        '''
        Handles legacy search/replace options sr1_search, sr1_replace,
        sr2_search, sr2_replace, sr3_search, sr3_replace.
        Before introducing the search_replace option only three search/replace
        definitions could be made. These where stored in the options named above.
        This function is for backward compatibility with saved options and for
        compatibility with setting sr* options in the CLI.
        '''

        if not val: return
        
        row = int(g[2]) - 1 # the row to set in the search_replace table is 0 for sr1_*, 1 for sr2_*, etc
        col = (0 if g[4] == 's' else 1) # the fourth character in g is 's' for search options and 'r' for replace options

        # add any missing rows 
        while self.search_replace.rowCount() < row+1:
            self.sr_add_row('', '')
        
        # set the value
        self.search_replace.item(row, col).setText(val)

    def setup_help_handler(self, g, help):
        if g != self.opt_search_replace:
            return True

        self.search_replace._help = help
        self.setup_widget_help(self.search_replace)
        return True
        
