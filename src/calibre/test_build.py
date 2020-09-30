#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Test a binary calibre build to ensure that all needed binary images/libraries have loaded.
'''

import os, ctypes, sys, unittest, time

from calibre.constants import plugins, iswindows, islinux, ismacos, plugins_loc
from polyglot.builtins import iteritems, map, unicode_type, getenv, native_string_type

is_ci = os.environ.get('CI', '').lower() == 'true'


class BuildTest(unittest.TestCase):

    @unittest.skipUnless(iswindows and not is_ci, 'DLL loading needs testing only on windows (non-continuous integration)')
    def test_dlls(self):
        import win32api
        base = win32api.GetDllDirectory()
        for x in os.listdir(base):
            if x.lower().endswith('.dll'):
                try:
                    ctypes.WinDLL(native_string_type(os.path.join(base, x)))
                except Exception as err:
                    self.assertTrue(False, 'Failed to load DLL %s with error: %s' % (x, err))
        from Crypto.Cipher import AES
        del AES

    @unittest.skipUnless(islinux, 'DBUS only used on linux')
    def test_dbus(self):
        import dbus
        if 'DBUS_SESSION_BUS_ADDRESS' in os.environ:
            bus = dbus.SystemBus()
            self.assertTrue(bus.list_names(), 'Failed to list names on the system bus')
            bus = dbus.SessionBus()
            self.assertTrue(bus.list_names(), 'Failed to list names on the session bus')
            del bus

    def test_loaders(self):
        import importlib
        ldr = importlib.import_module('calibre').__spec__.loader
        self.assertIn('ebooks', ldr.contents())
        try:
            raw = ldr.open_resource('__init__.py').read()
        except FileNotFoundError:
            raw = ldr.open_resource('__init__.pyc').read()
        self.assertGreater(len(raw), 1024)

    def test_regex(self):
        import regex
        self.assertEqual(regex.findall(r'(?i)(a)(b)', 'ab cd AB 1a1b'), [('a', 'b'), ('A', 'B')])
        self.assertEqual(regex.escape('a b', literal_spaces=True), 'a b')

    def test_hunspell(self):
        from calibre.spell.dictionary import build_test
        build_test()

    def test_pychm(self):
        from chm.chm import CHMFile, chmlib
        del CHMFile, chmlib

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
        import lzma
        lzma.open

    def test_html5lib(self):
        import html5lib.html5parser  # noqa
        from html5lib import parse  # noqa

    def test_html5_parser(self):
        from html5_parser import parse
        parse('<p>xxx')

    def test_bs4(self):
        import soupsieve, bs4
        del soupsieve, bs4

    def test_zeroconf(self):
        import zeroconf as z, ifaddr
        del z
        del ifaddr

    def test_plugins(self):
        exclusions = set()
        if islinux and (not os.path.exists('/dev/bus/usb') and not os.path.exists('/proc/bus/usb')):
            # libusb fails to initialize in containers without USB subsystems
            exclusions.update(set('libusb libmtp'.split()))
        for name in plugins:
            if name in exclusions:
                if name in ('libusb', 'libmtp'):
                    # Just check that the DLL can be loaded
                    ctypes.CDLL(os.path.join(plugins_loc, name + ('.dylib' if ismacos else '.so')))
                continue
            mod, err = plugins[name]
            self.assertFalse(err or not mod, 'Failed to load plugin: ' + name + ' with error:\n' + err)

    def test_lxml(self):
        from calibre.utils.cleantext import test_clean_xml_chars
        test_clean_xml_chars()
        from lxml import etree
        raw = b'<a/>'
        root = etree.fromstring(raw, parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False))
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
        self.assertEqual(type(msgpack_loads(msgpack_dumps('b'))), unicode_type)
        large = b'x' * (100 * 1024 * 1024)
        msgpack_loads(msgpack_dumps(large))

    @unittest.skipUnless(ismacos, 'FSEvents only present on OS X')
    def test_fsevents(self):
        from fsevents import Observer, Stream
        del Observer, Stream

    @unittest.skipUnless(iswindows, 'winutil is windows only')
    def test_winutil(self):
        from calibre.constants import plugins
        from calibre import strftime
        winutil = plugins['winutil'][0]

        def au(x, name):
            self.assertTrue(
                isinstance(x, unicode_type),
                '%s() did not return a unicode string, instead returning: %r' % (name, x))
        for x in winutil.argv():
            au(x, 'argv')
        for x in 'username temp_path locale_name'.split():
            au(getattr(winutil, x)(), x)
        d = winutil.localeconv()
        au(d['thousands_sep'], 'localeconv')
        au(d['decimal_point'], 'localeconv')
        for k, v in iteritems(d):
            au(v, k)
        os.environ['XXXTEST'] = 'YYY'
        self.assertEqual(getenv('XXXTEST'), 'YYY')
        del os.environ['XXXTEST']
        self.assertIsNone(getenv('XXXTEST'))
        for k in os.environ:
            v = getenv(k)
            if v is not None:
                au(v, 'getenv-' + k)
        t = time.localtime()
        fmt = '%Y%a%b%e%H%M'
        for fmt in (fmt, fmt.encode('ascii')):
            x = strftime(fmt, t)
            au(x, 'strftime')
            if isinstance(fmt, bytes):
                fmt = fmt.decode('ascii')
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
        from PyQt5.QtCore import QTimer
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtWebEngineWidgets import QWebEnginePage
        from PyQt5.QtGui import QImageReader, QFontDatabase
        from PyQt5.QtNetwork import QNetworkAccessManager
        from calibre.utils.img import image_from_data, image_to_data, test
        # Ensure that images can be read before QApplication is constructed.
        # Note that this requires QCoreApplication.libraryPaths() to return the
        # path to the Qt plugins which it always does in the frozen build,
        # because Qt is patched to know the layout of the calibre application
        # package. On non-frozen builds, it should just work because the
        # hard-coded paths of the Qt installation should work. If they do not,
        # then it is a distro problem.
        fmts = set(map(lambda x: x.data().decode('utf-8'), QImageReader.supportedImageFormats()))  # no2to3
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

        from calibre.gui2 import ensure_app, destroy_app
        display_env_var = os.environ.pop('DISPLAY', None)
        try:
            ensure_app()
            self.assertGreaterEqual(len(QFontDatabase().families()), 5, 'The QPA headless plugin is not able to locate enough system fonts via fontconfig')
            from calibre.ebooks.covers import create_cover
            create_cover('xxx', ['yyy'])
            na = QNetworkAccessManager()
            self.assertTrue(hasattr(na, 'sslErrors'), 'Qt not compiled with openssl')
            if iswindows:
                from PyQt5.Qt import QtWin
                QtWin
            p = QWebEnginePage()

            def callback(result):
                callback.result = result
                if hasattr(print_callback, 'result'):
                    QApplication.instance().quit()

            def print_callback(result):
                print_callback.result = result
                if hasattr(callback, 'result'):
                    QApplication.instance().quit()

            p.runJavaScript('1 + 1', callback)
            p.printToPdf(print_callback)
            QTimer.singleShot(5000, lambda: QApplication.instance().quit())
            QApplication.instance().exec_()
            test_flaky = ismacos and not is_ci
            if not test_flaky:
                self.assertEqual(callback.result, 2, 'Simple JS computation failed')
                self.assertIn(b'Skia/PDF', bytes(print_callback.result), 'Print to PDF failed')
            del p
            del na
            destroy_app()
            del QWebEnginePage
        finally:
            if display_env_var is not None:
                os.environ['DISPLAY'] = display_env_var

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
        i = Image.open(P('catalog/DefaultCover.jpg', allow_user_override=False))
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
        self.assertGreaterEqual(len(netifaces.interfaces()), 1, 'netifaces could find no network interfaces')

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

    def test_html2text(self):
        import html2text
        del html2text

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
        if ismacos:
            cafile = ssl.get_default_verify_paths().cafile
            if not cafile or not cafile.endswith('/mozilla-ca-certs.pem') or not os.access(cafile, os.R_OK):
                raise AssertionError('Mozilla CA certs not loaded')


def test_multiprocessing():
    from multiprocessing import get_context, get_all_start_methods
    for stype in get_all_start_methods():
        if stype == 'fork':
            continue
        ctx = get_context(stype)
        q = ctx.Queue()
        arg = 'hello'
        p = ctx.Process(target=q.put, args=(arg,))
        p.start()
        try:
            x = q.get(timeout=2)
        except Exception:
            raise SystemExit(f'Failed to get response from worker process with spawn_type: {stype}')
        if x != arg:
            raise SystemExit(f'{x!r} != {arg!r} with spawn_type: {stype}')
        p.join()


def find_tests():
    ans = unittest.defaultTestLoader.loadTestsFromTestCase(BuildTest)
    from calibre.utils.icu_test import find_tests
    ans.addTests(find_tests())
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
