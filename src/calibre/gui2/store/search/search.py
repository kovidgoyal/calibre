# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
from random import shuffle

from PyQt5.Qt import (Qt, QDialog, QDialogButtonBox, QTimer, QCheckBox, QLabel,
                      QVBoxLayout, QIcon, QWidget, QTabWidget, QGridLayout)

from calibre.gui2 import JSONConfig, info_dialog, error_dialog
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.gui2.ebook_download import show_download_info
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.store.config.chooser.chooser_widget import StoreChooserWidget
from calibre.gui2.store.config.search.search_widget import StoreConfigWidget
from calibre.gui2.store.search.adv_search_builder import AdvSearchBuilderDialog
from calibre.gui2.store.search.download_thread import SearchThreadPool, \
    CacheUpdateThreadPool
from calibre.gui2.store.search.search_ui import Ui_Dialog
from calibre.utils.filenames import ascii_filename


class SearchDialog(QDialog, Ui_Dialog):

    SEARCH_TEXT = _('&Search')
    STOP_TEXT = _('&Stop')

    def __init__(self, gui, parent=None, query=''):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.config = JSONConfig('store/search')
        self.search_title.initialize('store_search_search_title')
        self.search_author.initialize('store_search_search_author')
        self.search_edit.initialize('store_search_search')

        # Loads variables that store various settings.
        # This needs to be called soon in __init__ because
        # the variables it sets up are used later.
        self.load_settings()

        self.gui = gui

        # Setup our worker threads.
        self.search_pool = SearchThreadPool(self.search_thread_count)
        self.cache_pool = CacheUpdateThreadPool(self.cache_thread_count)
        self.results_view.model().cover_pool.set_thread_count(self.cover_thread_count)
        self.results_view.model().details_pool.set_thread_count(self.details_thread_count)
        self.results_view.setCursor(Qt.PointingHandCursor)

        # Check for results and hung threads.
        self.checker = QTimer()
        self.progress_checker = QTimer()
        self.hang_check = 0

        # Update store caches silently.
        for p in self.gui.istores.values():
            self.cache_pool.add_task(p, self.timeout)

        self.store_checks = {}
        self.setup_store_checks()

        # Set the search query
        if isinstance(query, (str, unicode)):
            self.search_edit.setText(query)
        elif isinstance(query, dict):
            if 'author' in query:
                self.search_author.setText(query['author'])
            if 'title' in query:
                self.search_title.setText(query['title'])

        # Create and add the progress indicator
        self.pi = ProgressIndicator(self, 24)
        self.button_layout.takeAt(0)
        self.button_layout.setAlignment(Qt.AlignCenter)
        self.button_layout.insertWidget(0, self.pi, 0, Qt.AlignCenter)

        self.adv_search_button.setIcon(QIcon(I('gear.png')))
        self.adv_search_button.setToolTip(_('Advanced search'))
        self.configure.setIcon(QIcon(I('config.png')))

        self.adv_search_button.clicked.connect(self.build_adv_search)
        self.search.clicked.connect(self.toggle_search)
        self.checker.timeout.connect(self.get_results)
        self.progress_checker.timeout.connect(self.check_progress)
        self.results_view.activated.connect(self.result_item_activated)
        self.results_view.download_requested.connect(self.download_book)
        self.results_view.open_requested.connect(self.open_store)
        self.results_view.model().total_changed.connect(self.update_book_total)
        self.select_all_stores.clicked.connect(self.stores_select_all)
        self.select_invert_stores.clicked.connect(self.stores_select_invert)
        self.select_none_stores.clicked.connect(self.stores_select_none)
        self.configure.clicked.connect(self.do_config)
        self.finished.connect(self.dialog_closed)
        self.searching = False

        self.progress_checker.start(100)

        self.restore_state()

    def setup_store_checks(self):
        first_run = self.config.get('first_run', True)

        # Add check boxes for each store so the user
        # can disable searching specific stores on a
        # per search basis.
        existing = {}
        for n in self.store_checks:
            existing[n] = self.store_checks[n].isChecked()

        self.store_checks = {}

        stores_check_widget = QWidget()
        store_list_layout = QGridLayout()
        stores_check_widget.setLayout(store_list_layout)

        icon = QIcon(I('donate.png'))
        for i, x in enumerate(sorted(self.gui.istores.keys(), key=lambda x: x.lower())):
            cbox = QCheckBox(x)
            cbox.setChecked(existing.get(x, first_run))
            store_list_layout.addWidget(cbox, i, 0, 1, 1)
            if self.gui.istores[x].base_plugin.affiliate:
                iw = QLabel(self)
                iw.setToolTip('<p>' + _('Buying from this store supports the calibre developer: %s</p>') % self.gui.istores[x].base_plugin.author + '</p>')
                iw.setPixmap(icon.pixmap(16, 16))
                store_list_layout.addWidget(iw, i, 1, 1, 1)
            self.store_checks[x] = cbox
        store_list_layout.setRowStretch(store_list_layout.rowCount(), 10)
        self.store_list.setWidget(stores_check_widget)

        self.config['first_run'] = False

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
        self.results_view.setColumnWidth(2,int(total*.12))
        # DRM
        self.results_view.setColumnWidth(3, int(total*.15))
        # Store / Formats
        self.results_view.setColumnWidth(4, int(total*.25))
        # Download
        self.results_view.setColumnWidth(5, 20)
        # Affiliate
        self.results_view.setColumnWidth(6, 20)

    def toggle_search(self):
        if self.searching:
            self.search_pool.abort()
            m = self.results_view.model()
            m.details_pool.abort()
            m.cover_pool.abort()
            self.search.setText(self.SEARCH_TEXT)
            self.checker.stop()
            self.searching = False
        else:
            self.do_search()
        # Prevent hitting the enter key twice in quick succession causing
        # the search to start and stop
        self.search.setEnabled(False)
        QTimer.singleShot(1000, lambda :self.search.setEnabled(True))

    def do_search(self):
        # Stop all running threads.
        self.checker.stop()
        self.search_pool.abort()
        # Clear the visible results.
        self.results_view.model().clear_results()

        # Don't start a search if there is nothing to search for.
        query = []
        if self.search_title.text():
            query.append(u'title2:"~%s"' % unicode(self.search_title.text()).replace('"', ' '))
        if self.search_author.text():
            query.append(u'author2:"%s"' % unicode(self.search_author.text()).replace('"', ' '))
        if self.search_edit.text():
            query.append(unicode(self.search_edit.text()))
        query = " ".join(query)
        if not query.strip():
            error_dialog(self, _('No query'),
                        _('You must enter a title, author or keyword to'
                          ' search for.'), show=True)
            return
        self.searching = True
        self.search.setText(self.STOP_TEXT)
        # Give the query to the results model so it can do
        # futher filtering.
        self.results_view.model().set_query(query)

        # Plugins are in random order that does not change.
        # Randomize the ord of the plugin names every time
        # there is a search. This way plugins closer
        # to a don't have an unfair advantage over
        # plugins further from a.
        store_names = self.store_checks.keys()
        if not store_names:
            return
        # Remove all of our internal filtering logic from the query.
        query = self.clean_query(query)
        shuffle(store_names)
        # Add plugins that the user has checked to the search pool's work queue.
        self.gui.istores.join(4.0)  # Wait for updated plugins to load
        for n in store_names:
            if self.store_checks[n].isChecked():
                self.search_pool.add_task(query, n, self.gui.istores[n], self.max_results, self.timeout)
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
        for loc in ('all', 'author', 'author2', 'authors', 'title', 'title2'):
            query = re.sub(r'%s:"(?P<a>[^\s"]+)"' % loc, '\g<a>', query)
            query = query.replace('%s:' % loc, '')
        # Remove the prefix and search text.
        for loc in ('cover', 'download', 'downloads', 'drm', 'format', 'formats', 'price', 'store'):
            query = re.sub(r'%s:"[^"]"' % loc, '', query)
            query = re.sub(r'%s:[^\s]*' % loc, '', query)
        # Remove logic.
        query = re.sub(r'(^|\s|")(and|not|or|a|the|is|of)(\s|$|")', r' ', query)
        # Remove "
        query = query.replace('"', '')
        # Remove excess whitespace.
        query = re.sub(r'\s+', ' ', query)
        query = query.strip()
        return query.encode('utf-8')

    def save_state(self):
        self.config['geometry'] = bytearray(self.saveGeometry())
        self.config['store_splitter_state'] = bytearray(self.store_splitter.saveState())
        self.config['results_view_column_width'] = [self.results_view.columnWidth(i) for i in range(self.results_view.model().columnCount())]
        self.config['sort_col'] = self.results_view.model().sort_col
        self.config['sort_order'] = self.results_view.model().sort_order
        self.config['open_external'] = self.open_external.isChecked()

        store_check = {}
        for k, v in self.store_checks.items():
            store_check[k] = v.isChecked()
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

        self.open_external.setChecked(self.should_open_external)

        store_check = self.config.get('store_checked', None)
        if store_check:
            for n in store_check:
                if n in self.store_checks:
                    self.store_checks[n].setChecked(store_check[n])

        self.results_view.model().sort_col = self.config.get('sort_col', 2)
        self.results_view.model().sort_order = self.config.get('sort_order', Qt.AscendingOrder)
        self.results_view.header().setSortIndicator(self.results_view.model().sort_col, self.results_view.model().sort_order)

    def load_settings(self):
        # Seconds
        self.timeout = self.config.get('timeout', 75)
        # Milliseconds
        self.hang_time = self.config.get('hang_time', 75) * 1000

        self.max_results = self.config.get('max_results', 15)
        self.should_open_external = self.config.get('open_external', True)

        # Number of threads to run for each type of operation
        self.search_thread_count = self.config.get('search_thread_count', 4)
        self.cache_thread_count = self.config.get('cache_thread_count', 2)
        self.cover_thread_count = self.config.get('cover_thread_count', 2)
        self.details_thread_count = self.config.get('details_thread_count', 4)

    def do_config(self):
        # Save values that need to be synced between the dialog and the
        # search widget.
        self.config['open_external'] = self.open_external.isChecked()

        # Create the config dialog. It's going to put two config widgets
        # into a QTabWidget for displaying all of the settings.
        d = QDialog(self)
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        v = QVBoxLayout(d)
        button_box.accepted.connect(d.accept)
        button_box.rejected.connect(d.reject)
        d.setWindowTitle(_('Customize Get books search'))

        tab_widget = QTabWidget(d)
        v.addWidget(tab_widget)
        v.addWidget(button_box)

        chooser_config_widget = StoreChooserWidget()
        search_config_widget = StoreConfigWidget(self.config)

        tab_widget.addTab(chooser_config_widget, _('Choose s&tores'))
        tab_widget.addTab(search_config_widget, _('Configure s&earch'))

        # Restore dialog state.
        geometry = self.config.get('config_dialog_geometry', None)
        if geometry:
            d.restoreGeometry(geometry)
        else:
            d.resize(800, 600)
        tab_index = self.config.get('config_dialog_tab_index', 0)
        tab_index = min(tab_index, tab_widget.count() - 1)
        tab_widget.setCurrentIndex(tab_index)

        d.exec_()

        # Save dialog state.
        self.config['config_dialog_geometry'] = bytearray(d.saveGeometry())
        self.config['config_dialog_tab_index'] = tab_widget.currentIndex()

        search_config_widget.save_settings()
        self.config_changed()
        self.gui.load_store_plugins()
        self.setup_store_checks()

    def config_changed(self):
        self.load_settings()

        self.open_external.setChecked(self.should_open_external)
        self.search_pool.set_thread_count(self.search_thread_count)
        self.cache_pool.set_thread_count(self.cache_thread_count)
        self.results_view.model().cover_pool.set_thread_count(self.cover_thread_count)
        self.results_view.model().details_pool.set_thread_count(self.details_thread_count)

    def get_results(self):
        # We only want the search plugins to run
        # a maximum set amount of time before giving up.
        self.hang_check += 1
        if self.hang_check >= self.hang_time:
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

    def update_book_total(self, total):
        self.total.setText('%s' % total)

    def result_item_activated(self, index):
        result = self.results_view.model().get_result(index)

        if result.downloads:
            self.download_book(result)
        else:
            self.open_store(result)

    def download_book(self, result):
        d = ChooseFormatDialog(self, _('Choose format to download to your library.'), result.downloads.keys())
        if d.exec_() == d.Accepted:
            ext = d.format()
            fname = result.title[:60] + '.' + ext.lower()
            fname = ascii_filename(fname)
            show_download_info(result.title, parent=self)
            self.gui.download_ebook(result.downloads[ext], filename=fname, create_browser=result.create_browser)

    def open_store(self, result):
        self.gui.istores[result.store_name].open(self, result.detail_item, self.open_external.isChecked())

    def check_progress(self):
        m = self.results_view.model()
        if not self.search_pool.threads_running() and not m.cover_pool.threads_running() and not m.details_pool.threads_running():
            self.pi.stopAnimation()
            self.search.setText(self.SEARCH_TEXT)
            self.searching = False
        else:
            self.searching = True
            if unicode(self.search.text()) != self.STOP_TEXT:
                self.search.setText(self.STOP_TEXT)
            if not self.pi.isAnimated():
                self.pi.startAnimation()

    def stores_select_all(self):
        for check in self.store_checks.values():
            check.setChecked(True)

    def stores_select_invert(self):
        for check in self.store_checks.values():
            check.setChecked(not check.isChecked())

    def stores_select_none(self):
        for check in self.store_checks.values():
            check.setChecked(False)

    def dialog_closed(self, result):
        self.results_view.model().closing()
        self.search_pool.abort()
        self.cache_pool.abort()
        self.save_state()

    def exec_(self):
        if unicode(self.search_edit.text()).strip() or unicode(self.search_title.text()).strip() or unicode(self.search_author.text()).strip():
            self.do_search()
        return QDialog.exec_(self)


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.preferences.main import init_gui
    import sys
    app = Application([])
    app
    gui = init_gui()

    s = SearchDialog(gui, query=' '.join(sys.argv[1:]))
    s.exec_()
