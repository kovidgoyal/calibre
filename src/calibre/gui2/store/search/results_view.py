# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

from functools import partial

from qt.core import QIcon, QMenu, QStyledItemDelegate, Qt, QTreeView, pyqtSignal

from calibre import fit_image
from calibre.gui2 import empty_index
from calibre.gui2.metadata.single_download import RichTextDelegate
from calibre.gui2.store.search.models import Matches
from calibre.utils.localization import _


class ImageDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, empty_index)
        img = index.data(Qt.ItemDataRole.DecorationRole)
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
                    img = img.scaled(
                        int(nw * dpr),
                        int(nh * dpr),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
            iw, ih = int(img.width() / dpr), int(img.height() / dpr)
            dx, dy = (option.rect.width() - iw) // 2, (option.rect.height() - ih) // 2
            painter.drawPixmap(option.rect.adjusted(dx, dy, -dx, -dy), img)


class ResultsView(QTreeView):
    download_requested = pyqtSignal(object)
    open_requested = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        QTreeView.__init__(self, *args, **kwargs)

        self._model = Matches()
        self.setModel(self._model)

        self.rt_delegate = RichTextDelegate(self)
        self.img_delegate = ImageDelegate(self)

        for i in self._model.HTML_COLS:
            self.setItemDelegateForColumn(i, self.rt_delegate)
        for i in self._model.IMG_COLS:
            self.setItemDelegateForColumn(i, self.img_delegate)

    def contextMenuEvent(self, a0):
        index = self.indexAt(a0.pos())

        if not index.isValid():
            return

        _m = self.model()
        assert isinstance(_m, Matches)
        result = _m.get_result(index)

        menu = QMenu(self)
        da = menu.addAction(_('Download...'), partial(self.download_requested.emit, result))
        assert da is not None
        if not result.downloads:
            da.setEnabled(False)
        menu.addSeparator()
        menu.addAction(_('Show in store'), partial(self.open_requested.emit, result))
        menu.exec(a0.globalPos())
