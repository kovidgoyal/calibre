#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

# Workaround a bunch of brain dead changes in PyQt6 that break backwards compat
# for no good reason. Since we have a huge body of poorly maintained third
# party plugin code, we NEED backward compat.

from qt.core import (
    QAbstractItemView, QAction, QComboBox, QDialog, QDialogButtonBox, QDrag,
    QDropEvent, QEvent, QEventLoop, QFontMetrics, QFormLayout, QFrame, QHoverEvent,
    QImage, QIODevice, QLayout, QLineEdit, QMenu, QMessageBox, QModelIndex, QPalette,
    QSinglePointEvent, QSizePolicy, Qt, QThread, QToolButton
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
QDropEvent.pos = lambda self: self.position().toPoint()
QDropEvent.posF = lambda self: self.position()
QHoverEvent.pos = lambda self: self.position().toPoint()
QHoverEvent.posF = lambda self: self.position()


# Restore the removed exec_ method

def exec_(self):
    return self.exec()


QDialog.exec_ = exec_
QMenu.exec_ = exec_
QDrag.exec_ = exec_
QEventLoop.exec_ = exec_
QThread.exec_ = exec_
QMessageBox.exec_ = exec_


# Restore ability to associate a menu with an action
def set_menu(self, menu):
    self.keep_menu_ref = menu
    progress_indicator.set_menu_on_action(self, menu)


QAction.setMenu = set_menu
QAction.menu = lambda self: progress_indicator.menu_for_action(self)


# Restore QModelIndex::child
QModelIndex.child = lambda self, row, column: self.model().index(row, column, self)


# Restore QFontMetrics::width
QFontMetrics.width = lambda self, text: self.horizontalAdvance(text)

# Restore enum values to various classes
for cls in (
    Qt, QDialog, QToolButton, QAbstractItemView, QDialogButtonBox, QFrame, QComboBox,
    QLineEdit, QAction, QImage, QIODevice, QPalette, QFormLayout, QEvent, QMessageBox,
    QSizePolicy, QLayout
):
    for var in tuple(vars(cls).values()):
        m = getattr(var, '__members__', {})
        for k, v in m.items():
            if not hasattr(cls, k):
                setattr(cls, k, v)
