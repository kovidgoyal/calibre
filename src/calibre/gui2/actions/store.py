# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import Qt, QMenu, QToolButton, QDialog, QVBoxLayout

from calibre.gui2.actions import InterfaceAction

class StoreAction(InterfaceAction):

    name = 'Store'
    action_spec = (_('Store'), None, None, None)
    
    def genesis(self):
        self.qaction.triggered.connect(self.search)
        self.store_menu = QMenu()
        self.store_menu.addAction(_('Search'), self.search)
        self.store_menu.addSeparator()
        for n, p in self.gui.istores.items():
            self.store_menu.addAction(n, partial(self.open_store, p))
        self.qaction.setMenu(self.store_menu)
    
    def search(self):
        from calibre.gui2.store.search import SearchDialog
        sd = SearchDialog(self.gui.istores, self.gui)
        sd.exec_()
        
    def open_store(self, store_plugin):
        store_plugin.open(self.gui)
