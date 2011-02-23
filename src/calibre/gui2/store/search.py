# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
from threading import Event, Thread
from Queue import Queue

from PyQt4.Qt import Qt, QAbstractItemModel, QDialog, QTimer, QVariant, \
    QModelIndex

from calibre.customize.ui import store_plugins
from calibre.gui2 import NONE
from calibre.gui2.store.search_ui import Ui_Dialog
from calibre.utils.icu import sort_key

class SearchDialog(QDialog, Ui_Dialog):

    HANG_TIME = 75000 # milliseconds seconds
    TIMEOUT = 75 # seconds

    def __init__(self, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)

        self.store_plugins = {}
        self.running_threads = []
        self.results = Queue()
        self.abort = Event()
        self.checker = QTimer()
        self.hang_check = 0
        
        self.model = Matches()
        self.results_view.setModel(self.model)

        for x in store_plugins():
            self.store_plugins[x.name] = x
            
        self.search.clicked.connect(self.do_search)
        self.checker.timeout.connect(self.get_results)
        self.results_view.activated.connect(self.open_store)
        
    def do_search(self, checked=False):
        # Stop all running threads.
        self.checker.stop()
        self.abort.set()
        self.running_threads = []
        self.results = Queue()
        self.abort = Event()
        # Clear the visible results.
        self.results_view.model().clear_results()
        
        # Don't start a search if there is nothing to search for.
        query = unicode(self.search_edit.text())
        if not query.strip():
            return
        
        for n in self.store_plugins:
            t = SearchThread(query, (n, self.store_plugins[n]), self.results, self.abort, self.TIMEOUT)
            self.running_threads.append(t)
            t.start()
        if self.running_threads:
            self.hang_check = 0
            self.checker.start(100)
            
    def get_results(self):
        # We only want the search plugins to run
        # a maximum set amount of time before giving up.
        self.hang_check += 1
        if self.hang_check >= self.HANG_TIME:
            self.abort.set()
            self.checker.stop()
        else:
            # Stop the checker if not threads are running.
            running = False
            for t in self.running_threads:
                if t.is_alive():
                    running = True
            if not running:
                self.checker.stop()
        
        while not self.results.empty():
            res = self.results.get_nowait()
            if res:
                result = SearchResult()
                result.store = res[0]
                result.cover_url = res[1][0]
                result.title = res[1][1]
                result.author = res[1][2]
                result.price = res[1][3]
                result.item_data = res[1][4]
                
                self.results_view.model().add_result(result)

    def open_store(self, index):
        result = self.results_view.model().get_result(index)
        self.store_plugins[result.store].open(self, result.item_data)


class SearchThread(Thread):
    
    def __init__(self, query, store, results, abort, timeout):
        Thread.__init__(self)
        self.daemon = True
        self.query = query
        self.store_name = store[0]
        self.store_plugin = store[1]
        self.results = results
        self.abort = abort
        self.timeout = timeout
    
    def run(self):
        for res in self.store_plugin.search(self.query, timeout=self.timeout):
            if self.abort.is_set():
                return
            self.results.put((self.store_name, res))


class SearchResult(object):
    
    def __init__(self):
        self.cover_url = ''
        self.title = ''
        self.author = ''
        self.price = ''
        self.store = ''
        self.item_data = ''


class Matches(QAbstractItemModel):

    HEADERS = [_('Cover'), _('Title'), _('Author(s)'), _('Price'), _('Store')]

    def __init__(self):
        QAbstractItemModel.__init__(self)
        self.matches = []
        
    def clear_results(self):
        self.matches = []
        self.reset()
    
    def add_result(self, result):
        self.matches.append(result)
        self.reset()
        #self.dataChanged.emit(self.createIndex(self.rowCount() - 1, 0), self.createIndex(self.rowCount() - 1, self.columnCount()))

    def get_result(self, index):
        row = index.row()
        if row < len(self.matches):
            return self.matches[row]
        else:
            return None

    def index(self, row, column, parent=QModelIndex()):
        return self.createIndex(row, column)

    def parent(self, index):
        if not index.isValid() or index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(0, 0)

    def rowCount(self, *args):
        return len(self.matches)

    def columnCount(self, *args):
        return 5
    
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
        result = self.matches[row]
        if role == Qt.DisplayRole:
            if col == 1:
                return QVariant(result.title)
            elif col == 2:
                return QVariant(result.author)
            elif col == 3:
                return QVariant(result.price)
            elif col == 4:
                return QVariant(result.store)
            return NONE
        elif role == Qt.DecorationRole:
            pass
        return NONE

    def data_as_text(self, result, col):
        text = ''
        if col == 1:
            text = result.title
        elif col == 2:
            text = result.author
        elif col == 3:
            text = result.price
            if len(text) < 3 or text[-3] not in ('.', ','):
                text += '00' 
            text = re.sub(r'\D', '', text)
        elif col == 4:
            text = result.store
        return text

    def sort(self, col, order, reset=True):
        if not self.matches:
            return
        descending = order == Qt.DescendingOrder       
        self.matches.sort(None,
            lambda x: sort_key(unicode(self.data_as_text(x, col))),
            descending)
        if reset:
            self.reset()
