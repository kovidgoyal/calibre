#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

# Workaround a bunch of brain dead changes in PyQt6 that break backwards compat
# for no good reason. Since we have a huge body of poorly maintained third
# party plugin code, we NEED backward compat.

from qt.core import (
    QAction, QDialog, QDrag, QEventLoop, QMenu, QMessageBox, QSinglePointEvent,
    QThread, QModelIndex
)

from calibre_extensions import progress_indicator

# Restore removed functions from QMouseEvent
QSinglePointEvent.x = lambda self: int(self.position().x())
QSinglePointEvent.y = lambda self: int(self.position().y())
QSinglePointEvent.globalPos = lambda self: self.globalPosition().toPoint()
QSinglePointEvent.globalX = lambda self: self.globalPosition().toPoint().x()
QSinglePointEvent.globalY = lambda self: self.globalPosition().toPoint().y()
QSinglePointEvent.localPos = lambda self: self.position()
QSinglePointEvent.screenPos = lambda self: self.globalPosition()
QSinglePointEvent.windowPos = lambda self: self.scenePosition()


# Restore the removed exec_ method
QDialog.exec_ = QDialog.exec
QMenu.exec_ = QMenu.exec
QDrag.exec_ = QDrag.exec
QEventLoop.exec_ = QEventLoop.exec
QThread.exec_ = QThread.exec
QMessageBox.exec_ = QMessageBox.exec


# Restore ability to associate a menu with an action
QAction.setMenu = lambda self, menu: progress_indicator.set_menu_on_action(self, menu)
QAction.menu = lambda self, menu: progress_indicator.menu_for_action(self)


# Restore QModelIndex child
QModelIndex.child = lambda self, row, column: self.model().index(row, column, self)
