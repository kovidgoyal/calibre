#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, array, socket, re

import dbus

from PyQt5.Qt import QSize, QImage, Qt, QKeySequence, QBuffer, QByteArray

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

def swap_mnemonic_char(text, from_char='&', to_char='_'):
    text = text.replace(to_char, to_char * 2)  # Escape to_char
    # Replace the first occurence of an unescaped from_char with to_char
    text = re.sub(r'(?<!{0}){0}(?!$)'.format(from_char), to_char, text, count=1)
    # Remove any remaining unescaped from_char
    text = re.sub(r'(?<!{0}){0}(?!$)'.format(from_char), '', text)
    # Unescape from_char
    text = text.replace(from_char * 2, from_char)
    return text

def key_sequence_to_dbus_shortcut(qks):
    for key in qks:
        if key == -1 or key == Qt.Key_unknown:
            continue
        items = []
        for mod, name in {Qt.META:'Super', Qt.CTRL:'Control', Qt.ALT:'Alt', Qt.SHIFT:'Shift'}.iteritems():
            if key & mod == mod:
                items.append(name)
        key &= int(~(Qt.ShiftModifier | Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier | Qt.KeypadModifier))
        text = QKeySequence(key).toString()
        if text:
            text = {'+':'plus', '-':'minus'}.get(text, text)
            items.append(text)
        if items:
            yield items

def icon_to_dbus_menu_icon(icon, size=32):
    if icon.isNull():
        return None
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    icon.pixmap(32).save(buf, 'PNG')
    return dbus.ByteArray(bytes((ba.data())))

def setup_for_cli_run():
    import signal
    from dbus.mainloop.glib import DBusGMainLoop, threads_init
    DBusGMainLoop(set_as_default=True)
    threads_init()
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # quit on Ctrl-C

