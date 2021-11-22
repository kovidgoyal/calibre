#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import re
import sys
from qt.core import QBuffer, QByteArray, QImage, QIODevice, QPixmap, Qt

from calibre.gui2 import must_use_qt
from calibre.utils.winreg.default_programs import split_commandline
from calibre_extensions import winutil

ICON_SIZE = 256


def hicon_to_pixmap(hicon):
    QPixmap.fromImage(QImage.fromHICON(int(hicon)))


def pixmap_to_data(pixmap):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buf, 'PNG')
    return bytes(bytearray(ba.data()))


def load_icon_resource_as_pixmap(icon_resource, size=ICON_SIZE):
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

    def area(p):
        return p.width() * p.height()

    pixmaps.sort(key=area)
    q = size * size
    for pmap in pixmaps:
        if area(pmap) >= q:
            if area(pmap) == q:
                return pmap
            return pmap.scaled(
                int(size), int(size), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio, transformMode=Qt.TransformationMode.SmoothTransformation)
    return pixmaps[-1].scaled(
        int(size), int(size), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio, transformMode=Qt.TransformationMode.SmoothTransformation)


def load_icon_resource(icon_resource, as_data=False, size=ICON_SIZE):
    ans = load_icon_resource_as_pixmap(icon_resource, size=size)
    if ans is not None:
        if as_data:
            ans = pixmap_to_data(ans)
    return ans


def load_icon_for_file(path: str, as_data=False, size=ICON_SIZE):
    try:
        hicon = winutil.get_icon_for_file(path)
    except Exception:
        return
    must_use_qt()
    pmap = hicon_to_pixmap(hicon)
    if not pmap.isNull():
        if pmap.width() != size:
            pmap = pmap.scaled(
                int(size), int(size), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio, transformMode=Qt.TransformationMode.SmoothTransformation)
        return pixmap_to_data(pmap) if as_data else pmap


def load_icon_for_cmdline(cmdline: str, as_data=False, size=ICON_SIZE):
    return load_icon_for_file(split_commandline(cmdline)[0], as_data=as_data, size=size)


def display_image(png_data):
    from base64 import standard_b64encode

    def serialize_gr_command(cmd, payload=None):
        cmd = ','.join(f'{k}={v}' for k, v in cmd.items())
        ans = []
        w = ans.append
        w(b'\033_G'), w(cmd.encode('ascii'))
        if payload:
            w(b';')
            w(payload)
        w(b'\033\\')
        return b''.join(ans)

    def write_chunked(cmd, data):
        data = standard_b64encode(data)
        while data:
            chunk, data = data[:4096], data[4096:]
            m = 1 if data else 0
            cmd['m'] = m
            sys.stdout.buffer.write(serialize_gr_command(cmd, chunk))
            sys.stdout.buffer.flush()
            cmd.clear()

    sys.stdout.flush()
    write_chunked({'a': 'T', 'f': 100}, png_data)


def test():
    png_data = load_icon_resource(sys.argv[-1], as_data=True)
    display_image(png_data)


def test_shell():
    png_data = load_icon_for_file(sys.argv[-1], as_data=True)
    display_image(png_data)
