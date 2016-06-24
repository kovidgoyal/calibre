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

import os, ctypes, sys, unittest
from calibre.constants import plugins, iswindows, islinux, isosx

class BuildTest(unittest.TestCase):

    @unittest.skipUnless(iswindows, 'DLL loading needs testing only on windows')
    def test_dlls(self):
        import win32api
        base = win32api.GetDllDirectory()
        for x in os.listdir(base):
            if x.lower().endswith('.dll'):
                try:
                    ctypes.WinDLL(os.path.join(base, x))
                except Exception as err:
                    self.assertTrue(False, 'Failed to load DLL %s with error: %s' % (x, err))

    @unittest.skipUnless(islinux, 'DBUS only used on linux')
    def test_dbus(self):
        import dbus
        bus = dbus.SystemBus()
        self.assertTrue(bus.list_names(), 'Failed to list names on the system bus')
        bus = dbus.SessionBus()
        self.assertTrue(bus.list_names(), 'Failed to list names on the session bus')
        del bus

    def test_regex(self):
        import regex
        self.assertEqual(regex.findall(r'(?i)(a)(b)', 'ab cd AB 1a1b'), [('a', 'b'), ('A', 'B')])

    def test_lzma(self):
        from lzma.xz import test_lzma2
        test_lzma2()

    def test_html5lib(self):
        import html5lib.html5parser  # noqa
        from html5lib import parse  # noqa

    def test_spell(self):
        from calibre.spell.dictionary import test_dictionaries
        test_dictionaries()

    def test_plugins(self):
        for name in plugins:
            mod, err = plugins[name]
            self.assertFalse(err or not mod, 'Failed to load plugin: ' + name + ' with error:\n' + err)

    def test_lxml(self):
        from calibre.utils.cleantext import test_clean_xml_chars
        test_clean_xml_chars()
        from lxml import etree
        raw = '<a/>'
        root = etree.fromstring(raw)
        self.assertEqual(etree.tostring(root), raw)

    def test_certgen(self):
        from calibre.utils.certgen import create_key_pair
        create_key_pair()

    @unittest.skipUnless(isosx, 'FSEvents only present on OS X')
    def test_fsevents(self):
        from fsevents import Observer, Stream
        del Observer, Stream

    @unittest.skipUnless(iswindows, 'winutil is windows only')
    def test_winutil(self):
        from calibre.constants import plugins
        winutil = plugins['winutil'][0]
        for x in winutil.argv():
            self.assertTrue(isinstance(x, unicode), 'argv() not returning unicode string')

    def test_sqlite(self):
        import sqlite3
        conn = sqlite3.connect(':memory:')
        from calibre.library.sqlite import load_c_extensions
        self.assertTrue(load_c_extensions(conn, True), 'Failed to load sqlite extension')

    def test_apsw(self):
        import apsw
        conn = apsw.Connection(':memory:')
        conn.close()

    def test_qt(self):
        # Must be run before QApplication is constructed
        # Test that the image formats are available without a QApplication being
        # constructed
        from calibre.utils.img import image_from_data, image_to_data, test
        data = I('blank.png', allow_user_override=False, data=True)
        img = image_from_data(data)
        image_from_data(P('catalog/mastheadImage.gif', allow_user_override=False, data=True))
        for fmt in 'png bmp jpeg'.split():
            d = image_to_data(img, fmt=fmt)
            image_from_data(d)
        # Run the imaging tests
        test()

        from calibre.gui2 import Application
        from PyQt5.Qt import (QImageReader, QNetworkAccessManager, QFontDatabase)
        from PyQt5.QtWebKitWidgets import QWebView
        os.environ.pop('DISPLAY', None)
        app = Application([], headless=islinux)
        self.assertGreaterEqual(len(QFontDatabase().families()), 5, 'The QPA headless plugin is not able to locate enough system fonts via fontconfig')
        fmts = set(map(unicode, QImageReader.supportedImageFormats()))
        testf = set(['jpg', 'png', 'svg', 'ico', 'gif'])
        self.assertEqual(testf.intersection(fmts), testf, "Qt doesn't seem to be able to load its image plugins")
        QWebView()
        del QWebView
        na = QNetworkAccessManager()
        self.assertTrue(hasattr(na, 'sslErrors'), 'Qt not compiled with openssl')
        del na
        del app

    def test_imaging(self):
        from PIL import Image
        try:
            import _imaging, _imagingmath, _imagingft
            _imaging, _imagingmath, _imagingft
        except ImportError:
            from PIL import _imaging, _imagingmath, _imagingft
        _imaging, _imagingmath, _imagingft
        i = Image.open(I('lt.png', allow_user_override=False))
        self.assertGreaterEqual(i.size, (20, 20))

    @unittest.skipUnless(iswindows, 'File dialog helper only used on windows')
    def test_file_dialog_helper(self):
        from calibre.gui2.win_file_dialogs import test
        test()

    def test_unrar(self):
        from calibre.utils.unrar import test_basic
        test_basic()

    @unittest.skipUnless(iswindows, 'WPD is windows only')
    def test_wpd(self):
        wpd = plugins['wpd'][0]
        try:
            wpd.init('calibre', 1, 1, 1)
        except wpd.NoWPD:
            pass
        else:
            wpd.uninit()

    def test_tinycss_tokenizer(self):
        from tinycss.tokenizer import c_tokenize_flat
        self.assertIsNotNone(c_tokenize_flat, 'tinycss C tokenizer not loaded')

    @unittest.skipUnless(getattr(sys, 'frozen', False), 'Only makes sense to test executables in frozen builds')
    def test_executables(self):
        from calibre.utils.ipc.launch import Worker
        from calibre.ebooks.pdf.pdftohtml import PDFTOHTML
        w = Worker({})
        self.assertTrue(os.path.exists(w.executable), 'calibre-parallel (%s) does not exist' % w.executable)
        self.assertTrue(os.path.exists(w.gui_executable), 'calibre-parallel-gui (%s) does not exist' % w.gui_executable)
        self.assertTrue(os.path.exists(PDFTOHTML), 'pdftohtml (%s) does not exist' % PDFTOHTML)
        if iswindows:
            from calibre.devices.usbms.device import eject_exe
            self.assertTrue(os.path.exists(eject_exe()), 'calibre-eject.exe (%s) does not exist' % eject_exe())

    def test_netifaces(self):
        import netifaces
        self.assertGreaterEqual(netifaces.interfaces(), 1, 'netifaces could find no network interfaces')

    def test_psutil(self):
        import psutil
        psutil.Process(os.getpid())

    def test_podofo(self):
        from calibre.utils.podofo import test_podofo as dotest
        dotest()

    @unittest.skipIf(iswindows, 'readline not available on windows')
    def test_terminal(self):
        import readline
        del readline

    def test_markdown(self):
        from calibre.ebooks.markdown import Markdown
        Markdown(extensions=['extra'])
        from calibre.library.comments import sanitize_html
        sanitize_html(b'''<script>moo</script>xxx<img src="http://moo.com/x.jpg">''')

    def test_image_compression(self):
        from calibre.utils.img import test
        test()

    def test_openssl(self):
        import ssl
        ssl.PROTOCOL_TLSv1_2
        if isosx:
            cafile = ssl.get_default_verify_paths().cafile
            if not cafile or not cafile.endswith('/mozilla-ca-certs.pem') or not os.access(cafile, os.R_OK):
                self.assert_('Mozilla CA certs not loaded')

def find_tests():
    ans = unittest.defaultTestLoader.loadTestsFromTestCase(BuildTest)
    from calibre.utils.icu_test import find_tests
    import duktape.tests as dtests
    ans.addTests(find_tests())
    ans.addTests(unittest.defaultTestLoader.loadTestsFromModule(dtests))
    from tinycss.tests.main import find_tests
    ans.addTests(find_tests())
    return ans

class TestRunner(unittest.main):

    def createTests(self):
        self.test = find_tests()

def test():
    result = TestRunner(verbosity=2, buffer=True, catchbreak=True, failfast=True, argv=sys.argv[:1], exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)

if __name__ == '__main__':
    test()
