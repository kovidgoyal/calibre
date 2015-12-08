#!/usr/bin/env python2
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

import cStringIO, os, ctypes, shutil, sys
from calibre import CurrentDir
from calibre.constants import plugins, iswindows, islinux, isosx
from calibre.ptempfile import TemporaryDirectory

def test_dlls():
    import win32api
    base = win32api.GetDllDirectory()
    errors = []
    for x in os.listdir(base):
        if x.lower().endswith('.dll'):
            try:
                ctypes.WinDLL(os.path.join(base, x))
            except Exception as err:
                errors.append('Failed to load DLL %s with error: %s' % (x, err))
                print (errors[-1])
    if errors:
        print ('Loading %d dll(s) failed!' % len(errors))
        raise SystemExit(1)
    print ('DLLs OK!')


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

def test_lzma():
    from lzma.xz import test_lzma2
    test_lzma2()
    print ('lzma OK!')

def test_html5lib():
    import html5lib.html5parser  # noqa
    from html5lib import parse  # noqa
    print ('html5lib OK!')

def test_spell():
    from calibre.spell.dictionary import test_dictionaries
    test_dictionaries()
    print ('hunspell OK!')

def test_plugins():
    bad = []
    for name in plugins:
        mod, err = plugins[name]
        if err or not mod:
            bad.append((name, err))
    if bad:
        for name, err in bad:
            print ('Failed to load plugin:', name, 'with error:\n', err, '\n')
        raise SystemExit(1)
    print ('Loaded all plugins successfully!')

def test_lxml():
    from lxml import etree
    raw = '<a/>'
    root = etree.fromstring(raw)
    if etree.tostring(root) == raw:
        print ('lxml OK!')
    else:
        raise RuntimeError('lxml failed')

def test_certgen():
    from calibre.utils.certgen import create_key_pair
    create_key_pair()

def test_fsevents():
    from fsevents import Observer, Stream
    del Observer, Stream
    print ('macfsevents OK!')

def test_winutil():
    from calibre.devices.scanner import win_pnp_drives
    from calibre.constants import plugins
    winutil = plugins['winutil'][0]
    try:
        matches = win_pnp_drives.scanner()
    except winutil.DriveError:
        print ('No removable drives found, skipping win_pnp_drives test!')
        return
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
    from calibre.gui2 import Application
    from PyQt5.Qt import (QImageReader, QNetworkAccessManager, QFontDatabase)
    from PyQt5.QtWebKitWidgets import QWebView
    os.environ.pop('DISPLAY', None)
    app = Application([], headless=islinux)
    if len(QFontDatabase().families()) < 5:
        raise RuntimeError('The QPA headless plugin is not able to locate enough system fonts via fontconfig')
    fmts = set(map(unicode, QImageReader.supportedImageFormats()))
    testf = set(['jpg', 'png', 'mng', 'svg', 'ico', 'gif'])
    if testf.intersection(fmts) != testf:
        raise RuntimeError(
            "Qt doesn't seem to be able to load its image plugins")
    QWebView()
    del QWebView
    na = QNetworkAccessManager()
    if not hasattr(na, 'sslErrors'):
        raise RuntimeError('Qt not compiled with openssl')
    del na
    del app
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

def test_dukpy():
    print ('Testing dukpy')
    from duktape import test_build
    test_build()
    print ('dukpy OK!')

def test_wpd():
    wpd = plugins['wpd'][0]
    try:
        wpd.init('calibre', 1, 1, 1)
    except wpd.NoWPD:
        print ('This computer does not have WPD')
    else:
        wpd.uninit()
    print ('WPD OK!')

def test_magick():
    from calibre.utils.magick import create_canvas
    i = create_canvas(100, 100)
    from calibre.gui2.tweak_book.editor.canvas import qimage_to_magick, magick_to_qimage
    img = magick_to_qimage(i)
    i = qimage_to_magick(img)
    print ('magick OK!')

def test_tokenizer():
    print ('Testing tinycss tokenizer')
    from tinycss.tokenizer import c_tokenize_flat
    if c_tokenize_flat is None:
        raise ValueError('tinycss C tokenizer not loaded')
    import tinycss.tests.main as m
    if getattr(m, '__file__', None) and os.path.exists(m.__file__):
        m.run_tests(for_build=True)
    print('tinycss tokenizer OK!')

def test_executables():
    from calibre.utils.ipc.launch import Worker
    if getattr(sys, 'frozen', False):
        w = Worker({})
        if not os.path.exists(w.executable):
            raise SystemExit('calibre-parallel (%s) does not exist' % w.executable)
        if not os.path.exists(w.gui_executable):
            raise SystemExit('calibre-parallel-gui (%s) does not exist' % w.gui_executable)
        if iswindows:
            from calibre.devices.usbms.device import eject_exe
            if not os.path.exists(eject_exe()):
                raise SystemExit('calibre-eject.exe (%s) does not exist' % eject_exe())
        from calibre.ebooks.pdf.pdftohtml import PDFTOHTML
        if not os.path.exists(PDFTOHTML):
            raise SystemExit('pdftohtml (%s) does not exist' % PDFTOHTML)

        print('executables OK!')

def test_netifaces():
    import netifaces
    if len(netifaces.interfaces()) < 1:
        raise ValueError('netifaces could find no network interfaces')
    print ('netifaces OK!')

def test_psutil():
    import psutil
    psutil.Process(os.getpid())
    print ('psutil OK!')

def test_podofo():
    from calibre.utils.podofo import test_podofo as dotest
    dotest()
    print ('podofo OK!')

def test_terminal():
    import readline
    del readline
    print ('readline OK!')

def test_markdown():
    from calibre.ebooks.markdown import Markdown
    Markdown(extensions=['extra'])
    from calibre.library.comments import sanitize_html
    sanitize_html(b'''<script>moo</script>xxx<img src="http://moo.com/x.jpg">''')
    print('Markdown OK!')

def test_image_compression():
    from calibre.utils.img import optimize_png, optimize_jpeg, encode_jpeg
    with TemporaryDirectory() as tdir, CurrentDir(tdir):
        shutil.copyfile(I('devices/kindle.jpg'), 'test.jpg')
        ret = optimize_jpeg('test.jpg')
        if ret is not None:
            raise SystemExit(ret)
        ret = encode_jpeg('test.jpg')
        if ret is not None:
            raise SystemExit(ret)
        shutil.copyfile(I('lt.png'), 'test.png')
        ret = optimize_png('test.png')
        if ret is not None:
            raise SystemExit(ret)
    print('Image compression OK!')

def test():
    if iswindows:
        test_dlls()
    test_plugins()
    test_executables()
    test_image_compression()
    test_lzma()
    test_dukpy()
    test_spell()
    test_lxml()
    test_ssl()
    test_sqlite()
    test_apsw()
    test_imaging()
    test_unrar()
    test_certgen()
    test_icu()
    test_qt()
    test_html5lib()
    test_regex()
    test_magick()
    test_tokenizer()
    test_netifaces()
    test_psutil()
    test_podofo()
    test_markdown()
    if islinux:
        test_dbus()
    if iswindows:
        test_wpd()
        test_winutil()
    else:
        test_terminal()
    if isosx:
        test_fsevents()

if __name__ == '__main__':
    test()

