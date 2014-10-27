#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, array, socket

import dbus

from PyQt5.Qt import QSize, QImage

def log(*args, **kw):
    kw['file'] = sys.stderr
    print('StatusNotifier:', *args, **kw)
    kw['file'].flush()


def qicon_to_sni_image_list(qicon):
    'See http://www.notmart.org/misc/statusnotifieritem/icons.html'
    ans = dbus.Array(signature='(iiay)')
    if not qicon.isNull():
        sizes = qicon.availableSizes() or (QSize(x, x) for x in (32, 64, 128, 256))
        tc = b'L' if array.array(b'I').itemsize < 4 else b'I'
        for size in sizes:
            # Convert to DBUS struct of width, height, and image data in ARGB32
            # in network endianness
            i = qicon.pixmap(size).toImage().convertToFormat(QImage.Format_ARGB32)
            w, h = i.width(), i.height()
            data = i.constBits().asstring(4 * w * h)
            if socket.htonl(1) != 1:
                # Host endianness != Network Endiannes
                data = array.array(tc, i.constBits().asstring(4 * i.width() * i.height()))
                data.byteswap()
                data = data.tostring()
            ans.append((w, h, dbus.ByteArray(data)))
    return ans

