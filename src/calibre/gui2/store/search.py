# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
import time
import traceback
from contextlib import closing
from random import shuffle
from threading import Thread
from Queue import Queue

from PyQt4.Qt import (Qt, QAbstractItemModel, QDialog, QTimer, QVariant,
    QModelIndex, QPixmap, QSize, QCheckBox, QVBoxLayout)

from calibre import browser
from calibre.gui2 import NONE
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.store.search_ui import Ui_Dialog
from calibre.gui2.store.search_result import SearchResult
from calibre.library.caches import _match, CONTAINS_MATCH, EQUALS_MATCH, \
    REGEXP_MATCH
from calibre.utils.config import DynamicConfig
from calibre.utils.icu import sort_key
from calibre.utils.magick.draw import thumbnail
from calibre.utils.search_query_parser import SearchQueryParser

HANG_TIME = 75000 # milliseconds seconds
TIMEOUT = 75 # seconds
SEARCH_THREAD_TOTAL = 4
COVER_DOWNLOAD_THREAD_TOTAL = 2

def comparable_price(text):
    if len(text) < 3 or text[-3] not in ('.', ','):
        text += '00'
    text = re.sub(r'\D', '', text)
    text = text.rjust(6, '0')
    return text


class SearchDialog(QDialog, Ui_Dialog):

    def __init__(self, istores, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)

        self.config = DynamicConfig('store/search')

        # We keep a cache of store plugins and reference them by name.
        self.store_plugins = istores
        self.search_pool = SearchThreadPool(SearchThread, SEARCH_THREAD_TOTAL)
        # Check for results and hung threads.
        self.checker = QTimer()
        self.hang_check = 0

        self.model = Matches()
        self.results_view.setModel(self.model)

        # Add check boxes for each store so the user
        # can disable searching specific stores on a
        # per search basis.
        stores_group_layout = QVBoxLayout()
        self.stores_group.setLayout(stores_group_layout)
        for x in self.store_plugins:
            cbox = QCheckBox(x)
            cbox.setChecked(True)
            stores_group_layout.addWidget(cbox)
            setattr(self, 'store_check_' + x, cbox)
        stores_group_layout.addStretch()

        # Create and add the progress indicator
        self.pi = ProgressIndicator(self, 24)
        self.bottom_layout.insertWidget(0, self.pi)

        self.search.clicked.connect(self.do_search)
        self.checker.timeout.connect(self.get_results)
        self.results_view.activated.connect(self.open_store)
        self.select_all_stores.clicked.connect(self.stores_select_all)
        self.select_invert_stores.clicked.connect(self.stores_select_invert)
        self.select_none_stores.clicked.connect(self.stores_select_none)
        self.finished.connect(self.dialog_closed)

        self.restore_state()

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
        self.results_view.setColumnWidth(3, int(total*.5))
        # DRM
        self.results_view.setColumnWidth(4, int(total*.5))
        # Store
        self.results_view.setColumnWidth(5, int(total*.15))
        # Formats
        self.results_view.setColumnWidth(6, int(total*.5))

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
        # Give the query to the results model so it can do
        # futher filtering.
        self.results_view.model().set_query(query)

        # Plugins are in alphebetic order. Randomize the
        # order of plugin names. This way plugins closer
        # to a don't have an unfair advantage over
        # plugins further from a.
        store_names = self.store_plugins.keys()
        if not store_names:
            return
        # Remove all of our internal filtering logic from the query.
        query = self.clean_query(query)
        shuffle(store_names)
        # Add plugins that the user has checked to the search pool's work queue.
        for n in store_names:
            if getattr(self, 'store_check_' + n).isChecked():
                self.search_pool.add_task(query, n, self.store_plugins[n], TIMEOUT)
        if self.search_pool.has_tasks():
            self.hang_check = 0
            self.checker.start(100)
            self.search_pool.start_threads()
            self.pi.startAnimation()

    def clean_query(self, query):
        query = query.lower()
        # Remove control modifiers.
        query = query.replace('\\', '')
        query = query.replace('!', '')
        query = query.replace('=', '')
        query = query.replace('~', '')
        query = query.replace('>', '')
        query = query.replace('<', '')
        # Remove the prefix.
        for loc in ( 'all', 'author', 'authors', 'title'):
            query = re.sub(r'%s:"?(?P<a>[^\s"]+)"?' % loc, '\g<a>', query)
        # Remove the prefix and search text.
        for loc in ('cover', 'drm', 'format', 'formats', 'price', 'store'):
            query = re.sub(r'%s:"[^"]"' % loc, '', query)
            query = re.sub(r'%s:[^\s]*' % loc, '', query)
        # Remove logic.
        query = re.sub(r'(^|\s)(and|not|or)(\s|$)', ' ', query)
        # Remove excess whitespace.
        query = re.sub(r'\s{2,}', ' ', query)
        query = query.strip()
        return query

    def save_state(self):
        self.config['store_search_geometry'] = self.saveGeometry()
        self.config['store_search_store_splitter_state'] = self.store_splitter.saveState()
        self.config['store_search_results_view_column_width'] = [self.results_view.columnWidth(i) for i in range(self.model.columnCount())]

        store_check = {}
        for n in self.store_plugins:
            store_check[n] = getattr(self, 'store_check_' + n).isChecked()
        self.config['store_search_store_checked'] = store_check

    def restore_state(self):
        geometry = self.config['store_search_geometry']
        if geometry:
            self.restoreGeometry(geometry)

        splitter_state = self.config['store_search_store_splitter_state']
        if splitter_state:
            self.store_splitter.restoreState(splitter_state)

        results_cwidth = self.config['store_search_results_view_column_width']
        if results_cwidth:
            for i, x in enumerate(results_cwidth):
                if i >= self.model.columnCount():
                    break
                self.results_view.setColumnWidth(i, x)
        else:
            self.resize_columns()

        store_check = self.config['store_search_store_checked']
        if store_check:
            for n in store_check:
                if hasattr(self, 'store_check_' + n):
                    getattr(self, 'store_check_' + n).setChecked(store_check[n])

    def get_results(self):
        # We only want the search plugins to run
        # a maximum set amount of time before giving up.
        self.hang_check += 1
        if self.hang_check >= HANG_TIME:
            self.search_pool.abort()
            self.checker.stop()
            self.pi.stopAnimation()
        else:
            # Stop the checker if not threads are running.
            if not self.search_pool.threads_running() and not self.search_pool.has_tasks():
                self.checker.stop()
                self.pi.stopAnimation()

        while self.search_pool.has_results():
            res, store_plugin = self.search_pool.get_result()
            if res:
                self.results_view.model().add_result(res, store_plugin)

    def open_store(self, index):
        result = self.results_view.model().get_result(index)
        self.store_plugins[result.store_name].open(self, result.detail_item)

    def get_store_checks(self):
        '''
        Returns a list of QCheckBox's for each store.
        '''
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

    def dialog_closed(self, result):
        self.model.closing()
        self.search_pool.abort()
        self.save_state()


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

    def add_task(self):
        raise NotImplementedError()

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
                    self.results.put((res, store_plugin))
                self.tasks.task_done()
            except:
                traceback.print_exc()


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


