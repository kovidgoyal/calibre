__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from functools import partial

from qt.core import (Qt, QTreeView, QSize, QMenu)

from calibre.customize.ui import store_plugins
from calibre.gui2.metadata.single_download import RichTextDelegate
from calibre.gui2.store.config.chooser.models import Matches, Delegate


class ResultsView(QTreeView):

    def __init__(self, *args):
        QTreeView.__init__(self,*args)

        self._model = Matches([p for p in store_plugins()])
        self.setModel(self._model)

        self.setIconSize(QSize(24, 24))

        self.rt_delegate = RichTextDelegate(self)
        self.delegate = Delegate()
        self.setItemDelegate(self.delegate)

        for i in self._model.HTML_COLS:
            self.setItemDelegateForColumn(i, self.rt_delegate)

        for i in range(self._model.columnCount()):
            self.resizeColumnToContents(i)

        self.model().sort(1, Qt.SortOrder.AscendingOrder)
        self.header().setSortIndicator(self.model().sort_col, self.model().sort_order)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())

        if not index.isValid():
            return

        plugin = self.model().get_plugin(index)

        menu = QMenu(self)
        ca = menu.addAction(_('Configure...'), partial(self.configure_plugin, plugin))
        if not plugin.is_customizable():
            ca.setEnabled(False)
        menu.exec(event.globalPos())

    def configure_plugin(self, plugin):
        plugin.do_user_config(self)
