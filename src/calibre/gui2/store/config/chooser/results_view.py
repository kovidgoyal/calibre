# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

from functools import partial

from qt.core import QMenu, QSize, Qt, QTreeView

from calibre.customize.ui import store_plugins
from calibre.gui2.metadata.single_download import RichTextDelegate
from calibre.gui2.store.config.chooser.models import Delegate, Matches
from calibre.utils.localization import _


class ResultsView(QTreeView):
    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)

        self._model = Matches(list(store_plugins()))
        self.setModel(self._model)

        self.setIconSize(QSize(24, 24))

        self.rt_delegate = RichTextDelegate(self)
        self.delegate = Delegate()
        self.setItemDelegate(self.delegate)

        for i in self._model.HTML_COLS:
            self.setItemDelegateForColumn(i, self.rt_delegate)

        for i in range(self._model.columnCount()):
            self.resizeColumnToContents(i)

        self._model.sort(1, Qt.SortOrder.AscendingOrder)
        _header = self.header()
        assert _header is not None
        _header.setSortIndicator(self._model.sort_col, self._model.sort_order)

    def contextMenuEvent(self, a0):
        index = self.indexAt(a0.pos())

        if not index.isValid():
            return

        _m = self.model()
        assert isinstance(_m, Matches)
        plugin = _m.get_plugin(index)

        menu = QMenu(self)
        ca = menu.addAction(_('Configure...'), partial(self.configure_plugin, plugin))
        if not plugin.is_customizable():
            assert ca is not None
            ca.setEnabled(False)
        menu.exec(a0.globalPos())

    def configure_plugin(self, plugin):
        plugin.do_user_config(self)
