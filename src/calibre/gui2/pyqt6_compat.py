#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

# Workaround a bunch of brain dead changes in PyQt6 that break backwards compat
# for no good reason. Since we have a huge body of poorly maintained third
# party plugin code, we NEED backward compat.

from qt.core import QSinglePointEvent


# Restore removed functions from QMouseEvent
QSinglePointEvent.x = lambda self: int(self.position().x())
QSinglePointEvent.y = lambda self: int(self.position().y())
QSinglePointEvent.globalPos = lambda self: self.globalPosition.toPoint()
QSinglePointEvent.globalX = lambda self: self.globalPosition.toPoint().x()
QSinglePointEvent.globalY = lambda self: self.globalPosition.toPoint().y()
QSinglePointEvent.localPos = lambda self: self.position()
QSinglePointEvent.screenPos = lambda self: self.globalPosition()
QSinglePointEvent.windowPos = lambda self: self.scenePosition()