class DetailsThreadPool(GenericDownloadThreadPool):
    '''
    Once started all threads run until abort is called.
    '''

    def add_task(self, search_result, store_plugin, update_callback, timeout=10):
        self.tasks.put((search_result, store_plugin, update_callback, timeout))


class DetailsThread(Thread):
    
    def __init__(self, tasks, results):
        Thread.__init__(self)
        self.daemon = True
        self.tasks = tasks
        self.results = results
        self._run = True

    def abort(self):
        self._run = False

    def run(self):
        while self._run:
            try:
                time.sleep(.1)
                while not self.tasks.empty():
                    if not self._run:
                        break
                    result, store_plugin, callback, timeout = self.tasks.get()
                    if result:
                        store_plugin.get_details(result, timeout)
                        callback(result)
                    self.tasks.task_done()
            except:
                continue

class Matches(QAbstractItemModel):

    HEADERS = [_('Cover'), _('Title'), _('Author(s)'), _('Price'), _('DRM'), _('Store'), _('Formats')]

    def __init__(self):
        QAbstractItemModel.__init__(self)
        
        self.DRM_LOCKED_ICON = QPixmap(I('drm-locked.png')).scaledToHeight(64)
        self.DRM_UNLOCKED_ICON = QPixmap(I('drm-unlocked.png')).scaledToHeight(64)
        self.DRM_UNKNOWN_ICON = QPixmap(I('dialog_warning.png')).scaledToHeight(64)
        
        # All matches. Used to determine the order to display
        # self.matches because the SearchFilter returns
        # matches unordered.
        self.all_matches = []
        # Only the showing matches.
        self.matches = []
        self.query = ''
        self.search_filter = SearchFilter()
        self.cover_pool = CoverThreadPool(CoverThread, 2)
        self.cover_pool.start_threads()
        self.details_pool = DetailsThreadPool(DetailsThread, 4)
        self.details_pool.start_threads()

    def closing(self):
        self.cover_pool.abort()
        self.details_pool.abort()

    def clear_results(self):
        self.all_matches = []
        self.matches = []
        self.all_matches = []
        self.search_filter.clear_search_results()
        self.query = ''
        self.cover_pool.abort()
        self.cover_pool.start_threads()
        self.details_pool.abort()
        self.details_pool.start_threads()
        self.reset()

    def add_result(self, result, store_plugin):
        self.layoutAboutToBeChanged.emit()
        self.all_matches.append(result)
        self.search_filter.add_search_result(result)
        if result.cover_url:
            result.cover_queued = True
            self.cover_pool.add_task(result, self.filter_results)
        else:
            result.cover_queued = False
        self.details_pool.add_task(result, store_plugin, self.got_result_details)
        self.filter_results()
        self.layoutChanged.emit()

    def get_result(self, index):
        row = index.row()
        if row < len(self.matches):
            return self.matches[row]
        else:
            return None
        
    def filter_results(self):
        self.layoutAboutToBeChanged.emit()
        if self.query:
            self.matches = list(self.search_filter.parse(self.query))
        else:
            self.matches = list(self.search_filter.universal_set())
        self.reorder_matches()
        self.layoutChanged.emit()

    def got_result_details(self, result):
        if not result.cover_queued and result.cover_url:
            result.cover_queued = True
            self.cover_pool.add_task(result, self.filter_results)
        if result in self.matches:
            row = self.matches.index(result)
            self.dataChanged.emit(self.index(row, 0), self.index(row, self.columnCount() - 1))
        if result.drm not in (SearchResult.DRM_LOCKED, SearchResult.DRM_UNLOCKED, SearchResult.DRM_UNKNOWN):
            result.drm = SearchResult.DRM_UNKNOWN
        self.filter_results()

    def set_query(self, query):
        self.query = query

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
            elif col == 5:
                return QVariant(result.store_name)
            elif col == 6:
                return QVariant(result.formats)
            return NONE
        elif role == Qt.DecorationRole:
            if col == 0 and result.cover_data:
                p = QPixmap()
                p.loadFromData(result.cover_data)
                return QVariant(p)
            if col == 4:
                if result.drm == SearchResult.DRM_LOCKED:
                    return QVariant(self.DRM_LOCKED_ICON)
                elif result.drm == SearchResult.DRM_UNLOCKED:
                    return QVariant(self.DRM_UNLOCKED_ICON)
                elif result.drm == SearchResult.DRM_UNKNOWN:
                    return QVariant(self.DRM_UNKNOWN_ICON)
        elif role == Qt.ToolTipRole:
            if col == 1:
                return QVariant('<p>%s</p>' % result.title)
            elif col == 2:
                return QVariant('<p>%s</p>' % result.author)
            elif col == 3:
                return QVariant('<p>' + _('Detected price as: %s. Check with the store before making a purchase to verify this price is correct. This price often does not include promotions the store may be running.') % result.price + '</p>')
            elif col == 4:
                if result.drm == SearchResult.DRM_LOCKED:
                    return QVariant('<p>' + _('This book as been detected as having DRM restrictions. This book may not work with your reader and you will have limitations placed upon you as to what you can do with this book. Check with the store before making any purchases to ensure you can actually read this book.') + '</p>')
                elif result.drm == SearchResult.DRM_UNLOCKED:
                    return QVariant('<p>' + _('This book has been detected as being DRM Free. You should be able to use this book on any device provided it is in a format calibre supports for conversion. However, before making a purchase double check the DRM status with the store. The store may not be disclosing the use of DRM.') + '</p>')
                else:
                    return QVariant('<p>' + _('The DRM status of this book could not be determined. There is a very high likelihood that this book is actually DRM restricted.') + '</p>')
            elif col == 5:
                return QVariant('<p>%s</p>' % result.store_name)
            elif col == 6:
                return QVariant('<p>%s</p>' % result.formats)
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
            text = comparable_price(result.price)
        elif col == 4:
            if result.drm == SearchResult.DRM_UNLOCKED:
                text = 'a'
            elif result.drm == SearchResult.DRM_LOCKED:
                text = 'b'
            else:
                text = 'c'
        elif col == 5:
            text = result.store_name
        elif col == 6:
            text = ', '.join(sorted(result.formats.split(',')))
        return text

    def sort(self, col, order, reset=True):
        if not self.matches:
            return
        descending = order == Qt.DescendingOrder
        self.all_matches.sort(None,
            lambda x: sort_key(unicode(self.data_as_text(x, col))),
            descending)
        self.reorder_matches()
        if reset:
            self.reset()
            
    def reorder_matches(self):
        self.matches = sorted(self.matches, key=lambda x: self.all_matches.index(x))


