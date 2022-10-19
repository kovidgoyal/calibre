# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals


__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


from qt.core import Qt, QDialog, QIcon, QComboBox

from calibre.gui2.store.stores.mobileread.adv_search_builder import AdvSearchBuilderDialog
from calibre.gui2.store.stores.mobileread.models import BooksModel
from calibre.gui2.store.stores.mobileread.store_dialog_ui import Ui_Dialog


class MobileReadStoreDialog(QDialog, Ui_Dialog):

    def __init__(self, plugin, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)

        self.plugin = plugin
        self.search_query.initialize('store_mobileread_search')
        self.search_query.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.search_query.setMinimumContentsLength(25)

        self.adv_search_button.setIcon(QIcon.ic('search.png'))

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
        self.results_view.model().search(type(u'')(self.search_query.text()))

    def open_store(self, index):
        result = self.results_view.model().get_book(index)
        if result:
            self.plugin.open(self, result.detail_item)

    def update_book_total(self, total):
        self.total.setText('%s' % total)

    def build_adv_search(self):
        adv = AdvSearchBuilderDialog(self)
        if adv.exec() == QDialog.DialogCode.Accepted:
            self.search_query.setText(adv.search_string())

    def restore_state(self):
        self.restore_geometry(self.plugin.config, 'dialog_geometry')
        results_cwidth = self.plugin.config.get('dialog_results_view_column_width')
        if results_cwidth:
            for i, x in enumerate(results_cwidth):
                if i >= self.results_view.model().columnCount():
                    break
                self.results_view.setColumnWidth(i, x)
        else:
            for i in range(self.results_view.model().columnCount()):
                self.results_view.resizeColumnToContents(i)

        self.results_view.model().sort_col = self.plugin.config.get('dialog_sort_col', 0)
        self.results_view.model().sort_order = self.plugin.config.get('dialog_sort_order', Qt.SortOrder.AscendingOrder)
        self.results_view.model().sort(self.results_view.model().sort_col, self.results_view.model().sort_order)
        self.results_view.header().setSortIndicator(self.results_view.model().sort_col, self.results_view.model().sort_order)

    def save_state(self):
        self.save_geometry(self.plugin.config, 'dialog_geometry')
        self.plugin.config['dialog_results_view_column_width'] = [self.results_view.columnWidth(i) for i in range(self.results_view.model().columnCount())]
        self.plugin.config['dialog_sort_col'] = self.results_view.model().sort_col
        self.plugin.config['dialog_sort_order'] = self.results_view.model().sort_order

    def dialog_closed(self, result):
        self.save_state()
