# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
import time
from contextlib import closing
from threading import Event, Thread
from Queue import Queue

from PyQt4.Qt import Qt, QAbstractItemModel, QDialog, QTimer, QVariant, \
    QModelIndex, QPixmap, QSize, QCheckBox, QVBoxLayout, QHBoxLayout, \
    QPushButton 

from calibre import browser
from calibre.customize.ui import store_plugins
from calibre.gui2 import NONE
from calibre.gui2.store.search_ui import Ui_Dialog
from calibre.utils.icu import sort_key
from calibre.utils.magick.draw import thumbnail

HANG_TIME = 75000 # milliseconds seconds
TIMEOUT = 75 # seconds
SEARCH_THREAD_TOTAL = 4
COVER_DOWNLOAD_THREAD_TOTAL = 2

class SearchDialog(QDialog, Ui_Dialog):

    def __init__(self, gui, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)
        
        self.gui = gui

        self.store_plugins = {}
        self.search_pool = SearchThreadPool(SearchThread, SEARCH_THREAD_TOTAL)
        self.checker = QTimer()
        self.hang_check = 0
        
        self.model = Matches()
        self.results_view.setModel(self.model)

        stores_group_layout = QVBoxLayout()
        self.stores_group.setLayout(stores_group_layout)
        for x in store_plugins():
            self.store_plugins[x.name] = x
            cbox = QCheckBox(x.name)
            cbox.setChecked(True)
            stores_group_layout.addWidget(cbox)
            setattr(self, 'store_check_' + x.name, cbox)
        stores_group_layout.addStretch()

        self.search.clicked.connect(self.do_search)
        self.checker.timeout.connect(self.get_results)
        self.results_view.activated.connect(self.open_store)
        self.select_all_stores.clicked.connect(self.stores_select_all)
        self.select_invert_stores.clicked.connect(self.stores_select_invert)
        self.select_none_stores.clicked.connect(self.stores_select_none)
        
        self.resize_columns()
        
    def resize_columns(self):
        total = 600
        # Cover
        self.results_view.setColumnWidth(0, 85)
        total = total - 85
        # Title
        self.results_view.setColumnWidth(1,int(total*.35))
        # Author
        self.results_view.setColumnWidth(2,int(total*.35))
        # Price
        self.results_view.setColumnWidth(3, int(total*.10))
        # Store
        self.results_view.setColumnWidth(4, int(total*.20))
        
    def do_search(self, checked=False):
        # Stop all running threads.
        self.checker.stop()
        self.search_pool.abort()
        # Clear the visible results.
        self.results_view.model().clear_results()
        
        # Don't start a search if there is nothing to search for.
        query = unicode(self.search_edit.text())
        if not query.strip():
            return
        
        for n in self.store_plugins:
            if getattr(self, 'store_check_' + n).isChecked():
                self.search_pool.add_task(query, n, self.store_plugins[n], TIMEOUT)
        if self.search_pool.has_tasks():
            self.hang_check = 0
            self.checker.start(100)
            self.search_pool.start_threads()
            
    def get_results(self):
        # We only want the search plugins to run
        # a maximum set amount of time before giving up.
        self.hang_check += 1
        if self.hang_check >= HANG_TIME:
            self.search_pool.abort()
            self.checker.stop()
        else:
            # Stop the checker if not threads are running.
            if not self.search_pool.threads_running():
                self.checker.stop()
        
        while self.search_pool.has_results():
            res = self.search_pool.get_result_no_wait()
            if res:
                self.results_view.model().add_result(res)

    def open_store(self, index):
        result = self.results_view.model().get_result(index)
        self.store_plugins[result.store_name].open(self.gui, self, result.detail_item)

    def get_store_checks(self):
        checks = []
        for x in self.store_plugins:
            check = getattr(self, 'store_check_' + x, None)
            if check:
                checks.append(check)
        return checks

    def stores_select_all(self):
        for check in self.get_store_checks():
            check.setChecked(True)
    
    def stores_select_invert(self):
        for check in self.get_store_checks():
            check.setChecked(not check.isChecked())
    
    def stores_select_none(self):
        for check in self.get_store_checks():
            check.setChecked(False)


