#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import asyncio
import functools
import http.server
import itertools
import json
import math
import os
import random
import socketserver
import struct
import tempfile
import threading
import time
import unittest
from collections.abc import Awaitable, Callable
from unittest.mock import patch

from calibre.constants import iswindows
from calibre.web.automate import camoufox
from calibre.web.automate.download_deps import camoufox_installer, camoufox_resource_dir

TEST_PAGE = '''<!DOCTYPE html><html><head><title>Test Page</title></head><body>
<h1 id="title">Hello</h1>
<div id="container"><p class="para">one</p><p class="para">two</p></div>
<img id="pic" src="pic.svg" alt="a picture">
<script>setTimeout(() => {
    const d = document.createElement('div');
    d.id = 'late'; d.textContent = 'appeared';
    document.body.appendChild(d);
}, 300);</script>
</body></html>'''

CLICK_PAGE = '''<!DOCTYPE html><html><head><title>Click Test</title><style>
body { margin: 0; height: 4000px; }
#btn { position: absolute; left: 40px; top: 30px; width: 120px; height: 40px; }
#far { position: absolute; left: 60px; top: 3000px; }
#hidden { display: none; }
</style></head><body>
<button id="btn">Press me</button>
<a href="#x" id="far">far away</a>
<span id="hidden">invisible</span>
</body></html>'''

# Installed by the tests rather than by the page itself, because scripts in the
# page run in a different JavaScript world from the one evaluate() uses
RECORDER_JS = '''() => {
    window.__moves = [];
    window.__events = [];
    window.__reset = () => { window.__moves = []; window.__events = []; };
    document.addEventListener('mousemove', (e) => window.__moves.push([e.clientX, e.clientY]), true);
    for (const type of ['mousedown', 'mouseup', 'click', 'dblclick', 'contextmenu'])
        document.addEventListener(type, (e) => window.__events.push({
            type: e.type, target: e.target.id, x: e.clientX, y: e.clientY, at: performance.now(),
            button: e.button, buttons: e.buttons, detail: e.detail,
            alt: e.altKey, ctrl: e.ctrlKey, shift: e.shiftKey, meta: e.metaKey}), true);
}'''

RECT_JS = '''(id) => {
    const r = document.getElementById(id).getBoundingClientRect();
    return {left: r.left, top: r.top, right: r.right, bottom: r.bottom};
}'''

TYPE_PAGE = '''<!DOCTYPE html><html><head><title>Type Test</title></head><body>
<form id="form" action="second.html">
<input id="text" name="q" value="old">
<button id="go" type="submit">go</button>
</form>
<textarea id="area"></textarea>
<div id="rich" contenteditable="true">old text</div>
<input id="ro" value="fixed" readonly>
</body></html>'''

KEY_RECORDER_JS = '''() => {
    window.__keys = [];
    window.__inputs = [];
    window.__submitted = false;
    window.__reset = () => { window.__keys = []; window.__inputs = []; window.__submitted = false; };
    for (const type of ['keydown', 'keyup', 'keypress'])
        document.addEventListener(type, (e) => window.__keys.push({
            type: e.type, key: e.key, code: e.code, keyCode: e.keyCode, location: e.location,
            repeat: e.repeat, at: performance.now(), target: e.target.id,
            alt: e.altKey, ctrl: e.ctrlKey, shift: e.shiftKey, meta: e.metaKey}), true);
    document.addEventListener('input', (e) => window.__inputs.push({
        data: e.data ?? null, inputType: e.inputType || '', at: performance.now()}), true);
    document.getElementById('form').addEventListener('submit', (e) => {
        e.preventDefault(); window.__submitted = true; });
}'''

TEST_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="red"/></svg>'

# How fast the browser shared by the tests types, in words per minute. Well
# above what a hand manages, but far enough below the floor a keystroke gap is
# clamped to, MIN_KEY_INTERVAL, that the gaps are still visibly uneven. What
# the default speed produces is checked by the tests of human_typing_plan(),
# which need no browser.
TEST_TYPING_WPM = 240.0
# The longest a cursor movement made by the shared browser may take, in
# seconds. Same idea: shorter than a hand takes, but long enough that the
# movement is still a path of its own rather than a jump.
TEST_MAX_MOVE_TIME = 0.3


def installed_camoufox() -> tuple[str, str] | None:
    """The camoufox install, but only if it is already present, so that running
    the test suite never downloads hundreds of megabytes."""
    try:
        metadata_path = camoufox_installer.metadata_path
        with open(metadata_path, 'rb') as f:
            version = json.loads(f.read())['version']
        if not camoufox_installer.is_installed(version):
            return None
        binary = camoufox_installer.payload_path(camoufox_installer.version_dir(version))
    except Exception:
        return None
    return binary, version


class TestCamoufoxConfig(unittest.TestCase):
    """Tests for generating the browser fingerprint. These never touch the network."""

    def test_cast_to_properties(self) -> None:
        config: dict = {}
        camoufox.cast_to_properties(
            config,
            camoufox.BROWSERFORGE_MAP,
            {
                'navigator': {
                    'userAgent': 'Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0',
                    'hardwareConcurrency': 8,
                    'vendor': 'ignored, not in the map',
                    'extraProperties': {'globalPrivacyControl': True, 'ignored': 1},
                },
                'screen': {'width': 1920, 'availLeft': -20, 'outerWidth': 1280, 'height': 0},
                'battery': {'charging': True},
                'unknownSection': {'x': 1},
            },
            '152',
        )
        self.assertEqual(config['navigator.hardwareConcurrency'], 8)
        self.assertEqual(config['navigator.globalPrivacyControl'], True)
        self.assertEqual(config['battery:charging'], True)
        self.assertEqual(config['screen.width'], 1920)
        self.assertEqual(config['window.outerWidth'], 1280)
        # Negative screen coordinates are impossible, they get clamped
        self.assertEqual(config['screen.availLeft'], 0)
        # Falsey values mean "not generated" and are skipped entirely
        self.assertNotIn('screen.height', config)
        # The browserforge Firefox version is replaced with the one we run
        self.assertEqual(config['navigator.userAgent'], 'Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0')

    def test_screen_y(self) -> None:
        config: dict = {}
        camoufox.set_screen_y(config, {'screenX': 0})
        self.assertEqual((config['window.screenX'], config['window.screenY']), (0, 0))
        config = {}
        camoufox.set_screen_y(config, {'screenX': 25})
        self.assertEqual(config['window.screenY'], 25)
        config = {}
        camoufox.set_screen_y(config, {'screenX': 500, 'availHeight': 1000, 'outerHeight': 900})
        self.assertIn(config['window.screenY'], range(100))
        config = {'window.screenY': 7}
        camoufox.set_screen_y(config, {'screenX': 500})
        self.assertEqual(config['window.screenY'], 7)  # an explicit value is left alone

    def test_clamp_window_dimensions(self) -> None:
        config = {
            'screen.availWidth': 1000,
            'screen.availHeight': 800,
            'window.outerWidth': 1600,
            'window.outerHeight': 400,
            'window.innerWidth': 1600,
            'window.innerHeight': 900,
        }
        camoufox.clamp_window_dimensions(config)
        self.assertEqual(config['window.outerWidth'], 1000)  # cannot be wider than the screen
        self.assertEqual(config['window.outerHeight'], 400)  # already fits
        self.assertEqual(config['window.innerWidth'], 1000)  # cannot be wider than the window
        self.assertEqual(config['window.innerHeight'], 400)

    def test_fix_navigator_arch(self) -> None:
        for target_os, platform in (('windows', 'Win32'), ('macos', 'MacIntel'), ('linux', 'Linux x86_64')):
            config: dict = {}
            camoufox.fix_navigator_arch(config, target_os)
            self.assertEqual(config['navigator.platform'], platform)
            self.assertTrue(config['navigator.oscpu'])
        config = {'navigator.platform': 'custom'}
        camoufox.fix_navigator_arch(config, 'windows')
        self.assertEqual(config['navigator.platform'], 'custom')

    def test_config_environment(self) -> None:
        env = camoufox.config_environment({'navigator.userAgent': 'x'})
        self.assertEqual(json.loads(env['CAMOU_CONFIG_1']), {'navigator.userAgent': 'x'})
        chunk_size = 2047 if iswindows else 32767
        big = camoufox.config_environment({'fonts': ['a' * 100] * 2000})
        self.assertGreater(len(big), 1)
        joined = ''.join(big[f'CAMOU_CONFIG_{i + 1}'] for i in range(len(big)))
        self.assertEqual(len(json.loads(joined)['fonts']), 2000)
        for i in range(len(big) - 1):  # every chunk but the last is full
            self.assertEqual(len(big[f'CAMOU_CONFIG_{i + 1}']), chunk_size)

    def test_value_has_type(self) -> None:
        for value, expected, ok in (
            ('x', 'str', True),
            (1, 'str', False),
            (True, 'bool', True),
            (1, 'bool', False),
            (5, 'int', True),
            (-5, 'int', True),
            (True, 'int', False),
            (5.0, 'int', True),
            (5.5, 'int', False),
            (5, 'uint', True),
            (-5, 'uint', False),
            (5.5, 'double', True),
            (5, 'double', True),
            (True, 'double', False),
            ([], 'array', True),
            ({}, 'array', False),
            ({}, 'dict', True),
            ([], 'dict', False),
            ('x', 'nonesuch', False),
        ):
            self.assertIs(camoufox.value_has_type(value, expected), ok, f'{value!r} as {expected}')

    def test_random_font_subset(self) -> None:
        families = ('Arimo', 'Cousine', 'Tinos', 'Twemoji Mozilla') + tuple(f'Noto Sans {i}' for i in range(50))
        for _ in range(10):
            subset = camoufox.random_font_subset(families, 'linux')
            self.assertEqual(subset, sorted(subset))
            self.assertEqual(len(set(subset)), len(subset), 'the subset contains duplicates')
            for font in camoufox.MARKER_FONTS['linux']:
                self.assertIn(font, subset, 'an OS marker font is missing')
            for font in ('Arimo', 'Cousine', 'Tinos'):
                self.assertIn(font, subset, 'an essential font is missing')
            self.assertLess(len(subset), len(families), 'the subset is not actually a subset')
        # A marker font that the browser cannot render must never be claimed
        subset = camoufox.random_font_subset(('Arimo',), 'linux')
        self.assertEqual(subset, ['Arimo'])

    def test_check_valid_os(self) -> None:
        self.assertEqual(camoufox.check_valid_os('linux'), 'linux')
        self.assertRaises(ValueError, camoufox.check_valid_os, 'plan9')


