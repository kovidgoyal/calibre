#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from polyglot.builtins import map, unicode_type

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Test a binary calibre build to ensure that all needed binary images/libraries have loaded.
'''

import os, ctypes, sys, unittest, time
from calibre.constants import plugins, iswindows, islinux, isosx
is_ci = os.environ.get('CI', '').lower() == 'true'


class BuildTest(unittest.TestCase):

    @unittest.skipUnless(iswindows and not is_ci, 'DLL loading needs testing only on windows (non-continuous integration)')
    def test_dlls(self):
        import win32api
        base = win32api.GetDllDirectory()
        for x in os.listdir(base):
            if x.lower().endswith('.dll'):
                try:
                    ctypes.WinDLL(str(os.path.join(base, x)))
                except Exception as err:
                    self.assertTrue(False, 'Failed to load DLL %s with error: %s' % (x, err))

    @unittest.skipUnless(islinux, 'DBUS only used on linux')
    def test_dbus(self):
        import dbus
        if 'DBUS_SESSION_BUS_ADDRESS' in os.environ:
            bus = dbus.SystemBus()
            self.assertTrue(bus.list_names(), 'Failed to list names on the system bus')
            bus = dbus.SessionBus()
            self.assertTrue(bus.list_names(), 'Failed to list names on the session bus')
            del bus

    def test_regex(self):
        import regex
        self.assertEqual(regex.findall(r'(?i)(a)(b)', 'ab cd AB 1a1b'), [('a', 'b'), ('A', 'B')])
        self.assertEqual(regex.escape('a b', literal_spaces=True), 'a b')

    def test_chardet(self):
        from chardet import detect
        raw = 'mūsi Füße'.encode('utf-8')
        data = detect(raw)
        self.assertEqual(data['encoding'], 'utf-8')
        self.assertGreater(data['confidence'], 0.5)
        # The following is used by html5lib
        from chardet.universaldetector import UniversalDetector
        detector = UniversalDetector()
        self.assertTrue(hasattr(detector, 'done'))
        detector.feed(raw)
        detector.close()
        self.assertEqual(detector.result['encoding'], 'utf-8')

    def test_lzma(self):
        from lzma.xz import test_lzma2
        test_lzma2()

    def test_html5lib(self):
        import html5lib.html5parser  # noqa
        from html5lib import parse  # noqa

    def test_html5_parser(self):
        from html5_parser import parse
        parse('<p>xxx')

    def test_plugins(self):
        exclusions = set()
        if is_ci:
            if isosx:
                # The compiler version on OS X is different between the
                # machine on which the dependencies are built and the
                # machine on which the calibre modules are built, which causes
                # C++ name mangling incompatibilities preventing some modules
                # from loading
                exclusions.update(set('podofo'.split()))
        if islinux and (not os.path.exists('/dev/bus/usb') and not os.path.exists('/proc/bus/usb')):
            # libusb fails to initialize in containers without USB subsystems
            exclusions.update(set('libusb libmtp'.split()))
        for name in plugins:
            if name in exclusions:
                if name in ('libusb', 'libmtp'):
                    # Just check that the DLL can be loaded
                    ctypes.CDLL(os.path.join(sys.extensions_location, name + ('.dylib' if isosx else '.so')))
                continue
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

    def test_msgpack(self):
        from calibre.utils.serialize import msgpack_dumps, msgpack_loads
        from calibre.utils.date import utcnow
        for obj in ({1:1}, utcnow()):
            s = msgpack_dumps(obj)
            self.assertEqual(obj, msgpack_loads(s))
        self.assertEqual(type(msgpack_loads(msgpack_dumps(b'b'))), bytes)
        self.assertEqual(type(msgpack_loads(msgpack_dumps(u'b'))), type(u''))
        large = b'x' * (100 * 1024 * 1024)
        msgpack_loads(msgpack_dumps(large))

    @unittest.skipUnless(isosx, 'FSEvents only present on OS X')
    def test_fsevents(self):
        from fsevents import Observer, Stream
        del Observer, Stream

    @unittest.skipUnless(iswindows, 'winutil is windows only')
    def test_winutil(self):
        from calibre.constants import plugins
        from calibre import strftime
        winutil = plugins['winutil'][0]

        def au(x, name):
            self.assertTrue(isinstance(x, unicode_type), name + '() did not return a unicode string')
        for x in winutil.argv():
            au(x, 'argv')
        for x in 'username temp_path locale_name'.split():
            au(getattr(winutil, x)(), x)
        d = winutil.localeconv()
        au(d['thousands_sep'], 'localeconv')
        au(d['decimal_point'], 'localeconv')
        for k, v in d.iteritems():
            au(v, k)
        for k in os.environ.keys():
            au(winutil.getenv(unicode_type(k)), 'getenv-' + k)
        os.environ['XXXTEST'] = 'YYY'
        self.assertEqual(winutil.getenv(u'XXXTEST'), u'YYY')
        del os.environ['XXXTEST']
        self.assertIsNone(winutil.getenv(u'XXXTEST'))
        t = time.localtime()
        fmt = u'%Y%a%b%e%H%M'
        for fmt in (fmt, fmt.encode('ascii')):
            x = strftime(fmt, t)
            au(x, 'strftime')
            self.assertEqual(unicode_type(time.strftime(fmt.replace('%e', '%#d'), t)), x)

    def test_sqlite(self):
        import sqlite3
        conn = sqlite3.connect(':memory:')
        from calibre.library.sqlite import load_c_extensions
        self.assertTrue(load_c_extensions(conn, True), 'Failed to load sqlite extension')

    def test_apsw(self):
        import apsw
        conn = apsw.Connection(':memory:')
        conn.close()

    @unittest.skipIf('SKIP_QT_BUILD_TEST' in os.environ, 'Skipping Qt build test as it causes crashes in the macOS VM')
    def test_qt(self):
        from PyQt5.Qt import QImageReader, QNetworkAccessManager, QFontDatabase
        from calibre.utils.img import image_from_data, image_to_data, test
        # Ensure that images can be read before QApplication is constructed.
        # Note that this requires QCoreApplication.libraryPaths() to return the
        # path to the Qt plugins which it always does in the frozen build,
        # because the QT_PLUGIN_PATH env var is set. On non-frozen builds,
        # it should just work because the hard-coded paths of the Qt
        # installation should work. If they do not, then it is a distro
        # problem.
        fmts = set(map(unicode_type, QImageReader.supportedImageFormats()))
        testf = {'jpg', 'png', 'svg', 'ico', 'gif'}
        self.assertEqual(testf.intersection(fmts), testf, "Qt doesn't seem to be able to load some of its image plugins. Available plugins: %s" % fmts)
        data = P('images/blank.png', allow_user_override=False, data=True)
        img = image_from_data(data)
        image_from_data(P('catalog/mastheadImage.gif', allow_user_override=False, data=True))
        for fmt in 'png bmp jpeg'.split():
            d = image_to_data(img, fmt=fmt)
            image_from_data(d)
        # Run the imaging tests
        test()

        from calibre.gui2 import Application
        os.environ.pop('DISPLAY', None)
        has_headless = isosx or islinux
        app = Application([], headless=has_headless)
        self.assertGreaterEqual(len(QFontDatabase().families()), 5, 'The QPA headless plugin is not able to locate enough system fonts via fontconfig')
        if has_headless:
            from calibre.ebooks.covers import create_cover
            create_cover('xxx', ['yyy'])
        na = QNetworkAccessManager()
        self.assertTrue(hasattr(na, 'sslErrors'), 'Qt not compiled with openssl')
        from PyQt5.QtWebKitWidgets import QWebView
        if iswindows:
            from PyQt5.Qt import QtWin
            QtWin
        QWebView()
        del QWebView
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

    @unittest.skipUnless(iswindows and not is_ci, 'File dialog helper only used on windows (non-continuous-itegration)')
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

    @unittest.skipIf(is_ci and isosx, 'Currently there is a C++ ABI incompatibility until the osx-build machine is moved to OS X 10.9')
    def test_podofo(self):
        from calibre.utils.podofo import test_podofo as dotest
        dotest()

    @unittest.skipIf(iswindows, 'readline not available on windows')
    def test_terminal(self):
        import readline
        del readline

    def test_markdown(self):
        from calibre.ebooks.txt.processor import create_markdown_object
        from calibre.ebooks.conversion.plugins.txt_input import MD_EXTENSIONS
        create_markdown_object(sorted(MD_EXTENSIONS))
        from calibre.library.comments import sanitize_comments_html
        sanitize_comments_html(b'''<script>moo</script>xxx<img src="http://moo.com/x.jpg">''')

    def test_feedparser(self):
        from calibre.web.feeds.feedparser import parse
        # sgmllib is needed for feedparser parsing malformed feeds
        # on python3 you can get it by taking it from python2 stdlib and
        # running 2to3 on it
        import sgmllib
        sgmllib, parse

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
    from calibre.spell.dictionary import find_tests
    ans.addTests(find_tests())
    return ans


def test():
    from calibre.utils.run_tests import run_cli
    run_cli(find_tests())


if __name__ == '__main__':
    test()
