#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Test a binary calibre build to ensure that all needed binary images/libraries have loaded.
'''

import cStringIO
from calibre.constants import plugins, iswindows, islinux

def test_dbus():
    import dbus
    bus = dbus.SystemBus()
    if not bus.list_names():
        raise ValueError('Failed to list names on the system bus')
    bus = dbus.SessionBus()
    if not bus.list_names():
        raise ValueError('Failed to list names on the session bus')
    del bus
    print ('dbus OK!')

def test_regex():
    import regex
    if regex.findall(r'(?i)(a)(b)', 'ab cd AB 1a1b') != [('a', 'b'), ('A', 'B')]:
        raise ValueError('regex module failed on a simple search')
    print ('regex OK!')

def test_html5lib():
    import html5lib.html5parser  # noqa
    from html5lib import parse  # noqa
    print ('html5lib OK!')

def test_plugins():
    for name in plugins:
        mod, err = plugins[name]
        if err or not mod:
            raise RuntimeError('Plugin %s failed to load with error: %s' %
                    (name, err))
        print (mod, 'loaded')

def test_lxml():
    from lxml import etree
    raw = '<a/>'
    root = etree.fromstring(raw)
    if etree.tostring(root) == raw:
        print ('lxml OK!')
    else:
        raise RuntimeError('lxml failed')

def test_winutil():
    from calibre.devices.scanner import win_pnp_drives
    matches = win_pnp_drives.scanner()
    if len(matches) < 1:
        raise RuntimeError('win_pnp_drives returned no drives')
    print ('win_pnp_drives OK!')

def test_sqlite():
    import sqlite3
    conn = sqlite3.connect(':memory:')
    from calibre.library.sqlite import load_c_extensions
    if not load_c_extensions(conn, True):
        raise RuntimeError('Failed to load sqlite extension')
    print ('sqlite OK!')

def test_apsw():
    import apsw
    conn = apsw.Connection(':memory:')
    conn.close()
    print ('apsw OK!')

def test_qt():
    from PyQt4.Qt import (QDialog, QImageReader, QNetworkAccessManager)
    from PyQt4.QtWebKit import QWebView
    fmts = set(map(unicode, QImageReader.supportedImageFormats()))
    testf = set(['jpg', 'png', 'mng', 'svg', 'ico', 'gif'])
    if testf.intersection(fmts) != testf:
        raise RuntimeError(
            "Qt doesn't seem to be able to load its image plugins")
    QWebView, QDialog
    na = QNetworkAccessManager()
    if not hasattr(na, 'sslErrors'):
        raise RuntimeError('Qt not compiled with openssl')
    print ('Qt OK!')

def test_imaging():
    from calibre.ebooks import calibre_cover
    data = calibre_cover('test', 'ok')
    if len(data) > 1000:
        print ('ImageMagick OK!')
    else:
        raise RuntimeError('ImageMagick choked!')
    from PIL import Image
    try:
        import _imaging, _imagingmath, _imagingft
        _imaging, _imagingmath, _imagingft
    except ImportError:
        from PIL import _imaging, _imagingmath, _imagingft
    _imaging, _imagingmath, _imagingft
    i = Image.open(cStringIO.StringIO(data))
    if i.size < (20, 20):
        raise RuntimeError('PIL choked!')
    print ('PIL OK!')

def test_unrar():
    from calibre.utils.unrar import test_basic
    test_basic()
    print ('Unrar OK!')

def test_ssl():
    import ssl
    ssl
    print ('SSL OK!')

def test_icu():
    print ('Testing ICU')
    from calibre.utils.icu_test import test_build
    test_build()
    print ('ICU OK!')

def test_wpd():
    wpd = plugins['wpd'][0]
    try:
        wpd.init('calibre', 1, 1, 1)
    except wpd.NoWPD:
        print ('This computer does not have WPD')
    else:
        wpd.uninit()

def test_woff():
    from calibre.utils.fonts.woff import test
    test()
    print ('WOFF ok!')

def test_magick():
    print ('Testing tinycss tokenizer')
    from calibre.utils.magick import create_canvas
    i = create_canvas(100, 100)
    from calibre.gui2.tweak_book.editor.canvas import qimage_to_magick, magick_to_qimage
    img = magick_to_qimage(i)
    i = qimage_to_magick(img)
    print ('magick OK!')

def test_tokenizer():
    from tinycss.tokenizer import c_tokenize_flat
    if c_tokenize_flat is None:
        raise ValueError('tinycss C tokenizer not loaded')
    from tinycss.tests.main import run_tests
    run_tests(for_build=True)
    print('tinycss tokenizer OK!')

def test():
    test_plugins()
    test_lxml()
    test_ssl()
    test_sqlite()
    test_apsw()
    test_imaging()
    test_unrar()
    test_icu()
    test_woff()
    test_qt()
    test_html5lib()
    test_regex()
    test_magick()
    test_tokenizer()
    if iswindows:
        test_winutil()
        test_wpd()
    if islinux:
        test_dbus()

if __name__ == '__main__':
    test()

