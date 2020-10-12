# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt5.Qt import (
    pyqtSignal, QMenu, QTreeView, QStyledItemDelegate, Qt, QIcon)

from calibre import fit_image
from calibre.gui2 import empty_index
from calibre.gui2.metadata.single_download import RichTextDelegate
from calibre.gui2.store.search.models import Matches


class ImageDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, empty_index)
        img = index.data(Qt.DecorationRole)
        if img:
            h = option.rect.height() - 4
            w = option.rect.width()
            if isinstance(img, QIcon):
                img = img.pixmap(h - 4, h - 4)
                dpr = img.devicePixelRatio()
            else:
                dpr = img.devicePixelRatio()
                scaled, nw, nh = fit_image(img.width(), img.height(), w, h)
                if scaled:
                    img = img.scaled(nw*dpr, nh*dpr, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            iw, ih = int(img.width()/dpr), int(img.height()/dpr)
            dx, dy = (option.rect.width() - iw) // 2, (option.rect.height() - ih) // 2
            painter.drawPixmap(option.rect.adjusted(dx, dy, -dx, -dy), img)


class ResultsView(QTreeView):

    download_requested = pyqtSignal(object)
    open_requested = pyqtSignal(object)

    def __init__(self, *args):
        QTreeView.__init__(self,*args)

        self._model = Matches()
        self.setModel(self._model)

        self.rt_delegate = RichTextDelegate(self)
        self.img_delegate = ImageDelegate(self)

        for i in self._model.HTML_COLS:
            self.setItemDelegateForColumn(i, self.rt_delegate)
        for i in self._model.IMG_COLS:
            self.setItemDelegateForColumn(i, self.img_delegate)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())

        if not index.isValid():
            return

        result = self.model().get_result(index)

        menu = QMenu(self)
        da = menu.addAction(_('Download...'), partial(self.download_requested.emit, result))
        if not result.downloads:
            da.setEnabled(False)
        menu.addSeparator()
        menu.addAction(_('Goto in store...'), partial(self.open_requested.emit, result))
        menu.exec_(event.globalPos())
