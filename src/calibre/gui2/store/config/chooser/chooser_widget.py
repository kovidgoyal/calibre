# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QWidget, QIcon, QDialog)

from calibre.gui2.store.config.chooser.adv_search_builder import AdvSearchBuilderDialog
from calibre.gui2.store.config.chooser.chooser_widget_ui import Ui_Form

class StoreChooserWidget(QWidget, Ui_Form):
    
    def __init__(self):
        QWidget.__init__(self)
        self.setupUi(self)
        
        self.adv_search_builder.setIcon(QIcon(I('search.png')))
        
        self.search.clicked.connect(self.do_search)
        self.adv_search_builder.clicked.connect(self.build_adv_search)
        self.results_view.activated.connect(self.toggle_plugin)

    def do_search(self):
        self.results_view.model().search(unicode(self.query.text()))

    def toggle_plugin(self, index):
        self.results_view.model().toggle_plugin(index)

    def build_adv_search(self):
        adv = AdvSearchBuilderDialog(self)
        if adv.exec_() == QDialog.Accepted:
            self.query.setText(adv.search_string())
