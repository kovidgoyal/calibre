# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from qt.core import QGraphicsView, QSize

if TYPE_CHECKING:
    from qt.core import QWidget


class BookView(QGraphicsView):
    MINIMUM_SIZE = QSize(400, 500)

    def __init__(self, parent: QWidget | None = None) -> None:
        QGraphicsView.__init__(self, parent)
        self.preferred_size = self.MINIMUM_SIZE

    def minimumSizeHint(self) -> QSize:
        return self.MINIMUM_SIZE

    def sizeHint(self) -> QSize:
        return self.preferred_size

    def resize_for(self, width: int, height: int) -> None:
        self.preferred_size = QSize(width, height)