class TestCamoufoxTransport(unittest.TestCase):
    """Tests for the plumbing used to talk to the browser process."""

    @unittest.skipIf(iswindows, 'file descriptors are not renumbered on Windows')
    def test_reserve_high_fd(self) -> None:
        read_fd, write_fd = os.pipe()
        try:
            read_fd = camoufox.reserve_high_fd(read_fd, minimum=32)
            self.assertGreaterEqual(read_fd, 32)
            os.write(write_fd, b'hello')
            self.assertEqual(os.read(read_fd, 5), b'hello')
        finally:
            camoufox.close_fd(read_fd)
            camoufox.close_fd(write_fd)

    def test_remove_profile_dir(self) -> None:
        """The profile directory is deleted even if it is briefly undeletable."""
        base = tempfile.mkdtemp()
        self.addCleanup(camoufox.remove_profile_dir, base)

        def make_profile(name: str) -> str:
            path = os.path.join(base, name)
            os.makedirs(os.path.join(path, 'sub'))
            with open(os.path.join(path, 'sub', 'file.txt'), 'w') as f:
                f.write('some profile data')
            return path

        path = make_profile('plain')
        camoufox.remove_profile_dir(path)
        self.assertFalse(os.path.exists(path))
        # Deleting one that is already gone is not an error
        camoufox.remove_profile_dir(path)

        # A file held open by something else, which is routine on Windows,
        # only delays the deletion, it does not prevent it
        path = make_profile('locked')
        real_rmtree, attempts = camoufox.shutil.rmtree, []

        def rmtree_that_is_busy_at_first(target: str) -> None:
            attempts.append(target)
            if len(attempts) < 3:
                raise PermissionError(f'{target} is in use by another process')
            real_rmtree(target)

        with patch.object(camoufox.shutil, 'rmtree', rmtree_that_is_busy_at_first):
            camoufox.remove_profile_dir(path)
        self.assertEqual(len(attempts), 3)
        self.assertFalse(os.path.exists(path))

        # One that never becomes deletable is handed to the atexit worker
        # instead of raising or blocking forever
        path = make_profile('wedged')
        deferred: list[str] = []

        def always_busy(target: str) -> None:
            raise PermissionError(f'{target} is in use by another process')

        with (
            patch.object(camoufox.shutil, 'rmtree', always_busy),
            patch.object(camoufox, 'remove_folder_atexit', deferred.append),
            patch.object(camoufox, 'debug', lambda *a: None),
        ):
            camoufox.remove_profile_dir(path, timeout=0)
        self.assertEqual(deferred, [path])
        self.assertTrue(os.path.exists(path))

    def test_crt_handle_block(self) -> None:
        """The layout of the inherited file descriptor block handed to Windows.

        The browser finds its pipes with _get_osfhandle(3)/(4), so getting this
        wrong means it never sees them. Checked on every platform because the
        layout is fixed and the Windows code path cannot be exercised elsewhere.
        """
        handles = (-1, 0x10, 0x14, 0x120, 0x124)
        flags = (0, camoufox.FOPEN | camoufox.FDEV, camoufox.FOPEN | camoufox.FDEV, camoufox.FOPEN | camoufox.FPIPE, camoufox.FOPEN | camoufox.FPIPE)
        for handle_size in (4, 8):
            block = camoufox.crt_handle_block(handles, flags, handle_size)
            self.assertEqual(len(block), 4 + len(handles) * (1 + handle_size))
            self.assertEqual(struct.unpack_from('<I', block)[0], 5, 'the descriptor count is wrong')
            self.assertEqual(tuple(block[4 : 4 + 5]), (0, 0x41, 0x41, 0x09, 0x09), 'the flags bytes are wrong')
            fmt = '<Q' if handle_size == 8 else '<I'
            got = struct.unpack_from(f'<{len(handles)}{fmt[1]}', block, 9)
            # An unused descriptor is INVALID_HANDLE_VALUE, all bits set
            self.assertEqual(got, (2 ** (8 * handle_size) - 1, 0x10, 0x14, 0x120, 0x124))
        self.assertRaises(ValueError, camoufox.crt_handle_block, (1, 2), (0,))

    def test_message_framing(self) -> None:
        """The browser sends NUL delimited JSON, which can be split across reads."""
        received: list[bytes] = []
        to_browser_read, to_browser_write = os.pipe()
        from_browser_read, from_browser_write = os.pipe()

        async def run() -> None:
            all_received, closed = asyncio.Event(), asyncio.Event()

            def on_message(message: bytes) -> None:
                received.append(message)
                if len(received) == 3:
                    all_received.set()

            transport = camoufox.Transport(from_browser_read, to_browser_write, asyncio.get_running_loop(), on_message, closed.set)
            try:
                # One message split over two writes, then two messages in one write
                os.write(from_browser_write, b'{"id":1,"resu')
                os.write(from_browser_write, b'lt":{}}\0{"id":2}\0{"id":3}\0')
                transport.send({'method': 'Browser.enable'})
                self.assertEqual(os.read(to_browser_read, 4096), b'{"method":"Browser.enable"}\0')
                async with asyncio.timeout(30):
                    await all_received.wait()
                    # Closing the browser end must be reported as a lost connection
                    os.close(from_browser_write)
                    await closed.wait()
            finally:
                transport.close()
                camoufox.close_fd(from_browser_read)

        try:
            asyncio.run(run())
        finally:
            camoufox.close_fd(to_browser_read)
        self.assertEqual([json.loads(x) for x in received], [{'id': 1, 'result': {}}, {'id': 2}, {'id': 3}])

    def test_connection_dispatch(self) -> None:
        connection = camoufox.Connection()
        root_events: list[tuple[str, dict]] = []
        session_events: list[tuple[str, dict]] = []
        connection.root_handler = lambda method, params: root_events.append((method, params))
        connection.event_handlers['s1'] = lambda method, params: session_events.append((method, params))

        async def run() -> None:
            future: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
            connection.replies[7] = future
            connection.message_received(b'{"id": 7, "result": {"targetId": "t1"}}')
            self.assertEqual((await future)['result'], {'targetId': 't1'})
            connection.message_received(b'{"method": "Browser.attachedToTarget", "params": {"a": 1}}')
            connection.message_received(b'{"method": "Page.ready", "params": {}, "sessionId": "s1"}')
            connection.message_received(b'{"method": "Page.ready", "params": {}, "sessionId": "unknown"}')
            connection.message_received(b'not json at all')  # must not raise
            connection.message_received(b'{"id": 999, "result": {}}')  # a reply nobody is waiting for

        asyncio.run(run())
        self.assertEqual(root_events, [('Browser.attachedToTarget', {'a': 1})])
        self.assertEqual(session_events, [('Page.ready', {})])

    def test_event_waiter(self) -> None:
        waiter = camoufox.EventWaiter()

        async def run() -> None:
            future = waiter.expect(lambda method, params: method == 'Page.ready')
            waiter.dispatch('Page.crashed', {})
            self.assertFalse(future.done())
            waiter.dispatch('Page.ready', {'x': 1})
            event = await future
            self.assertEqual((event.method, event.params), ('Page.ready', {'x': 1}))
            self.assertFalse(waiter.waiters, 'a matched waiter was not removed')
            # A predicate that raises must not stop other waiters from matching
            waiter.expect(lambda method, params: params['missing'] == 1)
            other = waiter.expect(lambda method, params: True)
            waiter.dispatch('Page.ready', {})
            await other
            aborted = waiter.expect(lambda method, params: False)
            waiter.abort(camoufox.BrowserClosedError('closed'))
            with self.assertRaises(camoufox.BrowserClosedError):
                await aborted

        asyncio.run(run())


