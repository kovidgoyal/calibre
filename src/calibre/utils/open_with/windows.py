#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import re, struct, ctypes
from collections import namedtuple
from polyglot.builtins import map

from PyQt5.Qt import QtWin, Qt, QIcon, QByteArray, QBuffer, QPixmap
import win32con, win32api, win32gui, pywintypes, winerror

from calibre import prints
from calibre.gui2 import must_use_qt
from calibre.utils.winreg.default_programs import split_commandline
from polyglot.builtins import filter

ICON_SIZE = 64


def hicon_to_pixmap(hicon):
    return QtWin.fromHICON(hicon)


def pixmap_to_data(pixmap):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pixmap.save(buf, 'PNG')
    return bytearray(ba.data())


def copy_to_size(pixmap, size=ICON_SIZE):
    if pixmap.width() > ICON_SIZE:
        return pixmap.scaled(ICON_SIZE, ICON_SIZE, transformMode=Qt.SmoothTransformation)
    return pixmap.copy()


def simple_load_icon(module, index, as_data=False, size=ICON_SIZE):
    ' Use the win32 API ExtractIcon to load the icon. This restricts icon size to 32x32, but has less chance of failing '
    try:
        large_icons, small_icons = win32gui.ExtractIconEx(module, index, 10)
    except pywintypes.error as err:
        if err.winerror != winerror.ERROR_FILE_NOT_FOUND:
            raise
        prints('File %r does not exist, cannot load icon' % module)
        return
    icons = large_icons + small_icons
    try:
        if icons:
            must_use_qt()
            pixmap = copy_to_size(QtWin.fromHICON(icons[0]), size=size)
            if as_data:
                return pixmap_to_data(pixmap)
            return QIcon(pixmap)
    finally:
        tuple(map(win32gui.DestroyIcon, icons))


def read_icon(handle, icon):
    must_use_qt()
    resource = win32api.LoadResource(handle, win32con.RT_ICON, icon.id)
    pixmap = QPixmap()
    pixmap.loadFromData(resource)
    hicon = None
    if pixmap.isNull():
        if icon.width > 0 and icon.height > 0:
            hicon = ctypes.windll.user32.CreateIconFromResourceEx(
                resource, len(resource), True, 0x00030000, icon.width, icon.height, win32con.LR_DEFAULTCOLOR)
        else:
            hicon = win32gui.CreateIconFromResource(resource, True)
        pixmap = hicon_to_pixmap(hicon).copy()
        win32gui.DestroyIcon(hicon)
    return pixmap


def load_icon(module, index, as_data=False, size=ICON_SIZE):
    handle = win32api.LoadLibraryEx(module, 0, 0x20 | 0x2)
    try:
        ids = win32api.EnumResourceNames(handle, win32con.RT_GROUP_ICON)
        grp_id = -index if index < 0 else ids[index]
        data = win32api.LoadResource(handle, win32con.RT_GROUP_ICON, grp_id)
        pos = 0
        reserved, idtype, count = struct.unpack_from(b'<HHH', data, pos)
        pos += 6
        fmt = b'<BBBBHHIH'
        ssz = struct.calcsize(fmt)
        icons = []
        Icon = namedtuple('Icon', 'size width height id')
        while count > 0:
            count -= 1
            width, height, color_count, reserved, planes, bitcount, isize, icon_id = struct.unpack_from(fmt, data, pos)
            icons.append(Icon(isize, width, height, icon_id))
            pos += ssz
        # Unfortunately we cannot simply choose the icon with the largest
        # width/height as the width and height are not recorded for PNG images
        pixmaps = []
        for icon in icons:
            ans = read_icon(handle, icon)
            if ans is not None and not ans.isNull():
                pixmaps.append(ans)
        pixmaps.sort(key=lambda p:p.size().width(), reverse=True)
        pixmap = copy_to_size(pixmaps[0], size=size)
        if as_data:
            pixmap = pixmap_to_data(pixmap)
        return pixmap
    finally:
        win32api.FreeLibrary(handle)


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
    try:
        return load_icon(module, index, as_data=as_data, size=size)
    except Exception:
        return simple_load_icon(module, index, as_data=as_data, size=size)
