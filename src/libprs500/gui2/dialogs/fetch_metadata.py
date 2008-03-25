__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
GUI for fetching metadata from servers.
'''

import logging, cStringIO

from PyQt4.QtCore import Qt, QObject, SIGNAL, QVariant, \
                         QAbstractTableModel, QCoreApplication
from PyQt4.QtGui import QDialog, QItemSelectionModel

from libprs500.gui2.dialogs.fetch_metadata_ui import Ui_FetchMetadata
from libprs500.gui2 import error_dialog, NONE
from libprs500.ebooks.metadata.isbndb import create_books, option_parser
from libprs500 import Settings

class Matches(QAbstractTableModel):
    
    def __init__(self, matches):
        self.matches = matches
        self.matches.sort(cmp=lambda b, a: cmp(len(a.comments if a.comments else ''), len(b.comments if b.comments else '')))
        QAbstractTableModel.__init__(self)
        
    def rowCount(self, *args):
        return len(self.matches)
    
    def columnCount(self, *args):
        return 5
    
    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        text = ""
        if orientation == Qt.Horizontal:      
            if   section == 0: text = "Title"
            elif section == 1: text = "Author(s)"
            elif section == 2: text = "Author Sort"
            elif section == 3: text = "Publisher"
            elif section == 4: text = "ISBN"
            
            return QVariant(self.trUtf8(text))
        else: 
            return QVariant(section+1)
        
    def summary(self, row):
        return self.matches[row].comments
    
    def data(self, index, role):
        row, col = index.row(), index.column()
        if role == Qt.DisplayRole:
            book = self.matches[row]
            res = None
            if col == 0:
                res = book.title
            elif col == 1:
                res = ', '.join(book.authors)
            elif col == 2:
                res = book.author_sort
            elif col == 3:
                res = book.publisher
            elif col == 4:
                res = book.isbn
            if not res:
                return NONE
            return QVariant(res)
        return NONE

class FetchMetadata(QDialog, Ui_FetchMetadata):
    
    def __init__(self, parent, isbn, title, author, publisher, timeout):
        QDialog.__init__(self, parent)
        Ui_FetchMetadata.__init__(self)
        self.setupUi(self)
        
        self.timeout = timeout
        QObject.connect(self.fetch, SIGNAL('clicked()'), self.fetch_metadata)
        
        self.key.setText(Settings().value('isbndb.com key', QVariant('')).toString())
        
        self.setWindowTitle(title if title else 'Unknown')
        self.tlabel.setText(self.tlabel.text().arg(title if title else 'Unknown'))
        self.isbn = isbn
        self.title = title
        self.author = author.strip()
        self.publisher = publisher
        self.previous_row = None
        
        
        
    def show_summary(self, current, previous):
        row  = current.row()
        if row != self.previous_row:
            summ =  self.model.summary(row)
            self.summary.setText(summ if summ else '')
            self.previous_row = row
        
    def fetch_metadata(self):
        key = str(self.key.text())
        if not key:
            error_dialog(self, _('Cannot connect'), 
                         _('You must specify a valid access key for isbndb.com'))
            return
        else:
            Settings().setValue('isbndb.com key', QVariant(self.key.text()))
            
        args = ['isbndb']
        if self.isbn:
            args.extend(('--isbn', self.isbn))
        if self.title:
            args.extend(('--title', self.title))
        if self.author and not self.author == 'Unknown':
            args.extend(('--author', self.author))
        #if self.publisher:
        #    args.extend(('--publisher', self.publisher))
        
        self.fetch.setEnabled(False)
        self.setCursor(Qt.WaitCursor)
        QCoreApplication.instance().processEvents()
        
        args.append(key)
        parser = option_parser()
        opts, args = parser.parse_args(args)
        
        self.logger = logging.getLogger('Job #'+str(id))
        self.logger.setLevel(logging.DEBUG)
        self.log_dest = cStringIO.StringIO()
        handler = logging.StreamHandler(self.log_dest)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(filename)s:%(lineno)s: %(message)s'))
        self.logger.addHandler(handler)
        
        books = create_books(opts, args, self.logger, self.timeout)
        
        self.model = Matches(books)
        
        self.matches.setModel(self.model)
        QObject.connect(self.matches.selectionModel(), SIGNAL('currentRowChanged(QModelIndex, QModelIndex)'),
                     self.show_summary)
        self.model.reset()
        self.matches.selectionModel().select(self.model.index(0, 0), 
                              QItemSelectionModel.Select | QItemSelectionModel.Rows)
        self.matches.setCurrentIndex(self.model.index(0, 0))
        self.fetch.setEnabled(True)
        self.unsetCursor()
        self.matches.resizeColumnsToContents()
        


    def selected_book(self):
        try:
            return self.matches.model().matches[self.matches.currentIndex().row()]
        except:
            return None
