#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, array, re, os, errno

import dbus

from PyQt5.Qt import QSize, QImage, Qt, QKeySequence, QBuffer, QByteArray

from polyglot.builtins import unicode_type, iteritems


def log(*args, **kw):
    kw['file'] = sys.stderr
    print('DBusExport:', *args, **kw)
    kw['file'].flush()


from calibre.ptempfile import PersistentTemporaryDirectory


class IconCache(object):

    # Avoiding sending status notifier icon data over DBus, makes dbus-monitor
    # easier to read.  Also Canonical's StatusNotifier implementation cannot
    # handle icon data over DBus, so we have to do this anyway.

    def __init__(self):
        self.icon_theme_path = os.path.join(PersistentTemporaryDirectory(prefix='dbus-export-icons-'), 'icons')
        self.theme_dir = os.path.join(self.icon_theme_path, 'hicolor')
        os.makedirs(self.theme_dir)
        self.cached = set()

    def name_for_icon(self, qicon):
        if qicon.isNull():
            return ''
        key = qicon.cacheKey()
        ans = 'dbus-icon-cache-%d' % key
        if key not in self.cached:
            self.write_icon(qicon, ans)
            self.cached.add(key)
        return ans

    def write_icon(self, qicon, name):
        sizes = qicon.availableSizes() or [QSize(x, x) for x in (16, 32, 64, 128, 256)]
        for size in sizes:
            sdir = os.path.join(self.theme_dir, '%dx%d' % (size.width(), size.height()), 'apps')
            try:
                os.makedirs(sdir)
            except EnvironmentError as err:
                if err.errno != errno.EEXIST:
                    raise
            fname = os.path.join(sdir, '%s.png' % name)
            qicon.pixmap(size).save(fname, 'PNG')
        # Touch the theme path: GTK icon loading system checks the mtime of the
        # dir to decide whether it should look for new icons in the theme dir.
        os.utime(self.icon_theme_path, None)


_icon_cache = None


def icon_cache():
    global _icon_cache
    if _icon_cache is None:
        _icon_cache = IconCache()
    return _icon_cache


def qicon_to_sni_image_list(qicon):
    'See http://www.notmart.org/misc/statusnotifieritem/icons.html'
    import socket
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
        for mod, name in iteritems({Qt.META:'Super', Qt.CTRL:'Control', Qt.ALT:'Alt', Qt.SHIFT:'Shift'}):
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
    return dbus.ByteArray(ba)


def setup_for_cli_run():
    import signal
    from dbus.mainloop.glib import DBusGMainLoop, threads_init
    threads_init()
    DBusGMainLoop(set_as_default=True)
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # quit on Ctrl-C


def set_X_window_properties(win_id, **properties):
    ' Set X Window properties on the window with the specified id. Only string values are supported. '
    import xcb, xcb.xproto
    conn = xcb.connect()
    atoms = {name:conn.core.InternAtom(False, len(name), name) for name in properties}
    utf8_string_atom = None
    for name, val in iteritems(properties):
        atom = atoms[name].reply().atom
        type_atom = xcb.xproto.Atom.STRING
        if isinstance(val, unicode_type):
            if utf8_string_atom is None:
                utf8_string_atom = conn.core.InternAtom(True, len(b'UTF8_STRING'), b'UTF8_STRING').reply().atom
            type_atom = utf8_string_atom
            val = val.encode('utf-8')
        conn.core.ChangePropertyChecked(xcb.xproto.PropMode.Replace, win_id, atom, type_atom, 8, len(val), val)
    conn.flush()
    conn.disconnect()
