# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QTreeView)

from calibre.gui2.metadata.single_download import RichTextDelegate


class ResultsView(QTreeView):

    def __init__(self, *args):
        QTreeView.__init__(self,*args)
        
        from search import Matches
        self._model = Matches()
        self.setModel(self._model)

        self.rt_delegate = RichTextDelegate(self)
        
        for i in self._model.HTML_COLS:
            self.setItemDelegateForColumn(i, self.rt_delegate)

