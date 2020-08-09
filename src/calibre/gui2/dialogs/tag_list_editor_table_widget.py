#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

from PyQt5.Qt import (Qt, QTableWidget, pyqtSignal)


class TleTableWidget(QTableWidget):

    delete_pressed = pyqtSignal()

    def __init__(self, parent=None):
        QTableWidget.__init__(self, parent=parent)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.delete_pressed.emit()
            event.accept()
            return
        return QTableWidget.keyPressEvent(self, event)
