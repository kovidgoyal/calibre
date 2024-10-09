#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Test a binary calibre build to ensure that all needed binary images/libraries have loaded.
'''

import builtins
import ctypes
import os
import shutil
import sys
import time
import unittest

from calibre.constants import islinux, ismacos, iswindows, plugins_loc
from calibre.utils.resources import get_image_path as I
from calibre.utils.resources import get_path as P
from polyglot.builtins import iteritems

is_ci = os.environ.get('CI', '').lower() == 'true'
is_sanitized = 'libasan' in os.environ.get('LD_PRELOAD', '')


def print(*a):
    builtins.print(*a, flush=True, file=sys.__stdout__)


class BuildTest(unittest.TestCase):

    @unittest.skipUnless(iswindows and not is_ci, 'DLL loading needs testing only on windows (non-continuous integration)')
    def test_dlls(self):
        from calibre_extensions import winutil
        base = winutil.get_dll_directory()
        for x in os.listdir(base):
            if x.lower().endswith('.dll'):
                try:
                    ctypes.WinDLL(os.path.join(base, x))
                except Exception as err:
                    self.assertTrue(False, f'Failed to load DLL {x} with error: {err}')

    def test_pycryptodome(self):
        from Crypto.Cipher import AES
        del AES

    @unittest.skipUnless(islinux, 'DBUS only used on linux')
    def test_dbus(self):
        from jeepney.io.blocking import open_dbus_connection
        if 'DBUS_SESSION_BUS_ADDRESS' in os.environ:
            bus = open_dbus_connection(bus='SYSTEM', auth_timeout=10.)
            bus.close()
            bus = open_dbus_connection(bus='SESSION', auth_timeout=10.)
            bus.close()
            del bus

    def test_loaders(self):
        import importlib
        ldr = importlib.import_module('calibre').__spec__.loader.get_resource_reader()
        self.assertIn('ebooks', ldr.contents())
        try:
            with ldr.open_resource('__init__.py') as f:
                raw = f.read()
        except FileNotFoundError:
            with ldr.open_resource('__init__.pyc') as f:
                raw = f.read()
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
        from calibre_extensions.uchardet import detect
        raw = 'mūsi Füße'.encode()
        enc = detect(raw).lower()
        self.assertEqual(enc, 'utf-8')
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

    def test_zstd(self):
        from pyzstd import compress, decompress
        data = os.urandom(4096)
        cdata = compress(data)
        self.assertEqual(data, decompress(cdata))

    def test_html5lib(self):
        import html5lib.html5parser  # noqa
        from html5lib import parse  # noqa

    def test_html5_parser(self):
        from html5_parser import parse
        parse('<p>xxx')

    def test_bs4(self):
        import bs4
        import soupsieve
        del soupsieve, bs4

    @unittest.skipUnless(islinux, 'Speech dispatcher only used on Linux')
    def test_speech_dispatcher(self):
        from speechd.client import SSIPClient
        del SSIPClient

    @unittest.skipIf('SKIP_SPEECH_TESTS' in os.environ, 'Speech support is opted out')
    def test_piper(self):
        import subprocess

        from calibre.constants import piper_cmdline
        self.assertTrue(piper_cmdline())
        raw = subprocess.check_output(piper_cmdline() + ('-h',), stderr=subprocess.STDOUT).decode()
        self.assertIn('--sentence_silence', raw)

    def test_zeroconf(self):
        import ifaddr
        import zeroconf as z
        del z
        del ifaddr

    def test_plugins(self):
        exclusions = set()
        if islinux and not os.path.exists('/dev/bus/usb'):
            # libusb fails to initialize in containers without USB subsystems
            exclusions.update(set('libusb libmtp'.split()))
        from importlib import import_module
        from importlib.resources import files
        for name in (path.name for path in files('calibre_extensions').iterdir()):
            if name in exclusions:
                if name in ('libusb', 'libmtp'):
                    # Just check that the DLL can be loaded
                    ctypes.CDLL(os.path.join(plugins_loc, name + ('.dylib' if ismacos else '.so')))
                continue
            import_module('calibre_extensions.' + name)

    def test_lxml(self):
        from calibre.utils.cleantext import test_clean_xml_chars
        test_clean_xml_chars()
        from lxml import etree
        raw = b'<a/>'
        root = etree.fromstring(raw, parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False))
        self.assertEqual(etree.tostring(root), raw)
        from lxml import html
        html.fromstring("<p>\U0001f63a")

    def test_certgen(self):
        from calibre.utils.certgen import create_key_pair
        create_key_pair()

    def test_fonttools(self):
        from fontTools.subset import main
        main

    def test_msgpack(self):
        from calibre.utils.date import utcnow
        from calibre.utils.serialize import msgpack_dumps, msgpack_loads
        for obj in ({1:1}, utcnow()):
            s = msgpack_dumps(obj)
            self.assertEqual(obj, msgpack_loads(s))
        self.assertEqual(type(msgpack_loads(msgpack_dumps(b'b'))), bytes)
        self.assertEqual(type(msgpack_loads(msgpack_dumps('b'))), str)
        large = b'x' * (100 * 1024 * 1024)
        msgpack_loads(msgpack_dumps(large))

    @unittest.skipUnless(ismacos, 'FSEvents only present on OS X')
    def test_fsevents(self):
        from fsevents import Observer, Stream
        del Observer, Stream

    @unittest.skipUnless(iswindows, 'winutil is windows only')
    def test_winutil(self):
        import tempfile

        from calibre import strftime
        from calibre_extensions import winutil
        self.assertEqual(winutil.special_folder_path(winutil.CSIDL_APPDATA), winutil.known_folder_path(winutil.FOLDERID_RoamingAppData))
        self.assertEqual(winutil.special_folder_path(winutil.CSIDL_LOCAL_APPDATA), winutil.known_folder_path(winutil.FOLDERID_LocalAppData))
        self.assertEqual(winutil.special_folder_path(winutil.CSIDL_FONTS), winutil.known_folder_path(winutil.FOLDERID_Fonts))
        self.assertEqual(winutil.special_folder_path(winutil.CSIDL_PROFILE), winutil.known_folder_path(winutil.FOLDERID_Profile))

        def au(x, name):
            self.assertTrue(
                isinstance(x, str),
                f'{name}() did not return a unicode string, instead returning: {x!r}')
        for x in 'username temp_path locale_name'.split():
            au(getattr(winutil, x)(), x)
        d = winutil.localeconv()
        au(d['thousands_sep'], 'localeconv')
        au(d['decimal_point'], 'localeconv')
        for k, v in iteritems(d):
            au(v, k)
        os.environ['XXXTEST'] = 'YYY'
        self.assertEqual(os.getenv('XXXTEST'), 'YYY')
        del os.environ['XXXTEST']
        self.assertIsNone(os.getenv('XXXTEST'))
        for k in os.environ:
            v = os.getenv(k)
            if v is not None:
                au(v, 'getenv-' + k)
        t = time.localtime()
        fmt = '%Y%a%b%e%H%M'
        for fmt in (fmt, fmt.encode('ascii')):
            x = strftime(fmt, t)
            au(x, 'strftime')
        tdir = tempfile.mkdtemp(dir=winutil.temp_path())
        path = os.path.join(tdir, 'test-create-file.txt')
        h = winutil.create_file(
            path, winutil.GENERIC_READ | winutil.GENERIC_WRITE, 0, winutil.OPEN_ALWAYS, winutil.FILE_ATTRIBUTE_NORMAL)
        self.assertRaises(OSError, winutil.delete_file, path)
        del h
        winutil.delete_file(path)
        self.assertRaises(OSError, winutil.delete_file, path)
        self.assertRaises(OSError, winutil.create_file,
            os.path.join(path, 'cannot'), winutil.GENERIC_READ, 0, winutil.OPEN_ALWAYS, winutil.FILE_ATTRIBUTE_NORMAL)
        self.assertTrue(winutil.supports_hardlinks(os.path.abspath(os.getcwd())[0] + ':\\'))
        sz = 23
        data = os.urandom(sz)
        open(path, 'wb').write(data)
        h = winutil.Handle(0, winutil.ModuleHandle, 'moo')
        r = repr(h)
        h2 = winutil.Handle(h.detach(), winutil.ModuleHandle, 'moo')
        self.assertEqual(r, repr(h2))
        h2.close()

        h = winutil.create_file(
            path, winutil.GENERIC_READ | winutil.GENERIC_WRITE, 0, winutil.OPEN_ALWAYS, winutil.FILE_ATTRIBUTE_NORMAL)
        self.assertEqual(winutil.get_file_size(h), sz)
        self.assertRaises(OSError, winutil.set_file_pointer, h, 23, 23)
        self.assertEqual(winutil.read_file(h), data)
        self.assertEqual(winutil.read_file(h), b'')
        winutil.set_file_pointer(h, 3)
        self.assertEqual(winutil.read_file(h), data[3:])
        self.assertEqual(winutil.nlinks(path), 1)
        npath = path + '.2'
        winutil.create_hard_link(npath, path)
        h.close()
        self.assertEqual(open(npath, 'rb').read(), data)
        self.assertEqual(winutil.nlinks(path), 2)
        winutil.delete_file(path)
        self.assertEqual(winutil.nlinks(npath), 1)
        winutil.set_file_attributes(npath, winutil.FILE_ATTRIBUTE_READONLY)
        self.assertRaises(OSError, winutil.delete_file, npath)
        winutil.set_file_attributes(npath, winutil.FILE_ATTRIBUTE_NORMAL)
        winutil.delete_file(npath)
        self.assertGreater(min(winutil.get_disk_free_space(None)), 0)
        open(path, 'wb').close()
        open(npath, 'wb').close()
        winutil.move_file(path, npath, winutil.MOVEFILE_WRITE_THROUGH | winutil.MOVEFILE_REPLACE_EXISTING)
        self.assertFalse(os.path.exists(path))
        os.remove(npath)
        dpath = tempfile.mkdtemp(dir=os.path.dirname(path))
        dh = winutil.create_file(
            dpath, winutil.FILE_LIST_DIRECTORY, winutil.FILE_SHARE_READ, winutil.OPEN_EXISTING, winutil.FILE_FLAG_BACKUP_SEMANTICS,
        )
        from threading import Event, Thread
        started = Event()
        events = []

        def read_changes():
            buffer = b'0' * 8192
            started.set()
            events.extend(winutil.read_directory_changes(
                dh, buffer, True,
                winutil.FILE_NOTIFY_CHANGE_FILE_NAME |
                winutil.FILE_NOTIFY_CHANGE_DIR_NAME |
                winutil.FILE_NOTIFY_CHANGE_ATTRIBUTES |
                winutil.FILE_NOTIFY_CHANGE_SIZE |
                winutil.FILE_NOTIFY_CHANGE_LAST_WRITE |
                winutil.FILE_NOTIFY_CHANGE_SECURITY
            ))
        t = Thread(target=read_changes, daemon=True)
        t.start()
        started.wait(1)
        t.join(0.1)
        testp = os.path.join(dpath, 'test')
        open(testp, 'w').close()
        t.join(4)
        self.assertTrue(events)
        for actions, path in events:
            self.assertEqual(os.path.join(dpath, path), testp)
        dh.close()
        os.remove(testp)
        os.rmdir(dpath)
        del h
        shutil.rmtree(tdir)
        m = winutil.create_mutex("test-mutex", False)
        self.assertRaises(OSError, winutil.create_mutex, 'test-mutex', False)
        m.close()
        self.assertEqual(winutil.parse_cmdline('"c:\\test exe.exe" "some arg" 2'), ('c:\\test exe.exe', 'some arg', '2'))

    def test_ffmpeg(self):
        from calibre_extensions.ffmpeg import resample_raw_audio_16bit
        data = os.urandom(22050 * 2)
        resample_raw_audio_16bit(data, 22050, 44100)

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
        if is_sanitized:
            raise unittest.SkipTest('Skipping Qt build test as sanitizer is enabled')
        from qt.core import QApplication, QFontDatabase, QImageReader, QLoggingCategory, QNetworkAccessManager, QSslSocket, QTimer
        QLoggingCategory.setFilterRules('''qt.webenginecontext.debug=true''')
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            # likely a container build, webengine cannot run as root with sandbox
            os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--no-sandbox'
        from qt.webengine import QWebEnginePage

        from calibre.utils.img import image_from_data, image_to_data, test

        # Ensure that images can be read before QApplication is constructed.
        # Note that this requires QCoreApplication.libraryPaths() to return the
        # path to the Qt plugins which it always does in the frozen build,
        # because Qt is patched to know the layout of the calibre application
        # package. On non-frozen builds, it should just work because the
        # hard-coded paths of the Qt installation should work. If they do not,
        # then it is a distro problem.
        fmts = set(map(lambda x: x.data().decode('utf-8'), QImageReader.supportedImageFormats()))  # no2to3
        testf = {'jpg', 'png', 'svg', 'ico', 'gif', 'webp'}
        self.assertEqual(testf.intersection(fmts), testf, "Qt doesn't seem to be able to load some of its image plugins. Available plugins: %s" % fmts)
        data = P('images/blank.png', allow_user_override=False, data=True)
        img = image_from_data(data)
        image_from_data(P('catalog/mastheadImage.gif', allow_user_override=False, data=True))
        for fmt in 'png bmp jpeg'.split():
            d = image_to_data(img, fmt=fmt)
            image_from_data(d)
        # Run the imaging tests
        test()

        from calibre.gui2 import destroy_app, ensure_app
        from calibre.utils.webengine import setup_profile
        display_env_var = os.environ.pop('DISPLAY', None)
        try:
            ensure_app()
            self.assertGreaterEqual(len(QFontDatabase.families()), 5, 'The QPA headless plugin is not able to locate enough system fonts via fontconfig')

            if 'SKIP_SPEECH_TESTS' not in os.environ:
                from qt.core import QMediaDevices, QTextToSpeech

                available_tts_engines = tuple(x for x in QTextToSpeech.availableEngines() if x != 'mock')
                self.assertTrue(available_tts_engines)

                QMediaDevices.audioOutputs()

            from calibre.ebooks.oeb.transforms.rasterize import rasterize_svg
            img = rasterize_svg(as_qimage=True)
            self.assertFalse(img.isNull())
            self.assertGreater(img.width(), 8)
            from calibre.ebooks.covers import create_cover
            create_cover('xxx', ['yyy'])
            na = QNetworkAccessManager()
            self.assertTrue(hasattr(na, 'sslErrors'), 'Qt not compiled with openssl')
            self.assertTrue(QSslSocket.availableBackends(), 'Qt tls plugins missings')
            p = QWebEnginePage()
            setup_profile(p.profile())

            def callback(result):
                callback.result = result
                if hasattr(print_callback, 'result'):
                    QApplication.instance().quit()

            def print_callback(result):
                print_callback.result = result
                if hasattr(callback, 'result'):
                    QApplication.instance().quit()

            def do_webengine_test(title):
                nonlocal p
                p.runJavaScript('1 + 1', callback)
                p.printToPdf(print_callback)

            def render_process_crashed(status, exit_code):
                print('Qt WebEngine Render process crashed with status:', status, 'and exit code:', exit_code)
                QApplication.instance().quit()

            p.titleChanged.connect(do_webengine_test)
            p.renderProcessTerminated.connect(render_process_crashed)
            p.runJavaScript(f'document.title = "test-run-{os.getpid()}";')
            timeout = 10
            QTimer.singleShot(timeout * 1000, lambda: QApplication.instance().quit())
            QApplication.instance().exec()
            self.assertTrue(hasattr(callback, 'result'), f'Qt WebEngine failed to run in {timeout} seconds')
            self.assertEqual(callback.result, 2, 'Simple JS computation failed')
            self.assertTrue(hasattr(print_callback, 'result'), f'Qt WebEngine failed to print in {timeout} seconds')
            self.assertIn(b'%PDF-1.4', bytes(print_callback.result), 'Print to PDF failed')
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
            import _imaging
            import _imagingft
            import _imagingmath
            _imaging, _imagingmath, _imagingft
        except ImportError:
            from PIL import _imaging, _imagingft, _imagingmath
        _imaging, _imagingmath, _imagingft
        from io import StringIO

        from PIL import features
        out = StringIO()
        features.pilinfo(out=out, supported_formats=False)
        out = out.getvalue()
        for line in '''\
        --- PIL CORE support ok
        --- FREETYPE2 support ok
        --- WEBP support ok
        --- WEBP Transparency support ok
        --- WEBPMUX support ok
        --- WEBP Animation support ok
        --- JPEG support ok
        --- ZLIB (PNG/ZIP) support ok
        '''.splitlines():
            self.assertIn(line.strip(), out)
        with Image.open(I('lt.png', allow_user_override=False)) as i:
            self.assertGreaterEqual(i.size, (20, 20))
        with Image.open(P('catalog/DefaultCover.jpg', allow_user_override=False)) as i:
            self.assertGreaterEqual(i.size, (20, 20))

    @unittest.skipUnless(iswindows and not is_ci, 'File dialog helper only used on windows (non-continuous-integration)')
    def test_file_dialog_helper(self):
        from calibre.gui2.win_file_dialogs import test
        test()

    def test_unrar(self):
        from calibre.utils.unrar import test_basic
        test_basic()

    def test_7z(self):
        from calibre.utils.seven_zip import test_basic
        test_basic()

    @unittest.skipUnless(iswindows, 'WPD is windows only')
    def test_wpd(self):
        from calibre_extensions import wpd
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
        from calibre.ebooks.pdf.pdftohtml import PDFTOHTML, PDFTOTEXT
        from calibre.utils.ipc.launch import Worker
        w = Worker({})
        self.assertTrue(os.path.exists(w.executable), 'calibre-parallel (%s) does not exist' % w.executable)
        self.assertTrue(os.path.exists(w.gui_executable), 'calibre-parallel-gui (%s) does not exist' % w.gui_executable)
        self.assertTrue(os.path.exists(PDFTOHTML), 'pdftohtml (%s) does not exist' % PDFTOHTML)
        self.assertTrue(os.path.exists(PDFTOTEXT), 'pdftotext (%s) does not exist' % PDFTOTEXT)
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
        from calibre.ebooks.conversion.plugins.txt_input import MD_EXTENSIONS
        from calibre.ebooks.txt.processor import create_markdown_object
        create_markdown_object(sorted(MD_EXTENSIONS))
        from calibre.library.comments import sanitize_comments_html
        sanitize_comments_html(b'''<script>moo</script>xxx<img src="http://moo.com/x.jpg">''')

    def test_feedparser(self):
        # sgmllib is needed for feedparser parsing malformed feeds
        # on python3 you can get it by taking it from python2 stdlib and
        # running 2to3 on it
        import sgmllib

        from calibre.web.feeds.feedparser import parse
        sgmllib, parse

    def test_openssl(self):
        import ssl
        ssl.PROTOCOL_TLSv1_2
        if ismacos:
            cafile = ssl.get_default_verify_paths().cafile
            if not cafile or not cafile.endswith('/mozilla-ca-certs.pem') or not os.access(cafile, os.R_OK):
                raise AssertionError('Mozilla CA certs not loaded')
        # On Fedora create_default_context() succeeds in the main thread but
        # not in other threads, because upstream OpenSSL cannot read whatever
        # shit Fedora puts in /etc/ssl, so this check makes sure our bundled
        # OpenSSL is built with ssl dir that is not /etc/ssl
        from threading import Thread
        certs_loaded = False
        def check_ssl_loading_certs():
            nonlocal certs_loaded
            ssl.create_default_context()
            certs_loaded = True
        t = Thread(target=check_ssl_loading_certs)
        t.start()
        t.join()
        if not certs_loaded:
            raise AssertionError('Failed to load SSL certificates')


def test_multiprocessing():
    from multiprocessing import get_all_start_methods, get_context
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


def find_tests(only_build=False):
    ans = unittest.defaultTestLoader.loadTestsFromTestCase(BuildTest)
    if only_build:
        return ans
    from calibre.utils.icu_test import find_tests
    ans.addTests(find_tests())
    from tinycss.tests.main import find_tests
    ans.addTests(find_tests())
    from calibre.spell.dictionary import find_tests
    ans.addTests(find_tests())
    from calibre.db.tests.fts import find_tests
    ans.addTests(find_tests())
    return ans


def test():
    from calibre.utils.run_tests import run_cli
    run_cli(find_tests())


if __name__ == '__main__':
    test()
