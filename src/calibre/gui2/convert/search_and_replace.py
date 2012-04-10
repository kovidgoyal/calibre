# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from PyQt4.QtCore import SIGNAL, Qt
from PyQt4.QtGui import QTableWidgetItem
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
                ['sr1_search', 'sr1_replace',
                 'sr2_search', 'sr2_replace',
                 'sr3_search', 'sr3_replace']
                )
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_sr1_search.set_msg(_('&Search Regular Expression'))
        self.opt_sr1_search.set_book_id(book_id)
        self.opt_sr1_search.set_db(db)
	self.opt_sr1_search.set_regex('test.*')
        self.opt_sr2_search.set_msg(_('&Search Regular Expression'))
        self.opt_sr2_search.set_book_id(book_id)
        self.opt_sr2_search.set_db(db)
        self.opt_sr3_search.set_msg(_('&Search Regular Expression'))
        self.opt_sr3_search.set_book_id(book_id)
        self.opt_sr3_search.set_db(db)

        self.opt_sr1_search.doc_update.connect(self.update_doc)
        self.opt_sr2_search.doc_update.connect(self.update_doc)
        self.opt_sr3_search.doc_update.connect(self.update_doc)

        self.opt_sr.setColumnCount(2)
        self.opt_sr.setHorizontalHeaderLabels(['Search Expression', 'Replacement'])
        self.connect(self.sr_add, SIGNAL('clicked()'), self.sr_add_clicked)
        self.connect(self.sr_change, SIGNAL('clicked()'), self.sr_change_clicked)
        self.connect(self.sr_remove, SIGNAL('clicked()'), self.sr_remove_clicked)
        self.connect(self.opt_sr, SIGNAL('currentCellChanged(int, int, int, int)'), self.sr_currentCellChanged)

    def sr_add_clicked(self):
        if self.opt_sr1_search.regex:
            self.opt_sr.insertRow(0)
            newItem = QTableWidgetItem()
            newItem.setFlags(Qt.ItemFlags(Qt.ItemIsSelectable + Qt.ItemIsEnabled))
            newItem.setText(self.opt_sr1_search.regex)
            self.opt_sr.setItem(0,0, newItem)
            newItem = QTableWidgetItem()
            newItem.setFlags(Qt.ItemFlags(Qt.ItemIsSelectable + Qt.ItemIsEnabled))
            newItem.setText(self.opt_sr1_replace.text())
            self.opt_sr.setItem(0,1, newItem)
            self.opt_sr.setCurrentCell(0, 0)

    def sr_change_clicked(self):
        row = self.opt_sr.currentRow()
        if  row >= 0:
            self.opt_sr.item(row, 0).setText(self.opt_sr1_search.regex)
            self.opt_sr.item(row, 1).setText(self.opt_sr1_replace.text())
            self.opt_sr.setCurrentCell(row, 0)
            
    def sr_remove_clicked(self):
        row = self.opt_sr.currentRow()
        if  row >= 0:
            self.opt_sr.removeRow(row)
            self.opt_sr.setCurrentCell(row-1, 0)
        
    def sr_currentCellChanged(self, row, column, previousRow, previousColumn) :
        if row >= 0:
            self.sr_change.setEnabled(True)
            self.sr_remove.setEnabled(True)
            self.opt_sr1_search.set_regex(self.opt_sr.item(row, 0).text())
            self.opt_sr1_replace.setText(self.opt_sr.item(row, 1).text())
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

        d(self.opt_sr1_search)
        d(self.opt_sr2_search)
        d(self.opt_sr3_search)

        self.opt_sr1_search.break_cycles()
        self.opt_sr2_search.break_cycles()
        self.opt_sr3_search.break_cycles()

    def update_doc(self, doc):
        self.opt_sr1_search.set_doc(doc)
        self.opt_sr2_search.set_doc(doc)
        self.opt_sr3_search.set_doc(doc)

    def pre_commit_check(self):
        for x in ('sr1_search', 'sr2_search', 'sr3_search'):
            x = getattr(self, 'opt_'+x)
            try:
                pat = unicode(x.regex)
                re.compile(pat)
            except Exception as err:
                error_dialog(self, _('Invalid regular expression'),
                             _('Invalid regular expression: %s')%err, show=True)
                return False
        return True

    def opt_sr_items
        items = []
        for row in xrange(0, self.opt_sr.rowCount()):
            items.append([self.opt_sr.getItem(row,0).text(), self.opt_sr.getItem(row,1).text()])
        return items
