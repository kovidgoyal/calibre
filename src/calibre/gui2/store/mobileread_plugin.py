# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import difflib
import heapq
import time
from contextlib import closing
from threading import RLock

from lxml import html

from PyQt4.Qt import Qt, QUrl, QDialog, QAbstractItemModel, QModelIndex, QVariant, \
    pyqtSignal

from calibre import browser
from calibre.gui2 import open_url, NONE
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.mobileread_store_dialog_ui import Ui_Dialog
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from calibre.utils.config import DynamicConfig
from calibre.utils.icu import sort_key

class MobileReadStore(BasicStoreConfig, StorePlugin):
    
    def genesis(self):
        self.config = DynamicConfig('store_' + self.name)
        self.rlock = RLock()
    
    def open(self, parent=None, detail_item=None, external=False):
        settings = self.get_settings()
        url = 'http://www.mobileread.com/'
        
        if external or settings.get(self.name + '_open_external', False):
            open_url(QUrl(detail_item if detail_item else url))
        else:
            if detail_item:
                d = WebStoreDialog(self.gui, url, parent, detail_item)
                d.setWindowTitle(self.name)
                d.set_tags(settings.get(self.name + '_tags', ''))
                d.exec_()
            else:
                d = MobeReadStoreDialog(self, parent)
                d.setWindowTitle(self.name)
                d.exec_()

    def search(self, query, max_results=10, timeout=60):
        books = self.get_book_list(timeout=timeout)

        query = query.lower()
        query_parts = query.split(' ')
        matches = []
        s = difflib.SequenceMatcher()
        for x in books:
            ratio = 0
            t_string = '%s %s' % (x.author.lower(), x.title.lower())
            query_matches = []
            for q in query_parts:
                if q in t_string:
                    query_matches.append(q)
            for q in query_matches:
                s.set_seq2(q)
                for p in t_string.split(' '):
                    s.set_seq1(p)
                    ratio += s.ratio()
            if ratio > 0:
                matches.append((ratio, x))
        
        # Move the best scorers to head of list.
        matches = heapq.nlargest(max_results, matches)
        for score, book in matches:
            book.price = '$0.00'
            book.drm = SearchResult.DRM_UNLOCKED
            yield book

    def update_book_list(self, timeout=10):
        with self.rlock:
            url = 'http://www.mobileread.com/forums/ebooks.php?do=getlist&type=html'
            
            last_download = self.config.get(self.name + '_last_download', None)
            # Don't update the book list if our cache is less than one week old.
            if last_download and (time.time() - last_download) < 604800:
                return
            
            # Download the book list HTML file from MobileRead.
            br = browser()
            raw_data = None
            with closing(br.open(url, timeout=timeout)) as f:
                raw_data = f.read()
            
            if not raw_data:
                return
            
            # Turn books listed in the HTML file into SearchResults's.
            books = []
            try:
                data = html.fromstring(raw_data)
                for book_data in data.xpath('//ul/li'):
                    book = SearchResult()
                    book.detail_item = ''.join(book_data.xpath('.//a/@href'))
                    book.formats = ''.join(book_data.xpath('.//i/text()'))
                    book.formats = book.formats.strip()
        
                    text = ''.join(book_data.xpath('.//a/text()'))
                    if ':' in text:
                        book.author, q, text = text.partition(':')
                    book.author = book.author.strip()
                    book.title = text.strip()
                    books.append(book)
            except:
                pass
    
            # Save the book list and it's create time.
            if books:
                self.config[self.name + '_last_download'] = time.time()
                self.config[self.name + '_book_list'] = books

    def get_book_list(self, timeout=10):
        self.update_book_list(timeout=timeout)
        return self.config.get(self.name + '_book_list', [])


