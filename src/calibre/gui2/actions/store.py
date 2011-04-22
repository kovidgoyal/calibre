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
        self.config = JSONConfig('store_action')

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
            info_dialog(self.gui, _('About Get Books'), '<p>' +
            _('Calibre helps you find the ebooks you want by searching '
            'the websites of a variety of commercial and public domain '
            'book sources for you.') +
            '<p>' +
            _('Using the integrated search you can easily find which '
            'store has the book you are looking for, at the best price. '
            'You will also get DRM status and other useful information.')
            + '<p>' +
            _('All transactions (paid or otherwise) are handled between '
            'you and the particular website. '
            'Calibre is not part of this process and any issues related '
            'to a purchase should be directed to the website you are '
            'buying from. Be sure to double check that any books you get '
            'will work with your e-book reader, especially if the book you '
            'are buying has '
            '<a href="http://drmfree.calibre-ebook.com/about#drm">DRM</a>.'
            ), show=True, show_copy_button=False)
