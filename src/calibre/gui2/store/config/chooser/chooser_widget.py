# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QWidget, QIcon, QDialog, QComboBox, QLineEdit

from calibre.gui2.store.config.chooser.adv_search_builder import AdvSearchBuilderDialog
from calibre.gui2.store.config.chooser.chooser_widget_ui import Ui_Form
from polyglot.builtins import unicode_type


class StoreChooserWidget(QWidget, Ui_Form):

    def __init__(self):
        QWidget.__init__(self)
        self.setupUi(self)

        self.query.initialize('store_config_chooser_query')
        self.query.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.query.setMinimumContentsLength(25)
        self.adv_search_action = ac = self.query.lineEdit().addAction(QIcon(I('gear.png')), QLineEdit.LeadingPosition)
        ac.triggered.connect(self.build_adv_search)
        ac.setToolTip(_('Advanced search'))
        self.search.clicked.connect(self.do_search)
        self.enable_all.clicked.connect(self.results_view.model().enable_all)
        self.enable_none.clicked.connect(self.results_view.model().enable_none)
        self.enable_invert.clicked.connect(self.results_view.model().enable_invert)
        self.results_view.activated.connect(self.results_view.model().toggle_plugin)

    def do_search(self):
        self.results_view.model().search(unicode_type(self.query.text()))

    def build_adv_search(self):
        adv = AdvSearchBuilderDialog(self)
        if adv.exec_() == QDialog.Accepted:
            self.query.setText(adv.search_string())