class GenericDownloadThreadPool(object):
    '''
    add_task must be implemented in a subclass.
    '''
    
    def __init__(self, thread_type, thread_count):
        self.thread_type = thread_type
        self.thread_count = thread_count
        
        self.tasks = Queue()
        self.results = Queue()
        self.threads = []
        
    def start_threads(self):
        for i in range(self.thread_count):
            t = self.thread_type(self.tasks, self.results)
            self.threads.append(t)
            t.start()
        
    def abort(self):
        self.tasks = Queue()
        self.results = Queue()
        for t in self.threads:
            t.abort()
        self.threads = []
    
    def has_tasks(self):
        return not self.tasks.empty()
    
    def get_result(self):
        return self.results.get()
    
    def get_result_no_wait(self):
        return self.results.get_nowait()
    
    def result_count(self):
        return len(self.results)
    
    def has_results(self):
        return not self.results.empty()
    
    def threads_running(self):
        for t in self.threads:
            if t.is_alive():
                return True
        return False


class SearchThreadPool(GenericDownloadThreadPool):
    '''
    Threads will run until there is no work or
    abort is called. Create and start new threads
    using start_threads(). Reset by calling abort().
    
    Example:
    sp = SearchThreadPool(SearchThread, 3)
    add tasks using add_task(...)
    sp.start_threads()
    all threads have finished.
    sp.abort()
    add tasks using add_task(...)
    sp.start_threads()
    '''
        
    def add_task(self, query, store_name, store_plugin, timeout):
        self.tasks.put((query, store_name, store_plugin, timeout))


class SearchThread(Thread):
    
    def __init__(self, tasks, results):
        Thread.__init__(self)
        self.daemon = True
        self.tasks = tasks
        self.results = results
        self._run = True

    def abort(self):
        self._run = False
    
    def run(self):
        while self._run and not self.tasks.empty():
            try:
                query, store_name, store_plugin, timeout = self.tasks.get()
                for res in store_plugin.search(query, timeout=timeout):
                    if not self._run:
                        return
                    res.store_name = store_name
                    self.results.put(res)
                self.tasks.task_done()
            except:
                pass


class CoverThreadPool(GenericDownloadThreadPool):
    '''
    Once started all threads run until abort is called.
    '''
    
    def add_task(self, search_result, update_callback, timeout=5):
        self.tasks.put((search_result, update_callback, timeout))


class CoverThread(Thread):

    def __init__(self, tasks, results):
        Thread.__init__(self)
        self.daemon = True
        self.tasks = tasks
        self.results = results
        self._run = True
        
        self.br = browser()

    def abort(self):
        self._run = False
        
    def run(self):
        while self._run:
            try:
                time.sleep(.1)
                while not self.tasks.empty():
                    if not self._run:
                        break
                    result, callback, timeout = self.tasks.get()
                    if result and result.cover_url:
                        with closing(self.br.open(result.cover_url, timeout=timeout)) as f:
                            result.cover_data = f.read()
                        result.cover_data = thumbnail(result.cover_data, 64, 64)[2]
                        callback()
                    self.tasks.task_done()
            except:
                continue


class Matches(QAbstractItemModel):

    HEADERS = [_('Cover'), _('Title'), _('Author(s)'), _('Price'), _('Store')]

    def __init__(self):
        QAbstractItemModel.__init__(self)
        self.matches = []
        self.cover_pool = CoverThreadPool(CoverThread, 2)
        self.cover_pool.start_threads()
        
    def clear_results(self):
        self.matches = []
        self.cover_pool.abort()
        self.cover_pool.start_threads()
        self.reset()
    
    def add_result(self, result):
        self.layoutAboutToBeChanged.emit()
        self.matches.append(result)
        
        self.cover_pool.add_task(result, self.update_result)
        self.layoutChanged.emit()

    def get_result(self, index):
        row = index.row()
        if row < len(self.matches):
            return self.matches[row]
        else:
            return None

    def update_result(self):
        self.layoutAboutToBeChanged.emit()
        self.layoutChanged.emit()

    def index(self, row, column, parent=QModelIndex()):
        return self.createIndex(row, column)

    def parent(self, index):
        if not index.isValid() or index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(0, 0)

    def rowCount(self, *args):
        return len(self.matches)

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
        result = self.matches[row]
        if role == Qt.DisplayRole:
            if col == 1:
                return QVariant(result.title)
            elif col == 2:
                return QVariant(result.author)
            elif col == 3:
                return QVariant(result.price)
            elif col == 4:
                return QVariant(result.store_name)
            return NONE
        elif role == Qt.DecorationRole:
            if col == 0 and result.cover_data:
                p = QPixmap()
                p.loadFromData(result.cover_data)
                return QVariant(p)
        elif role == Qt.SizeHintRole:
            return QSize(64, 64)
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
            text = text.rjust(6, '0')
        elif col == 4:
            text = result.store_name
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

