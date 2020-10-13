#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from PyQt5.Qt import QBuffer, QByteArray, QPixmap, Qt, QtWin

from calibre.constants import plugins
from calibre.gui2 import must_use_qt
from calibre.utils.winreg.default_programs import split_commandline
from polyglot.builtins import filter

ICON_SIZE = 64
winutil = plugins['winutil'][0]


def hicon_to_pixmap(hicon):
    return QtWin.fromHICON(int(hicon))


def pixmap_to_data(pixmap):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pixmap.save(buf, 'PNG')
    return bytearray(ba.data())


def load_icon_resource(icon_resource, as_data=False, size=ICON_SIZE):
    if not icon_resource:
        return
    parts = tuple(filter(None, re.split(r',([-0-9]+$)', icon_resource)))
    if len(parts) != 2:
        return
    module, index = parts
    index = int(index)
    if module.startswith('"') and module.endswith('"'):
        module = split_commandline(module)[0]
    hmodule = winutil.load_library(module, winutil.LOAD_LIBRARY_AS_DATAFILE | winutil.LOAD_LIBRARY_AS_IMAGE_RESOURCE)
    icons = winutil.load_icons(hmodule, index)
    pixmaps = []
    must_use_qt()
    for icon_data, icon_handle in icons:
        pixmap = QPixmap()
        pixmap.loadFromData(icon_data)
        if pixmap.isNull() and bool(icon_handle):
            pixmap = hicon_to_pixmap(icon_handle)
        if pixmap.isNull():
            continue
        pixmaps.append(pixmap)
    if not pixmaps:
        return
    pixmaps.sort(key=lambda p: p.width())
    for pmap in pixmaps:
        if pmap.width() >= size:
            if pmap.width() == size:
                return pmap
            return pixmap.scaled(size, size, transformMode=Qt.SmoothTransformation)
    return pixmaps[-1].scaled(size, size, transformMode=Qt.SmoothTransformation)