class TestCamoufoxFonts(unittest.TestCase):
    def test_sfnt_name_table(self) -> None:
        self.assertIsNone(camoufox.sfnt_name_table(b'too short'))
        self.assertIsNone(camoufox.sfnt_name_table(b'\x00\x01\x00\x00' + b'\x00\x00' * 4))

    @unittest.skipIf(installed_camoufox() is None, 'the camoufox browser is not installed')
    def test_bundled_font_families(self) -> None:
        install = installed_camoufox()
        assert install is not None
        resource_dir = camoufox_resource_dir(install[0])
        families = camoufox.font_families(resource_dir, install[1], 'linux')
        self.assertGreater(len(families), 100)
        for font in camoufox.MARKER_FONTS['linux']:
            self.assertIn(font, families, 'a Linux OS marker font is missing from the bundled fonts')
        # The second call must come from the on disk cache and agree
        self.assertEqual(families, camoufox.font_families(resource_dir, install[1], 'linux'))

    def test_fontconfig_generation(self) -> None:
        # Only the Linux camoufox bundle ships the fontconfig directories, as
        # it is the only platform on which the browser needs to be told where
        # its bundled fonts are, so use a fake resource dir, which also means
        # this test runs even without the browser installed.
        for dirname in ('fontconfig', 'fontconfigs'):  # renamed in camoufox v150
            with tempfile.TemporaryDirectory(prefix='camoufox-test-') as tdir:
                os.makedirs(os.path.join(tdir, dirname, 'windows'))
                with open(os.path.join(tdir, dirname, 'windows', 'fonts.conf'), 'w') as f:
                    f.write('<fontconfig><dir prefix="cwd">fonts</dir></fontconfig>')
                version = 'test-' + os.path.basename(tdir)
                path = camoufox.fontconfig_path(tdir, version, 'windows')
                self.addCleanup(os.remove, path)
                with open(path) as f:
                    conf = f.read()
                self.assertNotIn('prefix="cwd"', conf, 'the relative font dir was not made absolute')
                self.assertIn(f'<dir>{os.path.join(tdir, "fonts")}</dir>', conf)
                with self.assertRaises(camoufox.Error):  # no fonts.conf for this target OS
                    camoufox.fontconfig_path(tdir, version, 'linux')

    @unittest.skipIf(
        installed_camoufox() is None or camoufox.current_os() != 'linux',
        'the camoufox browser is not installed, or this is not Linux, and only the Linux bundle has fontconfig files',
    )
    def test_bundled_fontconfig(self) -> None:
        install = installed_camoufox()
        assert install is not None
        resource_dir = camoufox_resource_dir(install[0])
        path = camoufox.fontconfig_path(resource_dir, install[1], 'windows')
        with open(path) as f:
            conf = f.read()
        self.assertNotIn('prefix="cwd"', conf, 'the relative font dir was not made absolute')
        self.assertIn(f'<dir>{os.path.join(resource_dir, "fonts")}</dir>', conf)


class Server:
    """Serves the test pages over HTTP, so that the browser treats them the way
    it treats a real web page."""

    def __init__(self) -> None:
        self.dir = tempfile.mkdtemp(prefix='camoufox-test-')
        with open(os.path.join(self.dir, 'index.html'), 'w') as f:
            f.write(TEST_PAGE)
        with open(os.path.join(self.dir, 'second.html'), 'w') as f:
            f.write('<!DOCTYPE html><html><head><title>Second</title></head><body><h1>Second</h1></body></html>')
        with open(os.path.join(self.dir, 'click.html'), 'w') as f:
            f.write(CLICK_PAGE)
        with open(os.path.join(self.dir, 'type.html'), 'w') as f:
            f.write(TYPE_PAGE)
        with open(os.path.join(self.dir, 'pic.svg'), 'w') as f:
            f.write(TEST_SVG)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a: object) -> None:
                pass

            def end_headers(self) -> None:
                # The tests share a browser, so without this the pages and
                # images one of them loads are served to the next one out of
                # the cache, which is not the fresh response with headers of
                # its own that they are written against
                self.send_header('Cache-Control', 'no-store')
                super().end_headers()

        self.httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Handler, directory=self.dir))
        self.thread = threading.Thread(target=self.httpd.serve_forever, name='CamoufoxTestServer', daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.httpd.server_address[1]}/'

    def close(self) -> None:
        import shutil

        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=10)
        shutil.rmtree(self.dir, ignore_errors=True)


