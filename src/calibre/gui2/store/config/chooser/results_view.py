# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (Qt, QTreeView, QSize)

from calibre.customize.ui import store_plugins
from calibre.gui2.metadata.single_download import RichTextDelegate
from calibre.gui2.store.config.chooser.models import Matches

class ResultsView(QTreeView):

    def __init__(self, *args):
        QTreeView.__init__(self,*args)
            
        self._model = Matches([p for p in store_plugins()])
        self.setModel(self._model)
        
        self.setIconSize(QSize(24, 24))

        self.rt_delegate = RichTextDelegate(self)

        for i in self._model.HTML_COLS:
            self.setItemDelegateForColumn(i, self.rt_delegate)

        for i in xrange(self._model.columnCount()):
            self.resizeColumnToContents(i)
            
        self.model().sort(1, Qt.AscendingOrder)
        self.header().setSortIndicator(self.model().sort_col, self.model().sort_order)
