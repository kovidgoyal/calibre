# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import difflib
import heapq
import time
from contextlib import closing
from operator import attrgetter
from threading import RLock

from lxml import html

from PyQt4.Qt import Qt, QUrl, QDialog, QAbstractItemModel, QModelIndex, QVariant, \
    pyqtSignal, QIcon

from calibre import browser
from calibre.gui2 import open_url, NONE
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.mobileread_store_dialog_ui import Ui_Dialog
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from calibre.gui2.store.search.adv_search_builder import AdvSearchBuilderDialog
from calibre.library.caches import _match, CONTAINS_MATCH, EQUALS_MATCH, \
    REGEXP_MATCH
from calibre.utils.icu import sort_key
from calibre.utils.search_query_parser import SearchQueryParser

class MobileReadStore(BasicStoreConfig, StorePlugin):
    
    def genesis(self):
        self.rlock = RLock()
    
    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.mobileread.com/'
        
        if external or self.config.get('open_external', False):
            open_url(QUrl(detail_item if detail_item else url))
        else:
            if detail_item:
                d = WebStoreDialog(self.gui, url, parent, detail_item)
                d.setWindowTitle(self.name)
                d.set_tags(self.config.get('tags', ''))
                d.exec_()
            else:
                d = MobeReadStoreDialog(self, parent)
                d.setWindowTitle(self.name)
                d.exec_()

    def search(self, query, max_results=10, timeout=60):
        books = self.get_book_list(timeout=timeout)

        sf = SearchFilter(books)
        matches = sf.parse(query)

        for book in matches:
            book.price = '$0.00'
            book.drm = SearchResult.DRM_UNLOCKED
            yield book

    def update_book_list(self, timeout=10):
        with self.rlock:
            url = 'http://www.mobileread.com/forums/ebooks.php?do=getlist&type=html'
            
            last_download = self.config.get('last_download', None)
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
                self.config['last_download'] = time.time()
                self.config['book_list'] = self.seralize_books(books)

    def get_book_list(self, timeout=10):
        self.update_book_list(timeout=timeout)
        return self.deseralize_books(self.config.get('book_list', []))
    
    def seralize_books(self, books):
        sbooks = []
        for b in books:
            data = {}
            data['author'] = b.author
            data['title'] = b.title
            data['detail_item'] = b.detail_item
            data['formats'] = b.formats
            sbooks.append(data)
        return sbooks
    
    def deseralize_books(self, sbooks):
        books = []
        for s in sbooks:
            b = SearchResult()
            b.author = s.get('author', '')
            b.title = s.get('title', '')
            b.detail_item = s.get('detail_item', '')
            b.formats = s.get('formats', '')
            books.append(b)
        return books


class MobeReadStoreDialog(QDialog, Ui_Dialog):
    
    def __init__(self, plugin, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)

        self.plugin = plugin
        
        self.adv_search_button.setIcon(QIcon(I('search.png')))
        
        self._model = BooksModel(self.plugin.get_book_list())
        self.results_view.setModel(self._model)
        self.total.setText('%s' % self.results_view.model().rowCount())

        self.search_button.clicked.connect(self.do_search)
        self.adv_search_button.clicked.connect(self.build_adv_search)
        self.results_view.activated.connect(self.open_store)
        self.results_view.model().total_changed.connect(self.update_book_total)
        self.finished.connect(self.dialog_closed)
        
        self.restore_state()
        
    def do_search(self):
        self.results_view.model().search(unicode(self.search_query.text()))
        
    def open_store(self, index):
        result = self.results_view.model().get_book(index)
        if result:
            self.plugin.open(self, result.detail_item)
    
    def update_book_total(self, total):
        self.total.setText('%s' % total)
    
    def build_adv_search(self):
        adv = AdvSearchBuilderDialog(self)
        adv.price_label.hide()
        adv.price_box.hide()
        if adv.exec_() == QDialog.Accepted:
            self.search_query.setText(adv.search_string())
    
    def restore_state(self):
        geometry = self.plugin.config.get('dialog_geometry', None)
        if geometry:
            self.restoreGeometry(geometry)

        results_cwidth = self.plugin.config.get('dialog_results_view_column_width')
        if results_cwidth:
            for i, x in enumerate(results_cwidth):
                if i >= self.results_view.model().columnCount():
                    break
                self.results_view.setColumnWidth(i, x)
        else:
            for i in xrange(self.results_view.model().columnCount()):
                self.results_view.resizeColumnToContents(i)
                
        self.results_view.model().sort_col = self.plugin.config.get('dialog_sort_col', 0)
        self.results_view.model().sort_order = self.plugin.config.get('dialog_sort_order', Qt.AscendingOrder)
        self.results_view.model().sort(self.results_view.model().sort_col, self.results_view.model().sort_order)
        self.results_view.header().setSortIndicator(self.results_view.model().sort_col, self.results_view.model().sort_order)

    def save_state(self):
        self.plugin.config['dialog_geometry'] = bytearray(self.saveGeometry())
        self.plugin.config['dialog_results_view_column_width'] = [self.results_view.columnWidth(i) for i in range(self.results_view.model().columnCount())]
        self.plugin.config['dialog_sort_col'] = self.results_view.model().sort_col
        self.plugin.config['dialog_sort_order'] = self.results_view.model().sort_order

    def dialog_closed(self, result):
        self.save_state()


