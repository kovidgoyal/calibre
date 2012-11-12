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
from calibre.constants import plugins, iswindows

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

def test_freetype():
    from calibre.utils.fonts.free_type import test
    test()
    print ('FreeType OK!')

def test_winutil():
    from calibre.devices.scanner import win_pnp_drives
    matches = win_pnp_drives.scanner()
    if len(matches) < 1:
        raise RuntimeError('win_pnp_drives returned no drives')
    print ('win_pnp_drives OK!')

def test_win32():
    from calibre.utils.winshell import desktop
    d = desktop()
    if not d:
        raise RuntimeError('winshell failed')
    print ('winshell OK! (%s is the desktop)'%d)

def test_sqlite():
    import sqlite3
    conn = sqlite3.connect(':memory:')
    from calibre.library.sqlite import load_c_extensions
    if not load_c_extensions(conn, True):
        raise RuntimeError('Failed to load sqlite extension')
    print ('sqlite OK!')

def test_qt():
    from PyQt4.Qt import (QWebView, QDialog, QImageReader, QNetworkAccessManager)
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
    import _imaging, _imagingmath, _imagingft, _imagingcms
    _imaging, _imagingmath, _imagingft, _imagingcms
    from PIL import Image
    i = Image.open(cStringIO.StringIO(data))
    if i.size < (20, 20):
        raise RuntimeError('PIL choked!')
    print ('PIL OK!')

def test_unrar():
    from calibre.libunrar import _libunrar
    if not _libunrar:
        raise RuntimeError('Failed to load libunrar')
    print ('Unrar OK!')

def test_icu():
    from calibre.utils.icu import _icu_not_ok
    if _icu_not_ok:
        raise RuntimeError('ICU module not loaded/valid')
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

def test():
    test_plugins()
    test_lxml()
    test_freetype()
    test_sqlite()
    test_imaging()
    test_unrar()
    test_icu()
    test_woff()
    test_qt()
    if iswindows:
        test_win32()
        test_winutil()
        test_wpd()

if __name__ == '__main__':
    test()

