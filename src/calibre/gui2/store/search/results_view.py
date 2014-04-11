# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt5.Qt import (pyqtSignal, QMenu, QTreeView)

from calibre.gui2.metadata.single_download import RichTextDelegate
from calibre.gui2.store.search.models import Matches

class ResultsView(QTreeView):

    download_requested = pyqtSignal(object)
    open_requested = pyqtSignal(object)

    def __init__(self, *args):
        QTreeView.__init__(self,*args)

        self._model = Matches()
        self.setModel(self._model)

        self.rt_delegate = RichTextDelegate(self)

        for i in self._model.HTML_COLS:
            self.setItemDelegateForColumn(i, self.rt_delegate)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        
        if not index.isValid():
            return
        
        result = self.model().get_result(index)
        
        menu = QMenu()
        da = menu.addAction(_('Download...'), partial(self.download_requested.emit, result))
        if not result.downloads:
            da.setEnabled(False)
        menu.addSeparator()
        menu.addAction(_('Goto in store...'), partial(self.open_requested.emit, result))
        menu.exec_(event.globalPos())