class TestCamoufoxMouse(unittest.TestCase):
    """Tests for generating human like cursor paths. These never touch the browser."""

    def test_trajectory_shape(self) -> None:
        start, end = (0.0, 0.0), (400.0, 300.0)
        distance = math.hypot(*end)
        curved = 0
        for seed in range(24):
            path = camoufox.human_trajectory(start, end, rng=random.Random(seed))
            self.assertTrue(path)
            self.assertLessEqual(len(path), camoufox.MAX_MOVE_STEPS)
            # It must arrive exactly where it was asked to
            self.assertEqual(path[-1][:2], end)
            for x, y, t in path:
                self.assertTrue(math.isfinite(x) and math.isfinite(y) and math.isfinite(t))
            # Time must run forwards, from after the movement starts to the end of it
            times = [t for _, _, t in path]
            self.assertEqual(times, sorted(times))
            self.assertGreater(times[0], 0)
            self.assertGreaterEqual(times[-1], camoufox.MIN_MOVE_TIME)
            self.assertLessEqual(times[-1], camoufox.MAX_MOVE_TIME)
            # The path must bow away from the straight line rather than being a ruler edge
            deviation = max(abs((end[0] * y - end[1] * x) / distance) for x, y, _ in path)
            self.assertLess(deviation, distance, 'the path wandered absurdly far off course')
            if deviation > 1:
                curved += 1
        self.assertEqual(curved, 24, 'some paths were straight lines')

    def test_trajectory_timing(self) -> None:
        # A movement that lands on the pixel the cursor is already on is not worth making
        self.assertEqual(camoufox.human_trajectory((10.0, 10.0), (10.4, 9.7)), [])
        for seed in range(8):
            rng = random.Random(seed)
            # Distant targets take longer to reach than close ones, but not proportionally
            near = camoufox.human_trajectory((0.0, 0.0), (30.0, 0.0), rng=random.Random(seed))
            far = camoufox.human_trajectory((0.0, 0.0), (1200.0, 0.0), rng=random.Random(seed))
            self.assertLess(near[-1][2], far[-1][2])
            self.assertLess(far[-1][2], 12 * near[-1][2])
            # An explicit budget is honoured
            capped = camoufox.human_trajectory((0.0, 0.0), (1200.0, 800.0), max_time=0.2, rng=rng)
            self.assertLessEqual(capped[-1][2], 0.2)
        # The same seed must give the same path, so that failures are reproducible
        self.assertEqual(
            camoufox.human_trajectory((0.0, 0.0), (100.0, 50.0), rng=random.Random(3)),
            camoufox.human_trajectory((0.0, 0.0), (100.0, 50.0), rng=random.Random(3)),
        )

    def test_trajectory_overshoot(self) -> None:
        def overshoots(end: tuple[float, float], seed: int) -> bool:
            distance = math.hypot(*end)
            path = camoufox.human_trajectory((0.0, 0.0), end, rng=random.Random(seed))
            return max((x * end[0] + y * end[1]) / distance for x, y, _ in path) > distance + 1

        # A hand shoots past a distant target sometimes and a close one never
        self.assertTrue(any(overshoots((700.0, 500.0), seed) for seed in range(20)))
        self.assertFalse(any(overshoots((60.0, 40.0), seed) for seed in range(20)))

    def test_ease(self) -> None:
        self.assertEqual(camoufox.ease(0.0), 0.0)
        self.assertEqual(camoufox.ease(1.0), 1.0)
        values = [camoufox.ease(i / 20) for i in range(21)]
        self.assertEqual(values, sorted(values))
        # Biased so that the cursor speeds up faster than it slows down
        self.assertGreater(camoufox.ease(0.5), 0.5)

    def test_quads(self) -> None:
        square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        self.assertEqual(camoufox.quad_area(square), 100)
        self.assertEqual(camoufox.quad_area([(0.0, 0.0)] * 4), 0)
        self.assertTrue(camoufox.quad_contains(square, (5.0, 5.0)))
        self.assertFalse(camoufox.quad_contains(square, (11.0, 5.0)))
        self.assertEqual(camoufox.point_to_aim_at(square), (5.0, 5.0))
        # Whole pixels are preferred, since hit testing between them is unreliable
        self.assertEqual(camoufox.point_to_aim_at([(0.0, 0.0), (9.4, 0.0), (9.4, 9.4), (0.0, 9.4)]), (5.0, 5.0))
        quad = {'p1': {'x': -5, 'y': -5}, 'p2': {'x': 50, 'y': -5}, 'p3': {'x': 50, 'y': 50}, 'p4': {'x': -5, 'y': 50}}
        self.assertEqual(camoufox.clamp_quad(quad, 20, 30), [(0.0, 0.0), (20.0, 0.0), (20.0, 30.0), (0.0, 30.0)])

    def test_clamp_to_viewport(self) -> None:
        self.assertEqual(camoufox.VIEWPORT_MARGIN, 1.0)
        # A position outside the viewport is brought to the nearest usable pixel inside it
        self.assertEqual(camoufox.clamp_to_viewport(-3.0, 4.4, 100.0, 50.0), (1.0, 4.0))
        self.assertEqual(camoufox.clamp_to_viewport(120.0, 60.0, 100.0, 50.0), (98.0, 48.0))
        # The edge of the viewport is left alone, an event there is never acknowledged
        self.assertEqual(camoufox.clamp_to_viewport(0.0, 0.0, 100.0, 50.0), (1.0, 1.0))
        self.assertEqual(camoufox.clamp_to_viewport(99.0, 49.0, 100.0, 50.0), (98.0, 48.0))
        # One already inside is only snapped onto a whole pixel
        self.assertEqual(camoufox.clamp_to_viewport(10.5, 20.4, 100.0, 50.0), (11.0, 20.0))
        # A viewport too small to have an inside does not produce a position outside it
        self.assertEqual(camoufox.clamp_to_viewport(5.0, 5.0, 0.0, 0.0), (0.0, 0.0))
        self.assertEqual(camoufox.clamp_to_viewport(5.0, 5.0, 2.0, 2.0), (0.0, 0.0))

    def test_buttons_and_modifiers(self) -> None:
        self.assertEqual(camoufox.mouse_button('right'), (2, 2))
        self.assertEqual(camoufox.modifier_mask(()), 0)
        self.assertEqual(camoufox.modifier_mask(('alt', 'shift')), 5)
        for bad in (lambda: camoufox.mouse_button('sideways'), lambda: camoufox.modifier_mask(('hyper',))):
            with self.assertRaises(ValueError):
                bad()