class BooksModel(QAbstractItemModel):
    
    total_changed = pyqtSignal(int)

    HEADERS = [_('Title'), _('Author(s)'), _('Format')]

    def __init__(self, all_books):
        QAbstractItemModel.__init__(self)
        self.books = all_books
        self.all_books = all_books
        self.filter = ''
        self.search_filter = SearchFilter(all_books)
        self.sort_col = 0
        self.sort_order = Qt.AscendingOrder

    def get_book(self, index):
        row = index.row()
        if row < len(self.books):
            return self.books[row]
        else:
            return None
    
    def search(self, filter):        
        self.filter = filter.strip()
        if not self.filter:
            self.books = self.all_books
        else:
            try:
                self.books = list(self.search_filter.parse(self.filter))
            except:
                self.books = self.all_books
        self.sort(self.sort_col, self.sort_order)
        self.total_changed.emit(self.rowCount())
    
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


class SearchFilter(SearchQueryParser):
    
    USABLE_LOCATIONS = [
        'all',
        'author',
        'authors',
        'format',
        'formats',
        'title',
    ]

    def __init__(self, all_books=[]):
        SearchQueryParser.__init__(self, locations=self.USABLE_LOCATIONS)
        self.srs = set(all_books)

    def universal_set(self):
        return self.srs

    def get_matches(self, location, query):
        location = location.lower().strip()
        if location == 'authors':
            location = 'author'
        elif location == 'formats':
            location = 'format'

        matchkind = CONTAINS_MATCH
        if len(query) > 1:
            if query.startswith('\\'):
                query = query[1:]
            elif query.startswith('='):
                matchkind = EQUALS_MATCH
                query = query[1:]
            elif query.startswith('~'):
                matchkind = REGEXP_MATCH
                query = query[1:]
        if matchkind != REGEXP_MATCH: ### leave case in regexps because it can be significant e.g. \S \W \D
            query = query.lower()

        if location not in self.USABLE_LOCATIONS:
            return set([])
        matches = set([])
        all_locs = set(self.USABLE_LOCATIONS) - set(['all'])
        locations = all_locs if location == 'all' else [location]
        q = {
             'author': lambda x: x.author.lower(),
             'format': attrgetter('formats'),
             'title': lambda x: x.title.lower(),
        }
        for x in ('author', 'format'):
            q[x+'s'] = q[x]
        for sr in self.srs:
            for locvalue in locations:
                accessor = q[locvalue]
                if query == 'true':
                    if accessor(sr) is not None:
                        matches.add(sr)
                    continue
                if query == 'false':
                    if accessor(sr) is None:
                        matches.add(sr)
                    continue
                try:
                    ### Can't separate authors because comma is used for name sep and author sep
                    ### Exact match might not get what you want. For that reason, turn author
                    ### exactmatch searches into contains searches.
                    if locvalue == 'author' and matchkind == EQUALS_MATCH:
                        m = CONTAINS_MATCH
                    else:
                        m = matchkind

                    vals = [accessor(sr)]
                    if _match(query, vals, m):
                        matches.add(sr)
                        break
                except ValueError: # Unicode errors
                    import traceback
                    traceback.print_exc()
        return matches