class SearchFilter(SearchQueryParser):
    
    USABLE_LOCATIONS = [
        'all',
        'author',
        'authors',
        'cover',
        'drm',
        'format',
        'formats',
        'price',
        'title',
        'store',
    ]

    def __init__(self):
        SearchQueryParser.__init__(self, locations=self.USABLE_LOCATIONS)
        self.srs = set([])

    def add_search_result(self, search_result):
        self.srs.add(search_result)
        
    def clear_search_results(self):
        self.srs = set([])

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
             'cover': lambda x: x.cover_url,
             'drm': lambda x: x.drm,
             'format': lambda x: x.formats,
             'price': lambda x: comparable_price(x.price),
             'store': lambda x: x.store_name.lower(),
             'title': lambda x: x.title.lower(),
        }
        for x in ('author', 'format'):
            q[x+'s'] = q[x]
        for sr in self.srs:
            for locvalue in locations:
                accessor = q[locvalue]
                if query == 'true':
                    if locvalue == 'drm':
                        if accessor(sr) == SearchResult.DRM_LOCKED:
                            matches.add(sr)
                    else:
                        if accessor(sr) is not None:
                            matches.add(sr)
                    continue
                if query == 'false':
                    if locvalue == 'drm':
                        if accessor(sr) == SearchResult.DRM_UNKNOWN:
                            matches.add(sr)
                    else:
                        if accessor(sr) is None:
                            matches.add(sr)
                    continue
                # this is bool, so can't match below
                if locvalue == 'drm':
                    continue
                try:
                    ### Can't separate authors because comma is used for name sep and author sep
                    ### Exact match might not get what you want. For that reason, turn author
                    ### exactmatch searches into contains searches.
                    if locvalue == 'author' and matchkind == EQUALS_MATCH:
                        m = CONTAINS_MATCH
                    else:
                        m = matchkind
    
                    if locvalue == 'format':
                        vals = accessor(sr).split(',')
                    else:
                        vals = [accessor(sr)]
                    if _match(query, vals, m):
                        matches.add(sr)
                        break
                except ValueError: # Unicode errors
                    traceback.print_exc()
        return matches