class TestCamoufoxKeyboard(unittest.TestCase):
    """Tests for the keyboard layout and for planning human like typing. These
    never touch the browser."""

    def test_key_lookup(self) -> None:
        self.assertEqual(camoufox.key_info('a'), camoufox.KeyInfo('a', 'KeyA', 65))
        # a and A are the same physical key, one of them with shift held down
        self.assertEqual(camoufox.key_info('A'), camoufox.KeyInfo('A', 'KeyA', 65, shifted=True))
        self.assertEqual(camoufox.key_info('!'), camoufox.KeyInfo('!', 'Digit1', 49, shifted=True))
        self.assertEqual(camoufox.key_info(' ').code, 'Space')
        # The keys that are not characters are named, without regard to case,
        # and with the names people actually write for them
        self.assertEqual(camoufox.key_info('Enter'), camoufox.key_info('return'))
        self.assertEqual(camoufox.key_info('ESC').key, 'Escape')
        self.assertEqual(camoufox.key_info('ctrl'), camoufox.key_info('Control'))
        self.assertEqual(camoufox.key_info('cmd').key, 'Meta')
        self.assertEqual(camoufox.key_info('F7'), camoufox.KeyInfo('F7', 'F7', 118))
        # A modifier is reported as its left hand copy, the one a hand reaches for
        self.assertEqual(camoufox.key_info('shift'), camoufox.KeyInfo('Shift', 'ShiftLeft', 16, 1))
        # Tab and newlines are the keys that produce them, so text containing them can be typed
        self.assertEqual(camoufox.key_info('\n').key, 'Enter')
        self.assertEqual(camoufox.key_info('\t').key, 'Tab')
        for bad in ('', 'sideways', 'Hyper', 'ab'):
            with self.assertRaises(ValueError):
                camoufox.key_info(bad)

    def test_key_for_character(self) -> None:
        # An accented Latin character is typed as the key for the letter it
        # decomposes to, which is the one that produces it on a US
        # International layout, carrying the accented character as its value
        for ch, code in (('\u00e9', 'KeyE'), ('\u00fc', 'KeyU'), ('\u00f1', 'KeyN'), ('\u00e7', 'KeyC')):
            info = camoufox.key_for_character(ch)
            assert info is not None
            self.assertEqual((info.key, info.code, info.shifted), (ch, code, False))
        capital = camoufox.key_for_character('\u00c9')
        assert capital is not None
        self.assertEqual((capital.key, capital.code, capital.shifted), ('\u00c9', 'KeyE', True))
        self.assertEqual(camoufox.key_for_character('\u00e9'), camoufox.key_info('\u00e9'))
        # Anything else has no key that produces it and has to be inserted as text
        for ch in ('\u0444', '\u5b57', '\u00f8', '\u0142', '\u20ac', '\U0001f600'):
            self.assertIsNone(camoufox.key_for_character(ch), f'{ch} was claimed to be on the layout')

    def test_parse_chord(self) -> None:
        self.assertEqual(camoufox.parse_chord('a'), ((), 'a'))
        self.assertEqual(camoufox.parse_chord('Enter'), ((), 'Enter'))
        self.assertEqual(camoufox.parse_chord('ctrl+shift+a'), (('Control', 'Shift'), 'a'))
        self.assertEqual(camoufox.parse_chord('control+a'), (('Control',), 'a'))
        # The plus key is a key like any other, even at the end of a chord
        self.assertEqual(camoufox.parse_chord('+'), ((), '+'))
        self.assertEqual(camoufox.parse_chord('shift++'), (('Shift',), '+'))
        self.assertEqual(camoufox.parse_chord('ctrl+'), (('Control',), '+'))
        for bad in ('', 'a+b', 'ctrl+nosuchkey', 'ctrl++a'):
            with self.assertRaises(ValueError):
                camoufox.parse_chord(bad)

    def test_graphemes(self) -> None:
        # A combining mark belongs to the character before it rather than being
        # typed on its own, and the text is given back exactly as it came in
        for text in ('ab', 'e\u0301x', 'a\u0301\u0301b', '\U0001f44d\ufe0f', 'a\u200db', ''):
            self.assertEqual(''.join(camoufox.graphemes(text)), text)
        self.assertEqual(camoufox.graphemes('e\u0301x'), ['e\u0301', 'x'])
        self.assertEqual(camoufox.graphemes('ab'), ['a', 'b'])
        self.assertEqual(camoufox.graphemes('\U0001f44d\ufe0f!'), ['\U0001f44d\ufe0f', '!'])

    def test_typing_plan(self) -> None:
        self.assertEqual(camoufox.human_typing_plan(''), [])
        text = 'Hello, World! 42 times.'
        for seed in range(16):
            plan = camoufox.human_typing_plan(text, rng=random.Random(seed))
            # Every character of the text is typed, in order and only once
            self.assertEqual(''.join(k.text for k in plan), text)
            self.assertEqual(len(plan), len(text))
            for keystroke in plan:
                # A key must be one the browser can be told about
                self.assertTrue(keystroke.key, f'{keystroke.text!r} was not typed as a key press')
                camoufox.key_info(keystroke.key)
                self.assertTrue(math.isfinite(keystroke.delay) and math.isfinite(keystroke.dwell))
                self.assertGreaterEqual(keystroke.delay, camoufox.MIN_KEY_INTERVAL)
                self.assertLessEqual(keystroke.delay, camoufox.MAX_KEY_INTERVAL)
                # A key held down for longer than the gap to the next one would
                # still be down when that one is pressed
                self.assertGreater(keystroke.delay, keystroke.dwell)
                self.assertGreater(keystroke.dwell, 0)
            # Shift is needed for exactly the capitals and the shifted symbols
            self.assertEqual(''.join(k.key for k in plan if camoufox.key_info(k.key).shifted), 'HW!')
        # The same seed must give the same typing, so that failures are reproducible
        self.assertEqual(camoufox.human_typing_plan(text, rng=random.Random(3)), camoufox.human_typing_plan(text, rng=random.Random(3)))

    def test_typing_rhythm(self) -> None:
        text = 'the quick brown fox jumps over the lazy dog'
        for seed in range(8):
            fast = camoufox.human_typing_plan(text, wpm=200, rng=random.Random(seed))
            slow = camoufox.human_typing_plan(text, wpm=30, rng=random.Random(seed))
            self.assertLess(sum(k.delay for k in fast), sum(k.delay for k in slow))
            # The gaps between keystrokes must vary rather than being a metronome
            self.assertGreater(len({round(k.delay, 4) for k in slow}), len(text) // 2)
        # A speed in words per minute means what it says, once the pauses a
        # hand takes between words are averaged in
        median = 60.0 / (60.0 * camoufox.CHARS_PER_WORD)
        total = sum(sum(k.delay for k in camoufox.human_typing_plan(text, wpm=60, rng=random.Random(seed))) for seed in range(20))
        self.assertAlmostEqual(total / (20 * len(text)), median, delta=median * 0.5)
        for bad in (0, -5):
            with self.assertRaises(ValueError):
                camoufox.human_typing_plan(text, wpm=bad)
        with self.assertRaises(ValueError):
            camoufox.human_typing_plan(text, mistakes=1.5)

    def test_typing_text_that_is_not_on_the_layout(self) -> None:
        plan = camoufox.human_typing_plan('a\u0444\u00e9\u5b57', rng=random.Random(0))
        # An accented Latin character is a key press, anything the layout knows
        # nothing about is inserted as text instead
        self.assertEqual([(k.key, k.text) for k in plan], [('a', 'a'), ('', '\u0444'), ('\u00e9', '\u00e9'), ('', '\u5b57')])
        for text in ('\u043f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440', '\u4f60\u597d', '\u00e1'):
            plan = camoufox.human_typing_plan(text, rng=random.Random(0))
            self.assertEqual(''.join(k.text for k in plan), text)

    def test_typing_mistakes(self) -> None:
        text = 'the quick brown fox'
        seen_mistakes = 0
        for seed in range(16):
            plan = camoufox.human_typing_plan(text, mistakes=1.0, rng=random.Random(seed))
            # A mistake is a neighbouring key, so it is a key press like any other
            typed: list[str] = []
            for keystroke in plan:
                camoufox.key_info(keystroke.key)
                if keystroke.key == 'Backspace':
                    self.assertTrue(typed, 'backspace was pressed with nothing typed yet')
                    typed.pop()
                    seen_mistakes += 1
                else:
                    typed.append(keystroke.text)
            # Every mistake is taken back out again, so the text still ends up right
            self.assertEqual(''.join(typed), text)
        self.assertGreater(seen_mistakes, 16 * len(text) // 2, 'mistakes were asked for and not made')
        # and none are made unless they are asked for
        for seed in range(8):
            plan = camoufox.human_typing_plan(text, rng=random.Random(seed))
            self.assertFalse([k for k in plan if k.key == 'Backspace'])

    def test_hands_and_neighbours(self) -> None:
        self.assertEqual(camoufox.key_hand('f'), 'left')
        self.assertEqual(camoufox.key_hand('j'), 'right')
        self.assertEqual(camoufox.key_hand('F'), 'left')
        self.assertEqual(camoufox.key_hand('\u00e9'), 'left')  # the hand that types the letter it decomposes to
        self.assertEqual(camoufox.key_hand(' '), '')  # whichever thumb is idle
        self.assertEqual(camoufox.key_hand('\u5b57'), '')  # no key, so no hand
        self.assertEqual(camoufox.KEY_NEIGHBOURS['f'], ('d', 'g'))
        self.assertEqual(camoufox.KEY_NEIGHBOURS['F'], ('D', 'G'))
        self.assertEqual(camoufox.KEY_NEIGHBOURS['q'], ('w',))  # nothing to the left of it
        # The shifted twin of a key is on the same key
        for ch, twin in camoufox.SHIFTED_KEYS.items():
            self.assertEqual(camoufox.key_info(ch).code, camoufox.key_info(twin).code)
            self.assertTrue(camoufox.key_info(twin).shifted)
            self.assertFalse(camoufox.key_info(ch).shifted)


@unittest.skipIf(installed_camoufox() is None, 'the camoufox browser is not installed')
class TestCamoufoxBrowser(unittest.TestCase):
    """Tests that drive the real browser. Skipped unless it is already installed."""

    server: Server
    loop: asyncio.AbstractEventLoop
    browser: camoufox.Browser | None

    # These tests each drive a real browser, which is slow to start and heavy
    # to run, so the parallel test runner keeps them to a few of its worker
    # processes, where they can share one, rather than starting a browser in
    # every one of them. Measured on a sixteen core machine, one per worker
    # made the whole test suite take about a fifth longer than this does.
    max_parallel_workers = 6

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = Server()
        # Starting a browser and cleaning up after it costs well over a second,
        # which is longer than most of these tests take, so the ones that need
        # nothing particular of it share a single instance, started on first
        # use. It has to live on an event loop of its own, since the connection
        # to the browser is bound to the loop it was opened on and asyncio.run()
        # closes the loop it makes.
        cls.loop = asyncio.new_event_loop()
        cls.browser = None

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if (browser := cls.browser) is not None:
                cls.browser = None
                profile_dir = browser.profile_dir
                cls.loop.run_until_complete(browser.close())
                if os.path.exists(profile_dir):
                    raise AssertionError('the shared browser profile directory was not cleaned up')
        finally:
            cls.loop.close()
            cls.server.close()

    def run_browser(self, coro: Callable[[camoufox.Browser], Awaitable[object]], **kw: object) -> object:
        """Run coro against a browser of its own, for a test that needs one
        started with particular options."""

        async def main() -> object:
            async with camoufox.Browser(headless=True, **kw) as browser:  # type: ignore[arg-type]
                self.profile_dir = browser.profile_dir
                return await coro(browser)

        ans = asyncio.run(main())
        self.assertFalse(os.path.exists(self.profile_dir), 'the browser profile directory was not cleaned up')
        return ans

    def run_shared(self, coro: Callable[[camoufox.Browser], Awaitable[object]]) -> object:
        """Run coro against the browser shared with the other tests, in a tab
        of its own."""
        cls = type(self)

        async def main() -> object:
            # A browser whose process died takes every later test down with it,
            # so it is replaced rather than handed on
            if cls.browser is not None and cls.browser.closed:
                cls.browser = None
            if cls.browser is None:
                # Typing and cursor movement are deliberately slow, so the
                # shared browser does both faster than a hand would, to keep
                # the test suite quick. Their timing is scaled rather than
                # removed, so what a page sees is still the uneven rhythm of a
                # hand, see typing_interval() and human_trajectory().
                browser = camoufox.Browser(headless=True, typing_wpm=TEST_TYPING_WPM, humanize=TEST_MAX_MOVE_TIME)
                await browser.launch()
                cls.browser = browser
            browser = cls.browser
            # A tab of its own, with the ones any earlier test left behind
            # closed, so that the test sees the single blank page and empty
            # cookie jar that a freshly launched browser has
            page = await browser.new_page()
            for other in browser.open_pages:
                if other is not page:
                    await other.close()
            await browser.clear_cookies()
            return await coro(browser)

        return cls.loop.run_until_complete(main())

    def test_fingerprint_is_applied(self) -> None:
        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            config = browser.config
            self.assertEqual(await page.evaluate('navigator.userAgent'), config['navigator.userAgent'])
            self.assertEqual(await page.evaluate('navigator.platform'), config['navigator.platform'])
            self.assertEqual(await page.evaluate('screen.width'), config['screen.width'])
            self.assertEqual(await page.evaluate('window.outerWidth'), 1280)
            self.assertEqual(await page.evaluate('navigator.language'), 'en-US')
            # The whole point of camoufox: the automation must not be visible
            self.assertIs(await page.evaluate('navigator.webdriver'), False)
            for font in camoufox.MARKER_FONTS['windows']:
                self.assertIs(await page.evaluate(f'document.fonts.check("12px \'{font}\'")'), True, f'the font {font} is not available')

        self.run_browser(check, target_os='windows', locale='en-US', window=(1280, 800))

    def test_navigation_and_html(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            await page.open(base + 'index.html')
            self.assertEqual(await page.title(), 'Test Page')
            self.assertTrue(page.url.endswith('index.html'))
            self.assertIn('<h1 id="title">Hello</h1>', await page.html())
            await page.open(base + 'second.html')
            self.assertEqual(await page.title(), 'Second')
            self.assertIs(await page.go_back(), True)
            self.assertEqual(await page.title(), 'Test Page')
            self.assertIs(await page.go_forward(), True)
            self.assertEqual(await page.title(), 'Second')
            await page.reload()
            self.assertEqual(await page.title(), 'Second')
            await page.open(base + 'index.html', wait='domcontentloaded')
            self.assertEqual(await page.title(), 'Test Page')
            # Firefox refuses to connect to some low port numbers without
            # even trying, so use a high one that is merely closed
            with self.assertRaises(camoufox.Error):
                await page.open('http://127.0.0.1:47913/nothing-is-listening-here', timeout=30)

        self.run_shared(check)

    def test_waiting_for_elements(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            await page.open(base + 'index.html')
            # #late is added by a script 300ms after the page loads
            element = await page.wait_for_selector('#late', timeout=30)
            self.assertEqual(await element.text(), 'appeared')
            self.assertEqual(await (await page.wait_for_selector('#title')).text(), 'Hello')
            with self.assertRaises(camoufox.TimeoutExceeded):
                await page.wait_for_selector('#does-not-exist', timeout=1)
            await page.wait_for_load('domcontentloaded')

        self.run_shared(check)

    def test_dom_modification(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            await page.open(base + 'index.html')
            self.assertEqual(await page.remove('.para'), 2)
            self.assertEqual(await page.evaluate('document.querySelectorAll(".para").length'), 0)
            self.assertEqual(await page.remove('.para'), 0)
            self.assertEqual(await page.set_attribute('#title', 'data-x', 'yes'), 1)
            self.assertEqual(await page.evaluate('document.querySelector("#title").getAttribute("data-x")'), 'yes')
            self.assertEqual(await page.delete_attribute('#pic', 'alt'), 1)
            self.assertIs(await page.evaluate('document.querySelector("#pic").hasAttribute("alt")'), False)
            self.assertEqual(await page.append_child('#container', 'span', {'class': 'added'}, 'child text'), 1)
            self.assertEqual(await page.evaluate('document.querySelector("#container .added").textContent'), 'child text')
            self.assertEqual(await page.insert_html('#container', '<b class="bold">bee</b>'), 1)
            self.assertEqual(await page.evaluate('document.querySelector("#container .bold").textContent'), 'bee')
            self.assertEqual(await page.set_text('#title', 'Changed'), 1)
            with self.assertRaises(ValueError):
                await page.insert_html('#container', 'x', 'nowhere')
            html = await page.html()
            self.assertIn('Changed', html)
            self.assertNotIn('class="para"', html)
            self.assertIn('<span class="added">child text</span>', html)

        self.run_shared(check)

    def test_element_handles(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            await page.open(base + 'index.html')
            self.assertIsNone(await page.find('#does-not-exist'))
            image = await page.find('#pic')
            assert image is not None
            self.assertEqual(await image.attribute('id'), 'pic')
            self.assertEqual((await image.attributes())['alt'], 'a picture')
            await image.set_attribute('data-y', '7')
            self.assertEqual(await image.attribute('data-y'), '7')
            await image.delete_attribute('data-y')
            self.assertIsNone(await image.attribute('data-y'))
            self.assertTrue((await image.html()).startswith('<img'))
            container = await page.find('#container')
            assert container is not None
            self.assertEqual(await (await container.find('.para')).text(), 'one')
            await container.append_child('i', {'id': 'ital'}, 'italic')
            self.assertEqual(await (await page.find('#ital')).text(), 'italic')
            await container.insert_html('<u id="under">u</u>')
            self.assertIsNotNone(await page.find('#under'))
            self.assertEqual(len(await page.find_all('.para')), 2)
            await image.remove()
            self.assertIsNone(await page.find('#pic'))
            with self.assertRaises(camoufox.Error):
                await image.attribute('id')  # the handle was disposed by remove()

        self.run_shared(check)

    def test_resources(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            await page.open(base + 'index.html')
            self.assertEqual(page.resource_urls(r'\.svg$'), (base + 'pic.svg',))
            resource = await page.get_resource(base + 'pic.svg')
            self.assertEqual(resource.data.decode('utf-8'), TEST_SVG)
            self.assertIn('svg', resource.content_type)
            # A URL the page never requested has to be fetched from the page
            resource = await page.get_resource(base + 'second.html')
            self.assertIn('Second', resource.data.decode('utf-8'))
            with self.assertRaises(camoufox.Error):
                await page.get_resource(base + 'does-not-exist.png')
            self.assertTrue((await page.screenshot()).startswith(b'\x89PNG\r\n\x1a\n'))

        self.run_shared(check)

    def test_tabs(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            first = browser.page
            await first.open(base + 'second.html')
            second = await browser.new_page(base + 'index.html')
            self.assertEqual(len(browser.open_pages), 2)
            self.assertEqual(await second.title(), 'Test Page')
            # The tabs must be independent of each other
            self.assertEqual(await first.title(), 'Second')
            await second.close()
            self.assertEqual(len(browser.open_pages), 1)
            with self.assertRaises(camoufox.BrowserClosedError):
                await second.title()

        self.run_shared(check)

    def test_javascript_errors(self) -> None:
        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            with self.assertRaises(camoufox.JavaScriptError):
                await page.evaluate('throw new Error("boom")')
            with self.assertRaises(camoufox.JavaScriptError):
                await page.call('() => { undefined.x; }')
            # The page must still be usable afterwards
            self.assertEqual(await page.evaluate('1 + 1'), 2)
            self.assertEqual(await page.call('(a, b) => a + b', 2, 3), 5)

        self.run_shared(check)

    def test_cookies(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            await browser.page.open(base + 'index.html')
            await browser.set_cookies([{'name': 'cal', 'value': 'ibre', 'url': base}])
            self.assertEqual([c['value'] for c in await browser.cookies() if c['name'] == 'cal'], ['ibre'])
            self.assertIn('cal=ibre', await browser.page.evaluate('document.cookie'))
            await browser.clear_cookies()
            self.assertEqual(await browser.cookies(), [])

        self.run_shared(check)

    def test_mouse_clicking(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            await page.open(base + 'click.html')
            await page.call(RECORDER_JS)
            rect = await page.call(RECT_JS, 'btn')
            # Start from the far corner so that the path to the button is a long one
            width, height = await page.evaluate('[window.innerWidth, window.innerHeight]')
            await page.mouse.move(width - 20, height - 20, human=False)
            await page.evaluate('window.__reset()')
            await page.click('#btn')
            moves = await page.evaluate('window.__moves')
            events = await page.evaluate('window.__events')
            # The cursor must travel along a path rather than teleporting
            self.assertGreater(len(moves), 5)
            self.assertGreater(len({(round(x), round(y)) for x, y in moves}), 5)
            # and that path must bow away from the straight line between the ends
            (x0, y0), (x1, y1) = moves[0], moves[-1]
            length = math.hypot(x1 - x0, y1 - y0)
            deviation = max(abs(((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)) / length) for x, y in moves)
            self.assertGreater(deviation, 1, 'the cursor moved in a straight line')
            # It must end up on the button, and the page must agree it was clicked
            self.assertEqual([e['type'] for e in events], ['mousedown', 'mouseup', 'click'])
            self.assertEqual({e['target'] for e in events}, {'btn'})
            self.assertAlmostEqual(page.mouse.position[0], events[-1]['x'], delta=1)
            self.assertAlmostEqual(page.mouse.position[1], events[-1]['y'], delta=1)
            self.assertTrue(rect['left'] <= events[-1]['x'] <= rect['right'])
            self.assertTrue(rect['top'] <= events[-1]['y'] <= rect['bottom'])
            # The button must be pressed for a human like length of time
            self.assertGreater(events[1]['at'] - events[0]['at'], 30)
            self.assertEqual((events[0]['button'], events[0]['buttons']), (0, 1))
            self.assertEqual((events[1]['button'], events[1]['buttons']), (0, 0))
            self.assertEqual(events[0]['detail'], 1)

            # Buttons, modifiers and repeated clicks
            await page.evaluate('window.__reset()')
            await page.click('#btn', button='right')
            events = await page.evaluate('window.__events')
            self.assertEqual([e['type'] for e in events], ['mousedown', 'contextmenu', 'mouseup'])
            self.assertEqual(events[0]['button'], 2)
            await page.evaluate('window.__reset()')
            await page.click('#btn', click_count=2, modifiers=('shift', 'alt'))
            events = await page.evaluate('window.__events')
            self.assertEqual([e['type'] for e in events], ['mousedown', 'mouseup', 'click', 'mousedown', 'mouseup', 'click', 'dblclick'])
            self.assertEqual([e['detail'] for e in events], [1, 1, 1, 2, 2, 2, 2])
            self.assertTrue(all(e['shift'] and e['alt'] and not e['ctrl'] for e in events))

            # An element below the fold is scrolled to before being clicked
            await page.evaluate('window.__reset()')
            self.assertEqual(await page.evaluate('window.scrollY'), 0)
            await page.click('#far')
            self.assertGreater(await page.evaluate('window.scrollY'), 100)
            events = await page.evaluate('window.__events')
            self.assertEqual([e['target'] for e in events], ['far', 'far', 'far'])

            # Moving without humanizing goes straight there
            await page.evaluate('window.__reset()')
            await page.mouse.move(3, 4, human=False)
            self.assertEqual([[round(x), round(y)] for x, y in await page.evaluate('window.__moves')], [[3, 4]])
            self.assertEqual(page.mouse.position, (3, 4))

            # Hovering moves onto the element without pressing anything
            await page.evaluate('window.__reset()')
            await page.hover('#btn')
            self.assertEqual(await page.evaluate('window.__events'), [])
            self.assertEqual(await page.evaluate('document.querySelectorAll("#btn:hover").length'), 1)

        self.run_shared(check)

    def test_mouse_errors(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            await page.open(base + 'click.html')
            await page.call(RECORDER_JS)
            hidden = await page.find('#hidden')
            assert hidden is not None
            # An element with no visible area cannot be clicked
            with self.assertRaises(camoufox.Error):
                await hidden.click()
            with self.assertRaises(camoufox.TimeoutExceeded):
                await page.click('#hidden', timeout=1)
            with self.assertRaises(ValueError):
                await page.click('#btn', button='sideways')
            with self.assertRaises(ValueError):
                await page.click('#btn', modifiers=('hyper',))
            # A button left pressed is remembered and reported to the page
            await page.mouse.move(50, 50)
            await page.mouse.down()
            self.assertEqual(page.mouse.buttons, 1)
            await page.mouse.move(80, 70)
            # Within a pixel, the last step of a path is skipped when it lands
            # on the pixel the cursor is already on
            last = await page.evaluate('window.__moves.at(-1)')
            self.assertAlmostEqual(last[0], 80, delta=1)
            self.assertAlmostEqual(last[1], 70, delta=1)
            await page.mouse.up()
            self.assertEqual(page.mouse.buttons, 0)

            # Every position on a path stays clear of the edges of the
            # viewport, even when the path bows or overshoots past one on its
            # way to a corner. A movement onto an edge is never acknowledged
            # and takes every later one down with it, so this hangs the page
            # rather than merely putting the cursor in the wrong place.
            width, height = await page.viewport()
            await page.evaluate('window.__reset()')
            await page.mouse.move(width - 1, height - 1)
            moves = await page.evaluate('window.__moves')
            self.assertTrue(moves)
            margin = camoufox.VIEWPORT_MARGIN
            for x, y in moves:
                inside = margin <= x < width - margin and margin <= y < height - margin
                self.assertTrue(inside, f'the cursor reached ({x}, {y}), too close to the edge of the {width}x{height} viewport')
            self.assertEqual(page.mouse.position, camoufox.clamp_to_viewport(width - 1, height - 1, width, height))

        self.run_shared(check)

    def test_input_that_is_not_acknowledged(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            await page.open(base + 'click.html')
            await page.mouse.move(60, 60)
            # An event the page never sees is never answered, so waiting for
            # one is given up on quickly and the page written off, since
            # nothing sent to it after that is dispatched either
            original = camoufox.INPUT_TIMEOUT
            camoufox.INPUT_TIMEOUT = 0.000001
            try:
                with self.assertRaises(camoufox.InputWedged) as ctx:
                    await page.mouse.move(200, 200, human=False)
            finally:
                camoufox.INPUT_TIMEOUT = original
            # The failure says which half of the browser stopped answering
            self.assertIn('still runs JavaScript', str(ctx.exception))
            self.assertTrue(page.input_wedged)
            # Further input fails at once instead of waiting for another reply
            # that is not coming, without sending the browser anything at all
            sent = page.connection.message_id
            started = time.monotonic()
            with self.assertRaises(camoufox.InputWedged):
                await page.mouse.click(10, 10)
            self.assertEqual(page.connection.message_id, sent)
            self.assertLess(time.monotonic() - started, camoufox.INPUT_TIMEOUT)
            for typing in (page.keyboard.press('a'), page.keyboard.type('abc'), page.keyboard.insert_text('abc')):
                with self.assertRaises(camoufox.InputWedged):
                    await typing
            self.assertEqual(page.connection.message_id, sent)
            # while the page is still usable for everything else
            self.assertEqual(await page.evaluate('1 + 1'), 2)

        self.run_shared(check)

    def test_clicking_with_humanize(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            # The browser is never asked to generate cursor paths itself, the
            # option only says how long one of ours may take
            self.assertEqual(browser.max_move_time, TEST_MAX_MOVE_TIME)
            self.assertNotIn('humanize', browser.config)
            await page.open(base + 'click.html')
            await page.call(RECORDER_JS)
            # Every position along a path is a separate event the browser has
            # to acknowledge, and on a loaded machine those round trips, not
            # the budget, are what the wall clock is mostly made of, so measure
            # one here rather than assuming it is quick
            probe = time.monotonic()
            for i in range(6):
                await page.mouse.move(20 + 10 * i, 20, human=False)
            per_event = (time.monotonic() - probe) / 6
            # Back into the corner the cursor started in, so that the click
            # below is the same journey it would have been without measuring
            await page.mouse.move(1, 1, human=False)
            await page.evaluate('window.__reset()')
            start = time.monotonic()
            await page.click('#btn')
            self.assertGreater(len(await page.evaluate('window.__moves')), 5)
            self.assertEqual([e['type'] for e in await page.evaluate('window.__events')], ['mousedown', 'mouseup', 'click'])
            # The movement kept to the budget, with the click itself, the round
            # trips it took and the pauses of a human hand on top of it
            round_trips = (camoufox.MAX_MOVE_STEPS + 8) * per_event
            self.assertLess(time.monotonic() - start, TEST_MAX_MOVE_TIME + round_trips + 4)

        self.run_shared(check)

    def test_typing(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            await page.open(base + 'type.html')
            await page.call(KEY_RECORDER_JS)

            # Filling a field replaces what was in it, by typing rather than by
            # assigning to it, so the page sees every keystroke
            await page.fill('#text', 'Hello World')
            self.assertEqual(await page.evaluate('document.getElementById("text").value'), 'Hello World')
            downs = [e for e in await page.evaluate('window.__keys') if e['type'] == 'keydown']
            typed = [e for e in downs if len(e['key']) == 1 and not e['ctrl']]  # the a of the select all chord is not typing
            self.assertEqual(''.join(e['key'] for e in typed), 'Hello World')
            self.assertEqual([e['code'] for e in typed[:5]], ['KeyH', 'KeyE', 'KeyL', 'KeyL', 'KeyO'])
            self.assertEqual([e['keyCode'] for e in typed[:2]], [72, 69])
            # Shift is held down for the capitals and for nothing else
            self.assertEqual(''.join(e['key'] for e in typed if e['shift']), 'HW')
            # and it arrives as a key of its own, the way a keyboard sends it
            self.assertIn('Shift', [e['key'] for e in downs])
            # The page sees the text arrive as well as the keys
            self.assertEqual(''.join(e['data'] or '' for e in await page.evaluate('window.__inputs')), 'Hello World')
            # The keystrokes must have the uneven rhythm of a hand, not of a clock
            gaps = [b['at'] - a['at'] for a, b in itertools.pairwise(typed)]
            self.assertTrue(all(gap > 0 for gap in gaps))
            self.assertGreater(max(gaps) - min(gaps), 10, 'the typing was perfectly regular')

            # Typing appends at the caret instead of replacing
            await page.type('#text', '!')
            self.assertEqual(await page.evaluate('document.getElementById("text").value'), 'Hello World!')

            # A chord, and a key pressed more than once
            await page.evaluate('window.__reset()')
            await page.press('#text', 'ctrl+a')
            pressed = [e for e in await page.evaluate('window.__keys') if e['type'] == 'keydown']
            self.assertEqual([e['key'] for e in pressed], ['Control', 'a'])
            self.assertTrue(pressed[-1]['ctrl'])
            self.assertEqual(page.keyboard.modifiers, (), 'a modifier was left held down')
            await page.press('#text', 'Backspace')
            self.assertEqual(await page.evaluate('document.getElementById("text").value'), '')
            await page.type('#text', 'abcd')
            await page.press('#text', 'Backspace', count=2)
            self.assertEqual(await page.evaluate('document.getElementById("text").value'), 'ab')
            # shift makes a key produce its shifted character
            await page.press('#text', 'shift+c')
            self.assertEqual(await page.evaluate('document.getElementById("text").value'), 'abC')

            # Newlines are typed as the key that produces them
            await page.fill('#area', 'one\ntwo')
            self.assertEqual(await page.evaluate('document.getElementById("area").value'), 'one\ntwo')
            # and enter in a form submits it
            await page.evaluate('window.__reset()')
            await page.press('#text', 'Enter')
            self.assertIs(await page.evaluate('window.__submitted'), True)

            # An element can be typed into without the mouse, and something
            # that is not a form field can be typed into too
            await page.fill('#rich', 'edited', click=False)
            self.assertEqual(await page.evaluate('document.getElementById("rich").textContent'), 'edited')

            # Mistakes are corrected as they are made, so the text still ends
            # up right. Noticing a mistake and going back over it are pauses of
            # a fixed length rather than ones that scale with the typing speed,
            # so they are shortened here: what this checks is that the
            # correction happens, not how long a hand takes to make it.
            with patch.object(camoufox, 'MISTAKE_NOTICE', (0.01, 0.02)), patch.object(camoufox, 'MISTAKE_REPAIR', (0.01, 0.02)):
                await page.fill('#text', 'corrected', mistakes=1.0)
            self.assertEqual(await page.evaluate('document.getElementById("text").value'), 'corrected')

        self.run_shared(check)

    def test_typing_text_that_is_not_on_the_keyboard(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            await page.open(base + 'type.html')
            await page.call(KEY_RECORDER_JS)
            # An accented Latin character is a real key press, with the key of
            # the letter it decomposes to, which is how a US International
            # layout produces it. A character from another script has no key at
            # all, so it is inserted as text instead and the page sees no key
            # events for it, only the text arriving.
            text = 'café привет'
            await page.fill('#text', text)
            self.assertEqual(await page.evaluate('document.getElementById("text").value'), text)
            downs = [e for e in await page.evaluate('window.__keys') if e['type'] == 'keydown']
            accented = [e for e in downs if e['key'] == 'é']
            self.assertEqual(len(accented), 1)
            self.assertEqual((accented[0]['code'], accented[0]['keyCode']), ('KeyE', 69))
            self.assertFalse([e for e in downs if len(e['key']) == 1 and e['key'] in 'привет'])
            self.assertIn('п', ''.join(e['data'] or '' for e in await page.evaluate('window.__inputs')))

            # Text can only be inserted into something that can hold it, and
            # inserting it into anything else silently does nothing, so it fails
            await page.evaluate('document.activeElement.blur()')
            with self.assertRaises(camoufox.Error):
                await page.keyboard.insert_text('你好')
            # Keystrokes are thrown away by a page with nothing editable
            # focused too, so typing into one is reported rather than lost
            with self.assertRaises(camoufox.Error):
                await page.keyboard.type('abc')
            readonly = await page.find('#ro')
            assert readonly is not None
            await readonly.focus()
            with self.assertRaises(camoufox.Error):
                await page.keyboard.insert_text('你好')
            with self.assertRaises(camoufox.Error):
                await page.type('#ro', '你好', click=False)
            # while a field that can hold it takes it without any key events
            await page.evaluate('window.__reset()')
            await page.fill('#area', '')
            await page.keyboard.insert_text('你好')
            self.assertEqual(await page.evaluate('document.getElementById("area").value'), '你好')

        self.run_shared(check)

    def test_typing_speed(self) -> None:
        base = self.server.base

        async def check(browser: camoufox.Browser) -> None:
            page = browser.page
            self.assertEqual(browser.typing_wpm, TEST_TYPING_WPM)
            await page.open(base + 'type.html')
            await page.call(KEY_RECORDER_JS)
            # Every keystroke is two events the browser has to acknowledge, and
            # on a loaded machine those round trips, not the requested speed,
            # are what the wall clock is mostly made of, so measure one here
            # rather than assuming it is quick
            text = 'the quick brown fox'
            probe = time.monotonic()
            await page.fill('#text', text, delay=0)
            per_key = (time.monotonic() - probe) / len(text)
            self.assertEqual(await page.evaluate('document.getElementById("text").value'), text)
            # A fixed delay means no rhythm at all, which is quicker than a hand
            started = time.monotonic()
            await page.fill('#text', text, wpm=TEST_TYPING_WPM)
            self.assertEqual(await page.evaluate('document.getElementById("text").value'), text)
            expected = 60.0 * len(text) / (TEST_TYPING_WPM * camoufox.CHARS_PER_WORD)
            self.assertLess(time.monotonic() - started, expected + len(text) * per_key + 8)

        self.run_shared(check)


def find_tests() -> unittest.TestSuite:
    ans = unittest.TestSuite()
    for cls in (TestCamoufoxConfig, TestCamoufoxTransport, TestCamoufoxFonts, TestCamoufoxMouse, TestCamoufoxKeyboard, TestCamoufoxBrowser):
        ans.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    return ans


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(find_tests())
