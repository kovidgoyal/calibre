# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QWidget

from calibre.gui2 import JSONConfig
from calibre.gui2.store.config.search.search_widget_ui import Ui_Form


class StoreConfigWidget(QWidget, Ui_Form):

    def __init__(self, config=None):
        QWidget.__init__(self)
        self.setupUi(self)

        self.config = JSONConfig('store/search') if not config else config

        # These default values should be the same as in
        # calibre.gui2.store.search.search:SearchDialog.load_settings
        # Seconds
        self.opt_timeout.setValue(self.config.get('timeout', 75))
        self.opt_hang_time.setValue(self.config.get('hang_time', 75))

        self.opt_max_results.setValue(self.config.get('max_results', 10))
        self.opt_open_external.setChecked(self.config.get('open_external', True))

        # Number of threads to run for each type of operation
        self.opt_search_thread_count.setValue(self.config.get('search_thread_count', 4))
        self.opt_cache_thread_count.setValue(self.config.get('cache_thread_count', 2))
        self.opt_cover_thread_count.setValue(self.config.get('cover_thread_count', 2))
        self.opt_details_thread_count.setValue(self.config.get('details_thread_count', 4))

    def save_settings(self):
        self.config['timeout'] = self.opt_timeout.value()
        self.config['hang_time'] = self.opt_hang_time.value()
        self.config['max_results'] = self.opt_max_results.value()
        self.config['open_external'] = self.opt_open_external.isChecked()
        self.config['search_thread_count'] = self.opt_search_thread_count.value()
        self.config['cache_thread_count'] = self.opt_cache_thread_count.value()
        self.config['cover_thread_count'] = self.opt_cover_thread_count.value()
        self.config['details_thread_count'] = self.opt_details_thread_count.value()