class MobeReadStoreDialog(QDialog, Ui_Dialog):
    
    def __init__(self, plugin, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)

        self.plugin = plugin
        
        self.model = BooksModel()
        self.results_view.setModel(self.model)
        self.results_view.model().set_books(self.plugin.get_book_list())
        self.total.setText('%s' % self.model.rowCount())

        self.results_view.activated.connect(self.open_store)
        self.search_query.textChanged.connect(self.model.set_filter)
        self.results_view.model().total_changed.connect(self.total.setText)
        self.finished.connect(self.dialog_closed)
        
        self.restore_state()
        
    def open_store(self, index):
        result = self.results_view.model().get_book(index)
        if result:
            self.plugin.open(self, result.detail_item)
    
    def restore_state(self):
        geometry = self.plugin.config['store_mobileread_dialog_geometry']
        if geometry:
            self.restoreGeometry(geometry)

        results_cwidth = self.plugin.config['store_mobileread_dialog_results_view_column_width']
        if results_cwidth:
            for i, x in enumerate(results_cwidth):
                if i >= self.results_view.model().columnCount():
                    break
                self.results_view.setColumnWidth(i, x)
        else:
            for i in xrange(self.results_view.model().columnCount()):
                self.results_view.resizeColumnToContents(i)
                
        self.results_view.model().sort_col = self.plugin.config.get('store_mobileread_dialog_sort_col', 0)
        self.results_view.model().sort_order = self.plugin.config.get('store_mobileread_dialog_sort_order', Qt.AscendingOrder)
        self.results_view.model().sort(self.results_view.model().sort_col, self.results_view.model().sort_order)
        self.results_view.header().setSortIndicator(self.results_view.model().sort_col, self.results_view.model().sort_order)

    def save_state(self):
        self.plugin.config['store_mobileread_dialog_geometry'] = self.saveGeometry()
        self.plugin.config['store_mobileread_dialog_results_view_column_width'] = [self.results_view.columnWidth(i) for i in range(self.model.columnCount())]
        self.plugin.config['store_mobileread_dialog_sort_col'] = self.results_view.model().sort_col
        self.plugin.config['store_mobileread_dialog_sort_order'] = self.results_view.model().sort_order

    def dialog_closed(self, result):
        self.save_state()


class BooksModel(QAbstractItemModel):
    
    total_changed = pyqtSignal(unicode)

    HEADERS = [_('Title'), _('Author(s)'), _('Format')]

    def __init__(self):
        QAbstractItemModel.__init__(self)
        self.books = []
        self.all_books = []
        self.filter = ''
        self.sort_col = 0
        self.sort_order = Qt.AscendingOrder

    def set_books(self, books):
        self.books = books
        self.all_books = books
        
        self.sort(self.sort_col, self.sort_order)

    def get_book(self, index):
        row = index.row()
        if row < len(self.books):
            return self.books[row]
        else:
            return None
    
    def set_filter(self, filter):
        #self.layoutAboutToBeChanged.emit()
        self.beginResetModel()
        
        self.filter = unicode(filter)
        self.books = []
        if self.filter:
            for b in self.all_books:
                test = '%s %s %s' % (b.title, b.author, b.formats)
                test = test.lower()
                include = True
                for item in self.filter.split(' '):
                    item = item.lower()
                    if item not in test:
                        include = False
                        break
                if include:
                    self.books.append(b)
        else:
            self.books = self.all_books

        self.sort(self.sort_col, self.sort_order, reset=False)
        self.total_changed.emit('%s' % self.rowCount())

        self.endResetModel()
        #self.layoutChanged.emit()
    
    def index(self, row, column, parent=QModelIndex()):
        return self.createIndex(row, column)

    def parent(self, index):
        if not index.isValid() or index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(0, 0)

    def rowCount(self, *args):
        return len(self.books)

    def columnCount(self, *args):
        return len(self.HEADERS)
    
    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        text = ''
        if orientation == Qt.Horizontal:
            if section < len(self.HEADERS):
                text = self.HEADERS[section]
            return QVariant(text)
        else:
            return QVariant(section+1)

    def data(self, index, role):
        row, col = index.row(), index.column()
        result = self.books[row]
        if role == Qt.DisplayRole:
            if col == 0:
                return QVariant(result.title)
            elif col == 1:
                return QVariant(result.author)
            elif col == 2:
                return QVariant(result.formats)
        return NONE

    def data_as_text(self, result, col):
        text = ''
        if col == 0:
            text = result.title
        elif col == 1:
            text = result.author
        elif col == 2:
            text = result.formats
        return text

    def sort(self, col, order, reset=True):
        self.sort_col = col
        self.sort_order = order

        if not self.books:
            return
        descending = order == Qt.DescendingOrder       
        self.books.sort(None,
            lambda x: sort_key(unicode(self.data_as_text(x, col))),
            descending)
        if reset:
            self.reset()

