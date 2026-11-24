#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from qt.core import Qt, QTableWidget, pyqtSignal

if TYPE_CHECKING:
    from qt.core import QKeyEvent, QWidget


class TleTableWidget(QTableWidget):
    delete_pressed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        QTableWidget.__init__(self, parent=parent)

    def keyPressEvent(self, e: QKeyEvent | None) -> None:
        if e is not None and e.key() == Qt.Key.Key_Delete:
            self.delete_pressed.emit()
            e.accept()
            return
        return QTableWidget.keyPressEvent(self, e)
