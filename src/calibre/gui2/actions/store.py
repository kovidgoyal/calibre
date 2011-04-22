# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QMenu

from calibre.gui2 import JSONConfig
from calibre.gui2.actions import InterfaceAction

class StoreAction(InterfaceAction):

    name = 'Store'
    action_spec = (_('Get books'), 'store.png', None, None)

    def genesis(self):
        self.config = JSONConfig('store/action')

        self.qaction.triggered.connect(self.search)
        self.store_menu = QMenu()
        self.load_menu()

    def load_menu(self):
        self.store_menu.clear()
        self.store_menu.addAction(_('Search'), self.search)
        self.store_menu.addSeparator()
        for n, p in self.gui.istores.items():
            self.store_menu.addAction(n, partial(self.open_store, p))
        self.qaction.setMenu(self.store_menu)

    def search(self):
        self.first_run_check()
        from calibre.gui2.store.search import SearchDialog
        sd = SearchDialog(self.gui.istores, self.gui)
        sd.exec_()

    def open_store(self, store_plugin):
        self.first_run_check()
        store_plugin.open(self.gui)

    def first_run_check(self):
        if self.config.get('first_run', True):
            self.config['first_run'] = False
            from calibre.gui2 import info_dialog
            info_dialog(self.gui, _('Get Books Disclaimer'),
                _('<p>Calibre helps you find books to read by connecting you with outside stores. '
                'The stores are a variety of big, independent, free, and public domain sources.</p>'
                '<p>Using the integrated search you can easily find what store has the book you\'re '
                'looking for. It will also give you a price, DRM status as well as a lot of '
                'other useful information.</p>'
                '<p>All transaction (paid or otherwise) are handled between you and the store. '
                'Calibre is not part of this process and any issues related to a purchase need to '
                'be directed to the actual store. Be sure to double check that any books you get '
                'will work with you device. Double check for format and '
                '<a href="http://en.wikipedia.org/wiki/Digital_rights_management">DRM</a> '
                'restrictions.</p>'),
                show=True, show_copy_button=False)
