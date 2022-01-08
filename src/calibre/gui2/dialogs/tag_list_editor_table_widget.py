#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import (Qt, QTableWidget, pyqtSignal)


class TleTableWidget(QTableWidget):

    delete_pressed = pyqtSignal()

    def __init__(self, parent=None):
        QTableWidget.__init__(self, parent=parent)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_pressed.emit()
            event.accept()
            return
        return QTableWidget.keyPressEvent(self, event)
