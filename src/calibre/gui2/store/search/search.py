# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
from random import shuffle

from PyQt4.Qt import (Qt, QDialog, QTimer, QCheckBox, QVBoxLayout, QIcon, QWidget) 

from calibre.gui2 import JSONConfig, info_dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.store.search.adv_search_builder import AdvSearchBuilderDialog
from calibre.gui2.store.search.download_thread import SearchThreadPool, \
    CacheUpdateThreadPool
from calibre.gui2.store.search.search_ui import Ui_Dialog

HANG_TIME = 75000 # milliseconds seconds
TIMEOUT = 75 # seconds

class SearchDialog(QDialog, Ui_Dialog):

    def __init__(self, istores, parent=None, query=''):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.config = JSONConfig('store/search')
        
        self.search_edit.initialize('store_search_search')

        # We keep a cache of store plugins and reference them by name.
        self.store_plugins = istores
        self.search_pool = SearchThreadPool(4)
        self.cache_pool = CacheUpdateThreadPool(2)
        # Check for results and hung threads.
        self.checker = QTimer()
        self.progress_checker = QTimer()
        self.hang_check = 0
        
        # Update store caches silently.
        for p in self.store_plugins.values():
            self.cache_pool.add_task(p, 30)

        # Add check boxes for each store so the user
        # can disable searching specific stores on a
        # per search basis.
        stores_check_widget = QWidget()
        stores_group_layout = QVBoxLayout()
        stores_check_widget.setLayout(stores_group_layout)
        for x in sorted(self.store_plugins.keys(), key=lambda x: x.lower()):
            cbox = QCheckBox(x)
            cbox.setChecked(False)
            stores_group_layout.addWidget(cbox)
            setattr(self, 'store_check_' + x, cbox)
        stores_group_layout.addStretch()
        self.stores_group.setWidget(stores_check_widget)

        # Set the search query
        self.search_edit.setText(query)

        # Create and add the progress indicator
        self.pi = ProgressIndicator(self, 24)
        self.top_layout.addWidget(self.pi)
        
        self.adv_search_button.setIcon(QIcon(I('search.png')))

        self.adv_search_button.clicked.connect(self.build_adv_search)
        self.search.clicked.connect(self.do_search)
        self.checker.timeout.connect(self.get_results)
        self.progress_checker.timeout.connect(self.check_progress)
        self.results_view.activated.connect(self.open_store)
        self.select_all_stores.clicked.connect(self.stores_select_all)
        self.select_invert_stores.clicked.connect(self.stores_select_invert)
        self.select_none_stores.clicked.connect(self.stores_select_none)
        self.finished.connect(self.dialog_closed)

        self.progress_checker.start(100)

        self.restore_state()

    def build_adv_search(self):
        adv = AdvSearchBuilderDialog(self)
        if adv.exec_() == QDialog.Accepted:
            self.search_edit.setText(adv.search_string())

    def resize_columns(self):
        total = 600
        # Cover
        self.results_view.setColumnWidth(0, 85)
        total = total - 85
        # Title / Author
        self.results_view.setColumnWidth(1,int(total*.40))
        # Price
        self.results_view.setColumnWidth(2,int(total*.20))
        # DRM
        self.results_view.setColumnWidth(3, int(total*.15))
        # Store / Formats
        self.results_view.setColumnWidth(4, int(total*.25))

    def do_search(self):
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
        self.hang_check = 0
        self.checker.start(100)
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
        for loc in ('all', 'author', 'authors', 'title'):
            query = re.sub(r'%s:"(?P<a>[^\s"]+)"' % loc, '\g<a>', query)
            query = query.replace('%s:' % loc, '')
        # Remove the prefix and search text.
        for loc in ('cover', 'drm', 'format', 'formats', 'price', 'store'):
            query = re.sub(r'%s:"[^"]"' % loc, '', query)
            query = re.sub(r'%s:[^\s]*' % loc, '', query)
        # Remove logic.
        query = re.sub(r'(^|\s)(and|not|or|a|the|is|of)(\s|$)', ' ', query)
        # Remove "
        query = query.replace('"', '')
        # Remove excess whitespace.
        query = re.sub(r'\s{2,}', ' ', query)
        query = query.strip()
        return query

    def save_state(self):
        self.config['geometry'] = bytearray(self.saveGeometry())
        self.config['store_splitter_state'] = bytearray(self.store_splitter.saveState())
        self.config['results_view_column_width'] = [self.results_view.columnWidth(i) for i in range(self.results_view.model().columnCount())]
        self.config['sort_col'] = self.results_view.model().sort_col
        self.config['sort_order'] = self.results_view.model().sort_order
        self.config['open_external'] = self.open_external.isChecked()

        store_check = {}
        for n in self.store_plugins:
            store_check[n] = getattr(self, 'store_check_' + n).isChecked()
        self.config['store_checked'] = store_check

    def restore_state(self):
        geometry = self.config.get('geometry', None)
        if geometry:
            self.restoreGeometry(geometry)

        splitter_state = self.config.get('store_splitter_state', None)
        if splitter_state:
            self.store_splitter.restoreState(splitter_state)

        results_cwidth = self.config.get('results_view_column_width', None)
        if results_cwidth:
            for i, x in enumerate(results_cwidth):
                if i >= self.results_view.model().columnCount():
                    break
                self.results_view.setColumnWidth(i, x)
        else:
            self.resize_columns()

        self.open_external.setChecked(self.config.get('open_external', False))

        store_check = self.config.get('store_checked', None)
        if store_check:
            for n in store_check:
                if hasattr(self, 'store_check_' + n):
                    getattr(self, 'store_check_' + n).setChecked(store_check[n])
                    
        self.results_view.model().sort_col = self.config.get('sort_col', 2)
        self.results_view.model().sort_order = self.config.get('sort_order', Qt.AscendingOrder)
        self.results_view.header().setSortIndicator(self.results_view.model().sort_col, self.results_view.model().sort_order)         

    def get_results(self):
        # We only want the search plugins to run
        # a maximum set amount of time before giving up.
        self.hang_check += 1
        if self.hang_check >= HANG_TIME:
            self.search_pool.abort()
            self.checker.stop()
        else:
            # Stop the checker if not threads are running.
            if not self.search_pool.threads_running() and not self.search_pool.has_tasks():
                self.checker.stop()

        while self.search_pool.has_results():
            res, store_plugin = self.search_pool.get_result()
            if res:
                self.results_view.model().add_result(res, store_plugin)

        if not self.search_pool.threads_running() and not self.results_view.model().has_results():
            info_dialog(self, _('No matches'), _('Couldn\'t find any books matching your query.'), show=True, show_copy_button=False)


    def open_store(self, index):
        result = self.results_view.model().get_result(index)
        self.store_plugins[result.store_name].open(self, result.detail_item, self.open_external.isChecked())

    def check_progress(self):
        if not self.search_pool.threads_running() and not self.results_view.model().cover_pool.threads_running() and not self.results_view.model().details_pool.threads_running(): 
            self.pi.stopAnimation()
        else:
            if not self.pi.isAnimated():
                self.pi.startAnimation()

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
        self.results_view.model().closing()
        self.search_pool.abort()
        self.cache_pool.abort()
        self.save_state()
        
    def exec_(self):
        if unicode(self.search_edit.text()).strip():
            self.do_search()
        return QDialog.exec_(self)

