#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
An asyncio based API for driving the Camoufox browser.

Camoufox is a fork of Firefox that hides the fact that it is being automated and
allows the fingerprint it presents to web pages (the values reported by
``navigator``, ``screen``, the list of installed fonts, WebGL, etc.) to be
spoofed. The browser binary is downloaded on demand by
:mod:`calibre.web.automate.download_deps`.

The browser is driven using the Juggler protocol, which is the protocol
Playwright uses to drive Firefox. Messages are NUL delimited JSON objects
exchanged over a pair of pipes connected to file descriptors 3 and 4 of the
browser process. Implementing the protocol directly means the only dependency
outside the standard library is browserforge, which is used solely to generate
fingerprints.

Typical usage::

    async with Browser() as browser:
        page = browser.page
        await page.open('https://example.com')
        await page.click('a.more')
        await page.fill('input[name=q]', 'search terms')
        await page.press('input[name=q]', 'Enter')
        await page.remove('script, style')
        html = await page.html()
        img = await page.get_resource('https://example.com/logo.png')
"""

import asyncio
import base64
import json
import math
import os
import queue
import random
import re
import shutil
import struct
import sys
import tempfile
import threading
import time
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import lru_cache
from typing import Any, NamedTuple

from calibre.constants import cache_dir, ismacos, iswindows
from calibre.utils.filenames import make_long_path_useable
from calibre.utils.safe_atexit import remove_folder_atexit
from calibre.web.automate.download_deps import browserforge_data, camoufox_installer, camoufox_resource_dir, debug

DEFAULT_TIMEOUT = 60.0  # seconds, for individual protocol commands
# The browser answers an input event only once the page has actually seen it,
# see Mouse.dispatch, and an event the page never sees is never answered at
# all, so the wait for one is kept short. An event that has not been
# acknowledged within a few seconds never will be.
INPUT_TIMEOUT = 5.0  # seconds, for a single input event
INPUT_DIAGNOSTIC_TIMEOUT = 5.0  # seconds, for each question asked of a browser that stopped accepting input
LAUNCH_TIMEOUT = 180.0  # seconds, the first launch has to create a fresh profile
CLOSE_TIMEOUT = 20.0  # seconds to wait for the browser to exit before killing it
PROFILE_REMOVE_TIMEOUT = 30.0  # seconds to keep trying to delete the profile directory, see remove_profile_dir()
MAX_TRACKED_REQUESTS = 2048  # per page, bounds the memory used to map URLs to network requests

# The OS names used by camoufox in its config, its bundled data directories and
# its user agent strings, respectively
OS_NAMES = ('windows', 'macos', 'linux')
OS_DIRS = {'windows': 'windows', 'macos': 'macos', 'linux': 'linux'}
OS_ABBREV = {'windows': 'win', 'macos': 'mac', 'linux': 'lin'}


def current_os() -> str:
    return 'windows' if iswindows else ('macos' if ismacos else 'linux')


class Error(Exception):
    """Base class for all errors raised by this module."""


class ProtocolError(Error):
    """The browser reported an error in response to a command."""

    def __init__(self, method: str, message: str, data: str = '') -> None:
        super().__init__(f'{method} failed: {message}')
        self.method, self.message, self.data = method, message, data


class BrowserClosedError(Error):
    """The browser process exited or the connection to it was lost."""


class InputWedged(Error):
    """The browser stopped acknowledging input events.

    Every mouse, wheel and key event the browser is sent is dispatched from a
    single queue shared by the whole browser process, and the browser works
    through it one event at a time, answering each only once the page has seen
    it. An event that never reaches the page is therefore never answered, and
    worse, nothing behind it in the queue is ever dispatched either, so the page
    can no longer be given input of any kind. Nothing here can undo that, the page has
    to be abandoned, so once it happens further input events fail immediately
    rather than waiting for a reply that will not come.
    """


class JavaScriptError(Error):
    """Evaluating JavaScript in the page raised an exception."""


class TimeoutExceeded(Error):
    """An operation did not complete within its allotted time."""


# Fingerprint generation {{{

# Maps the fields of a browserforge fingerprint onto camoufox config properties.
# This is a transcription of browserforge.yml from the camoufox package. Fields
# that are absent are deliberately not spoofed, see that file for the reasoning,
# in particular note that videoCard is omitted because browserforge generates
# Chrome flavored values such as 'ANGLE (AMD, ... Direct3D11 ...)' which would
# be a glaring inconsistency in a Firefox based browser.
BROWSERFORGE_MAP: dict[str, Any] = {
    'navigator': {
        'userAgent': 'navigator.userAgent',
        'doNotTrack': 'navigator.doNotTrack',
        'appCodeName': 'navigator.appCodeName',
        'appName': 'navigator.appName',
        'appVersion': 'navigator.appVersion',
        'oscpu': 'navigator.oscpu',
        'platform': 'navigator.platform',
        'hardwareConcurrency': 'navigator.hardwareConcurrency',
        'product': 'navigator.product',
        'maxTouchPoints': 'navigator.maxTouchPoints',
        'extraProperties': {
            'globalPrivacyControl': 'navigator.globalPrivacyControl',
        },
    },
    'screen': {
        'availLeft': 'screen.availLeft',
        'availTop': 'screen.availTop',
        'availWidth': 'screen.availWidth',
        'availHeight': 'screen.availHeight',
        'height': 'screen.height',
        'width': 'screen.width',
        'colorDepth': 'screen.colorDepth',
        'pixelDepth': 'screen.pixelDepth',
        'pageXOffset': 'screen.pageXOffset',
        'pageYOffset': 'screen.pageYOffset',
        'outerHeight': 'window.outerHeight',
        'outerWidth': 'window.outerWidth',
        'innerHeight': 'window.innerHeight',
        'innerWidth': 'window.innerWidth',
        'screenX': 'window.screenX',
        'screenY': 'window.screenY',
    },
    'headers': {
        'Accept-Encoding': 'headers.Accept-Encoding',
    },
    'battery': {
        'charging': 'battery:charging',
        'chargingTime': 'battery:chargingTime',
        'dischargingTime': 'battery:dischargingTime',
    },
}

# Fonts that must always be present in the generated font subset, because a real
# installation of the OS in question always has them
ESSENTIAL_FONTS = {
    'macos': (
        'Arial',
        'Helvetica',
        'Times New Roman',
        'Courier New',
        'Verdana',
        'Georgia',
        'Trebuchet MS',
        'Tahoma',
        'Helvetica Neue',
        'Lucida Grande',
        'Menlo',
        'Monaco',
        'Geneva',
        'PingFang HK',
        'PingFang SC',
        'PingFang TC',
    ),
    'windows': (
        'Arial',
        'Times New Roman',
        'Courier New',
        'Verdana',
        'Georgia',
        'Trebuchet MS',
        'Tahoma',
        'Segoe UI',
        'Calibri',
        'Cambria Math',
        'Nirmala UI',
        'Consolas',
    ),
    'linux': (
        'Arimo',
        'Cousine',
        'Tinos',
        'Twemoji Mozilla',
        'Noto Sans Devanagari',
        'Noto Sans JP',
        'Noto Sans KR',
        'Noto Sans SC',
        'Noto Sans TC',
    ),
}

# Fonts used by fingerprinting scripts to detect the OS. They must be present or
# the reported OS will not match the rest of the fingerprint.
MARKER_FONTS = {
    'macos': ('Helvetica Neue', 'PingFang HK', 'PingFang SC', 'PingFang TC'),
    'windows': ('Segoe UI', 'Tahoma', 'Cambria Math', 'Nirmala UI'),
    'linux': ('Arimo', 'Cousine', 'Tinos', 'Twemoji Mozilla'),
}

# Firefox preferences needed to make WebGL work in headless mode. Without them
# there is no WebGL context at all, which is a strong signal that the browser is
# not a normal desktop browser.
BASE_USER_PREFS: dict[str, Any] = {
    'webgl.force-enabled': True,
    'webgl.enable-webgl2': True,
    # Camoufox cannot open new windows, so make sure nothing tries to
    'browser.link.open_newwindow': 3,
    'browser.link.open_newwindow.restriction': 0,
    # Avoid pointless network traffic and startup work
    'browser.shell.checkDefaultBrowser': False,
    'browser.startup.homepage_override.mstone': 'ignore',
    'datareporting.policy.dataSubmissionEnabled': False,
    'datareporting.healthreport.uploadEnabled': False,
    'toolkit.telemetry.enabled': False,
    'app.update.auto': False,
    'extensions.update.enabled': False,
}

# Preferences that make the browser keep previously loaded pages and requests
# around, at the cost of using more memory
CACHE_USER_PREFS: dict[str, Any] = {
    'browser.sessionhistory.max_entries': 10,
    'browser.sessionhistory.max_total_viewers': -1,
    'browser.cache.memory.enable': True,
    'browser.cache.disk_cache_ssl': True,
    'browser.cache.disk.smart_size.enabled': True,
}


def check_valid_os(target_os: str) -> str:
    if target_os not in OS_NAMES:
        raise ValueError(f'{target_os} is not a valid operating system, must be one of: {", ".join(OS_NAMES)}')
    return target_os


def cast_to_properties(dest: dict[str, Any], mapping: Mapping[str, Any], src: Mapping[str, Any], ff_version: str) -> None:
    """Copy the values in src into dest, renaming them as specified by mapping."""
    for key, value in src.items():
        if not value:  # browserforge uses falsey values to mean "not set"
            continue
        target = mapping.get(key)
        if not target:
            continue
        if isinstance(target, dict):
            if isinstance(value, dict):
                cast_to_properties(dest, target, value, ff_version)
            continue
        if isinstance(value, int) and not isinstance(value, bool) and target.startswith('screen.') and value < 0:
            value = 0
        if isinstance(value, str):
            # browserforge fingerprints tend to name an older Firefox than the
            # one we are actually running, replace the major version
            value = re.sub(r'(?<!\d)(1[0-9]{2})(\.0)(?!\d)', rf'{ff_version}\2', value)
        dest[target] = value


def set_screen_y(config: dict[str, Any], screen: Mapping[str, Any]) -> None:
    """Derive window.screenY, which browserforge does not generate, from screenX."""
    if 'window.screenY' in config:
        return
    screen_x = screen.get('screenX') or 0
    if not screen_x:
        config['window.screenX'] = config['window.screenY'] = 0
        return
    if -50 <= screen_x <= 50:  # the window is maximized, y matches x
        config['window.screenY'] = screen_x
        return
    span = (screen.get('availHeight') or 0) - (screen.get('outerHeight') or 0)
    if span == 0:
        config['window.screenY'] = 0
    elif span > 0:
        config['window.screenY'] = random.randrange(0, span)
    else:
        config['window.screenY'] = random.randrange(span, 0)


def clamp_window_dimensions(config: dict[str, Any]) -> None:
    """Ensure the spoofed window is not larger than the spoofed screen."""
    for window_key, screen_key in (('window.outerWidth', 'screen.availWidth'), ('window.outerHeight', 'screen.availHeight')):
        window, screen = config.get(window_key), config.get(screen_key)
        if isinstance(window, int) and isinstance(screen, int) and screen and window > screen:
            config[window_key] = screen
    for inner_key, outer_key in (('window.innerWidth', 'window.outerWidth'), ('window.innerHeight', 'window.outerHeight')):
        inner, outer = config.get(inner_key), config.get(outer_key)
        if isinstance(inner, int) and isinstance(outer, int) and inner > outer:
            config[inner_key] = outer


def fix_navigator_arch(config: dict[str, Any], target_os: str) -> None:
    """Make navigator.platform and navigator.oscpu consistent with the target OS."""
    ua = config.get('navigator.userAgent') or ''
    if target_os == 'windows':
        platform, oscpu = 'Win32', 'Windows NT 10.0; Win64; x64'
    elif target_os == 'macos':
        platform, oscpu = 'MacIntel', 'Intel Mac OS X 10.15'
    else:
        platform = 'Linux x86_64'
        oscpu = 'Linux aarch64' if 'aarch64' in ua else 'Linux x86_64'
    config.setdefault('navigator.platform', platform)
    config.setdefault('navigator.oscpu', oscpu)


def set_media_devices_defaults(config: dict[str, Any]) -> None:
    """A machine with no microphone and no camera at all is an unusual, and so
    identifying, thing to be. Report one of each."""
    config.setdefault('mediaDevices:enabled', True)
    config.setdefault('mediaDevices:micros', 1)
    config.setdefault('mediaDevices:webcams', 1)
    config.setdefault('mediaDevices:speakers', 0)


# Fonts {{{


def sfnt_name_table(raw: bytes, offset: int = 0) -> bytes | None:
    """Return the raw 'name' table of the SFNT font whose table directory starts at offset."""
    if len(raw) < offset + 12:
        return None
    num_tables = struct.unpack_from(b'>H', raw, offset + 4)[0]
    for i in range(num_tables):
        pos = offset + 12 + 16 * i
        if len(raw) < pos + 16:
            break
        tag, _, table_offset, table_size = struct.unpack_from(b'>4sLLL', raw, pos)
        if tag == b'name':
            return raw[table_offset : table_offset + table_size]
    return None


def font_families_in(path: str) -> set[str]:
    """The font families defined by the font file at path, which can be a
    TrueType/OpenType font or a TrueType collection."""
    from calibre.utils.fonts.utils import get_font_names

    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:4] == b'ttcf':  # a collection, with one table directory per font
        num_fonts = struct.unpack_from(b'>L', raw, 8)[0]
        offsets: Sequence[int] = struct.unpack_from(f'>{num_fonts}L'.encode(), raw, 12)
    else:
        offsets = (0,)
    ans = set()
    for offset in offsets:
        table = sfnt_name_table(raw, offset)
        if table is None:
            continue
        try:
            family = get_font_names(table, raw_is_table=True)[0]
        except Exception:
            continue
        if family:
            ans.add(family)
    return ans


def read_font_families(resource_dir: str, target_os: str) -> tuple[str, ...]:
    """The font families camoufox bundles for target_os.

    The list is read from the font files themselves rather than from a hard
    coded table so that it stays in sync with whatever version of the browser
    happens to be installed, and so that we never claim to have a font the
    browser cannot actually render.
    """
    ans: set[str] = set()
    base = os.path.join(resource_dir, 'fonts')
    # Fonts directly in the fonts dir, such as Twemoji, are shared by every OS
    for d in (base, os.path.join(base, OS_DIRS[target_os])):
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            path = os.path.join(d, name)
            if not os.path.isfile(path):
                continue
            try:
                ans |= font_families_in(path)
            except Exception:
                continue  # not a font file we can read, ignore it
    return tuple(sorted(ans))


@lru_cache(maxsize=4)
def font_families(resource_dir: str, version: str, target_os: str) -> tuple[str, ...]:
    """Like read_font_families() but cached on disk, since parsing a few hundred
    font files takes a noticeable fraction of a second."""
    cache_path = os.path.join(cache_dir(), f'camoufox-fonts-{version}.json')
    try:
        with open(cache_path, 'rb') as f:
            cached = json.loads(f.read())
        if isinstance(cached, dict) and isinstance(cached.get(target_os), list):
            return tuple(cached[target_os])
    except Exception:
        cached = {}
    if not isinstance(cached, dict):
        cached = {}
    ans = read_font_families(resource_dir, target_os)
    cached[target_os] = list(ans)
    try:
        with open(cache_path, 'wb') as f:
            f.write(json.dumps(cached).encode('utf-8'))
    except OSError:
        pass  # an unwritable cache dir is not fatal, we just pay to parse again
    return ans


def random_font_subset(families: Sequence[str], target_os: str) -> list[str]:
    """A random subset of families, the way camoufox generates one.

    A real machine has a more or less arbitrary set of fonts installed, so
    reporting the same list every time would itself be identifying. The fonts
    that every installation of the OS has, and the fonts used to detect the OS,
    are always included.
    """
    essential = frozenset(ESSENTIAL_FONTS[target_os])
    always = [f for f in families if f in essential]
    optional = [f for f in families if f not in essential]
    count = round(random.uniform(0.30, 0.78) * len(optional))
    ans = always + random.sample(optional, min(count, len(optional)))
    present = set(ans)
    available = frozenset(families)
    for marker in MARKER_FONTS[target_os]:
        # Only claim a marker font if the browser can really render it
        if marker not in present and marker in available:
            ans.append(marker)
    return sorted(ans)


def fontconfig_path(resource_dir: str, version: str, target_os: str) -> str:
    """Generate the fontconfig file that limits the fonts visible to the browser
    to the ones camoufox bundles for target_os, and return its path.

    The bundled fonts.conf refers to the font directory relative to the current
    working directory, which is of no use to us, so it is rewritten to use an
    absolute path. Only needed on Linux, elsewhere camoufox restricts the fonts
    itself.
    """
    for name in ('fontconfig', 'fontconfigs'):  # renamed in camoufox v150
        src = os.path.join(resource_dir, name, OS_DIRS[target_os], 'fonts.conf')
        if os.path.exists(src):
            break
    else:
        raise Error(f'The camoufox install in {resource_dir} has no fonts.conf for {target_os}')
    with open(src) as f:
        conf = f.read()
    fonts_dir = os.path.join(resource_dir, 'fonts')
    conf = conf.replace('<dir prefix="cwd">fonts</dir>', f'<dir>{fonts_dir}</dir>')
    base = os.path.join(cache_dir(), 'camoufox-fontconfig')
    os.makedirs(base, exist_ok=True)
    ans = os.path.join(base, f'fonts-{version}-{target_os}.conf')
    if not os.path.exists(ans):
        # Write atomically, several processes can be doing this at once
        fd, tmp = tempfile.mkstemp(dir=base, suffix='.conf')
        try:
            with open(fd, 'w') as f:
                f.write(conf)
            os.replace(tmp, ans)
        except BaseException:
            os.remove(tmp)
            raise
    return ans


# }}}


def generate_fingerprint(target_os: str, window: tuple[int, int] | None = None) -> dict[str, Any]:
    """Generate a random, internally consistent, fingerprint for target_os using
    browserforge and return it as a camoufox config."""
    browserforge_data()  # ensure the data files are present and up to date first
    from browserforge.fingerprints import FingerprintGenerator

    fingerprint = FingerprintGenerator(browser='firefox', os=(target_os,)).generate()
    from dataclasses import asdict

    data = asdict(fingerprint)
    if window is not None:
        screen = data['screen']
        outer_width, outer_height = window
        screen['screenX'] = (screen.get('screenX') or 0) + (screen['width'] - outer_width) // 2
        screen['screenY'] = (screen['height'] - outer_height) // 2
        if screen.get('innerWidth'):
            screen['innerWidth'] = max(outer_width - screen['outerWidth'] + screen['innerWidth'], 0)
        if screen.get('innerHeight'):
            screen['innerHeight'] = max(outer_height - screen['outerHeight'] + screen['innerHeight'], 0)
        screen['outerWidth'], screen['outerHeight'] = outer_width, outer_height
    return data


@lru_cache(maxsize=2)
def config_property_types(resource_dir: str) -> dict[str, str]:
    """The config properties the installed browser understands, mapped to their types."""
    with open(os.path.join(resource_dir, 'properties.json'), 'rb') as f:
        return {entry['property']: entry['type'] for entry in json.loads(f.read())}


def value_has_type(value: Any, expected: str) -> bool:  # noqa: ANN401
    match expected:
        case 'str':
            return isinstance(value, str)
        case 'bool':
            return isinstance(value, bool)
        case 'int' | 'uint':
            ok = (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and value.is_integer())
            return ok and (expected == 'int' or value >= 0)
        case 'double':
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        case 'array':
            return isinstance(value, list)
        case 'dict':
            return isinstance(value, dict)
    return False


def validate_config(config: Mapping[str, Any], resource_dir: str) -> None:
    """Check that config only contains properties the installed browser knows
    about, with values of the right type. Unknown properties are dropped by the
    browser, so they are merely reported, a wrongly typed value is an error."""
    types = config_property_types(resource_dir)
    for key, value in config.items():
        expected = types.get(key)
        if expected is None:
            debug(f'Ignoring the camoufox config property {key} which is not supported by this version of the browser')
        elif not value_has_type(value, expected):
            raise ValueError(f'The camoufox config property {key} must be of type {expected} not {type(value).__name__}')


def generate_config(
    resource_dir: str,
    version: str,
    *,
    target_os: str = '',
    window: tuple[int, int] | None = None,
    fonts: Sequence[str] | None = None,
    locale: str | Sequence[str] = '',
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the camoufox config used to spoof the browser fingerprint.

    :param resource_dir: the directory containing the browser's data files
    :param version: the version of the installed browser
    :param target_os: the OS to impersonate, defaults to the OS we are running on
    :param window: a fixed (width, height) for the browser window instead of a random one
    :param fonts: the font families to report, defaults to a random subset of the
        fonts camoufox bundles for target_os
    :param locale: the locale(s) to report, the first is used for the Intl API
    :param extra: config properties that override the generated ones

    Note that the camoufox ``humanize`` property, which has the browser expand
    every mouse movement into a path of its own, is deliberately not set here
    and must not be set through extra either: :class:`Mouse` generates paths
    itself and the two cannot be combined, see :class:`InputWedged` for what
    letting the browser do it costs.
    """
    target_os = check_valid_os(target_os or current_os())
    ff_version = version.split('.', 1)[0]
    config: dict[str, Any] = {}
    fingerprint = generate_fingerprint(target_os, window)
    cast_to_properties(config, BROWSERFORGE_MAP, fingerprint, ff_version)
    set_screen_y(config, fingerprint['screen'])
    fix_navigator_arch(config, target_os)
    clamp_window_dimensions(config)
    set_media_devices_defaults(config)

    # A browser that has never been used before is unusual, give it some history
    config['window.history.length'] = random.randrange(1, 6)

    if fonts is None:
        available = font_families(resource_dir, version, target_os)
        if available:
            config['fonts'] = random_font_subset(available, target_os)
    else:
        config['fonts'] = list(fonts)

    if locale:
        languages = (locale,) if isinstance(locale, str) else tuple(locale)
        if languages:
            primary = languages[0].replace('_', '-')
            language, _, region = primary.partition('-')
            config['locale:language'] = language
            if region:
                config['locale:region'] = region
            config['locale:all'] = ','.join(x.replace('_', '-') for x in languages)

    # Randomize the per-launch noise seeds. They must differ between runs or the
    # audio/canvas/font measurements they perturb become a stable identifier.
    for key in ('fonts:spacing_seed', 'audio:seed', 'canvas:seed'):
        config[key] = random.randrange(1, 4_294_967_296)

    if extra:
        config.update(extra)
    validate_config(config, resource_dir)
    return config


def config_environment(config: Mapping[str, Any]) -> dict[str, str]:
    """Encode config into the environment variables camoufox reads it from.

    The config is passed as JSON split over as many CAMOU_CONFIG_n variables as
    are needed to stay under the platform's limit on the size of a single
    environment variable.
    """
    raw = json.dumps(config, separators=(',', ':'))
    chunk_size = 2047 if iswindows else 32767
    return {f'CAMOU_CONFIG_{i + 1}': raw[pos : pos + chunk_size] for i, pos in enumerate(range(0, len(raw), chunk_size))}


# }}}

# Talking to the browser process {{{


def write_all(fd: int, data: bytes) -> None:
    while data:
        data = data[os.write(fd, data) :]


def close_fd(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


class Transport:
    """A NUL delimited JSON message channel to the browser process.

    The pipes the browser uses are ordinary blocking pipes, and on Windows they
    cannot be used with asyncio at all, so they are serviced by a pair of
    threads that hand messages to and from the event loop.
    """

    def __init__(self, read_fd: int, write_fd: int, loop: asyncio.AbstractEventLoop, on_message: Callable[[bytes], None], on_close: Callable[[], None]) -> None:
        self.read_fd, self.write_fd = read_fd, write_fd
        self.loop, self.on_message, self.on_close = loop, on_message, on_close
        self.write_queue: queue.SimpleQueue[bytes | None] = queue.SimpleQueue()
        self.closed = False
        self.reader = threading.Thread(target=self.read_loop, name='CamoufoxRead', daemon=True)
        self.writer = threading.Thread(target=self.write_loop, name='CamoufoxWrite', daemon=True)
        self.reader.start()
        self.writer.start()

    def call_in_loop(self, func: Callable[..., Any], *args: Any) -> None:  # noqa: ANN401
        try:
            self.loop.call_soon_threadsafe(func, *args)
        except RuntimeError:
            pass  # the loop has been closed, nothing left to deliver messages to

    def read_loop(self) -> None:
        buf = bytearray()
        while True:
            try:
                data = os.read(self.read_fd, 1024 * 1024)
            except OSError:
                break
            if not data:
                break
            buf.extend(data)
            while (pos := buf.find(b'\0')) != -1:
                message = bytes(buf[:pos])
                del buf[: pos + 1]
                self.call_in_loop(self.on_message, message)
        self.call_in_loop(self.on_close)

    def write_loop(self) -> None:
        while True:
            item = self.write_queue.get()
            if item is None:
                break
            try:
                write_all(self.write_fd, item)
            except OSError:
                break  # the browser has gone away, the reader will notice

    def send(self, message: Mapping[str, Any]) -> None:
        if self.closed:
            raise BrowserClosedError('The connection to the browser has been closed')
        self.write_queue.put(json.dumps(message, separators=(',', ':')).encode('utf-8') + b'\0')

    def close(self) -> None:
        """Close the command pipe. The browser treats this as a request to exit."""
        if self.closed:
            return
        self.closed = True
        self.write_queue.put(None)
        self.writer.join(timeout=5)
        close_fd(self.write_fd)

    def shutdown(self) -> None:
        """Release both pipes. Only safe once the browser has exited, as that is
        what makes the reader thread see end of file and stop."""
        self.close()
        self.reader.join(timeout=5)
        close_fd(self.read_fd)


class Process:
    """The running browser process, and the pipes used to talk to it."""

    def __init__(self, pid_or_handle: int, read_fd: int, write_fd: int, log_path: str) -> None:
        self.read_fd, self.write_fd, self.log_path = read_fd, write_fd, log_path
        self.returncode: int | None = None
        if iswindows:
            self.handle = pid_or_handle
            self.pid = 0
        else:
            self.pid = pid_or_handle

    def poll(self) -> int | None:
        raise NotImplementedError

    def wait(self, timeout: float) -> int | None:
        raise NotImplementedError

    def kill(self) -> None:
        raise NotImplementedError

    def cleanup(self, close_pipes: bool) -> None:
        """Release the operating system resources this process still owns. The
        pipes belong to the Transport once one has been created for them."""
        if close_pipes:
            close_fd(self.read_fd)
            close_fd(self.write_fd)

    def log_tail(self, num_lines: int = 30) -> str:
        try:
            with open(self.log_path, errors='replace') as f:
                return ''.join(f.readlines()[-num_lines:])
        except OSError:
            return ''


class PosixProcess(Process):
    def poll(self) -> int | None:
        if self.returncode is None:
            try:
                pid, status = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                self.returncode = -1
            else:
                if pid:
                    self.returncode = status
        return self.returncode

    def wait(self, timeout: float) -> int | None:
        deadline = time.monotonic() + timeout
        while self.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.returncode

    def kill(self) -> None:
        import signal

        if self.poll() is None:
            try:
                os.killpg(self.pid, signal.SIGKILL)
            except OSError:
                try:
                    os.kill(self.pid, signal.SIGKILL)
                except OSError:
                    pass
            self.wait(5)


def reserve_high_fd(fd: int, minimum: int = 5) -> int:
    """Move fd so that it does not collide with the descriptors we have to set up
    in the child, returning the new descriptor."""
    if fd >= minimum:
        return fd
    temporary = []
    try:
        while True:
            new = os.dup(fd)
            if new >= minimum:
                os.close(fd)
                return new
            temporary.append(new)
    finally:
        for x in temporary:
            os.close(x)


def spawn_posix(argv: Sequence[str], env: Mapping[str, str], log_path: str) -> PosixProcess:
    """Start the browser with its command pipe on fd 3 and its response pipe on fd 4."""
    command_read, command_write = os.pipe()
    response_read, response_write = os.pipe()
    command_read, response_write = reserve_high_fd(command_read), reserve_high_fd(response_write)
    command_write, response_read = reserve_high_fd(command_write), reserve_high_fd(response_read)
    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        pid = os.posix_spawn(
            argv[0],
            list(argv),
            dict(env),
            file_actions=[
                (os.POSIX_SPAWN_DUP2, command_read, 3),
                (os.POSIX_SPAWN_DUP2, response_write, 4),
                (os.POSIX_SPAWN_DUP2, log_fd, 1),
                (os.POSIX_SPAWN_DUP2, log_fd, 2),
            ],
            # Put the browser in its own process group so that, for example, a
            # Ctrl-C in a terminal does not kill it out from under us
            setpgroup=0,
        )
    except BaseException:
        for fd in (command_write, response_read):
            os.close(fd)
        raise
    finally:
        for fd in (command_read, response_write, log_fd):
            os.close(fd)
    return PosixProcess(pid, response_read, command_write, log_path)


# The block of inherited C runtime file descriptors is built outside the Windows
# only section below so that its layout can be tested on any platform
CRT_HANDLE_SIZE = 8 if struct.calcsize('P') == 8 else 4
# msvcrt file descriptor flags, from the ioinfo structure in the CRT sources
FOPEN, FPIPE, FDEV = 0x01, 0x08, 0x40


def crt_handle_block(handles: Sequence[int], flags: Sequence[int], handle_size: int = CRT_HANDLE_SIZE) -> bytes:
    """Build the block of inherited file descriptors that the Microsoft C runtime
    reads out of STARTUPINFO.lpReserved2.

    The browser finds its pipes with _get_osfhandle(3) and _get_osfhandle(4), so
    they have to be handed over as C runtime file descriptors, which Python's
    subprocess module cannot do. The layout is a count, then one flags byte per
    descriptor, then one handle per descriptor.
    """
    if len(handles) != len(flags):
        raise ValueError('There must be exactly one flags byte per handle')
    fmt = '<Q' if handle_size == 8 else '<I'
    invalid = 2 ** (8 * handle_size) - 1  # INVALID_HANDLE_VALUE, that is, -1
    ans = bytearray(struct.pack('<I', len(handles)))
    ans += bytes(flags)
    for handle in handles:
        ans += struct.pack(fmt, invalid if handle < 0 else handle)
    return bytes(ans)


if iswindows:  # {{{
    import ctypes
    import msvcrt
    import subprocess
    from ctypes import wintypes

    STARTF_USESTDHANDLES = 0x00000100
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_SUSPENDED = 0x00000004
    STILL_ACTIVE = 259
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION_CLASS = 1
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ('cb', wintypes.DWORD),
            ('lpReserved', wintypes.LPWSTR),
            ('lpDesktop', wintypes.LPWSTR),
            ('lpTitle', wintypes.LPWSTR),
            ('dwX', wintypes.DWORD),
            ('dwY', wintypes.DWORD),
            ('dwXSize', wintypes.DWORD),
            ('dwYSize', wintypes.DWORD),
            ('dwXCountChars', wintypes.DWORD),
            ('dwYCountChars', wintypes.DWORD),
            ('dwFillAttribute', wintypes.DWORD),
            ('dwFlags', wintypes.DWORD),
            ('wShowWindow', wintypes.WORD),
            ('cbReserved2', wintypes.WORD),
            ('lpReserved2', ctypes.POINTER(ctypes.c_byte)),
            ('hStdInput', wintypes.HANDLE),
            ('hStdOutput', wintypes.HANDLE),
            ('hStdError', wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('hProcess', wintypes.HANDLE),
            ('hThread', wintypes.HANDLE),
            ('dwProcessId', wintypes.DWORD),
            ('dwThreadId', wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ('ReadOperationCount', ctypes.c_ulonglong),
            ('WriteOperationCount', ctypes.c_ulonglong),
            ('OtherOperationCount', ctypes.c_ulonglong),
            ('ReadTransferCount', ctypes.c_ulonglong),
            ('WriteTransferCount', ctypes.c_ulonglong),
            ('OtherTransferCount', ctypes.c_ulonglong),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('PerProcessUserTimeLimit', ctypes.c_longlong),
            ('PerJobUserTimeLimit', ctypes.c_longlong),
            ('LimitFlags', wintypes.DWORD),
            ('MinimumWorkingSetSize', ctypes.c_size_t),
            ('MaximumWorkingSetSize', ctypes.c_size_t),
            ('ActiveProcessLimit', wintypes.DWORD),
            ('Affinity', ctypes.c_size_t),
            ('PriorityClass', wintypes.DWORD),
            ('SchedulingClass', wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ('IoInfo', IO_COUNTERS),
            ('ProcessMemoryLimit', ctypes.c_size_t),
            ('JobMemoryLimit', ctypes.c_size_t),
            ('PeakProcessMemoryUsed', ctypes.c_size_t),
            ('PeakJobMemoryUsed', ctypes.c_size_t),
        ]

    class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('TotalUserTime', ctypes.c_longlong),
            ('TotalKernelTime', ctypes.c_longlong),
            ('ThisPeriodTotalUserTime', ctypes.c_longlong),
            ('ThisPeriodTotalKernelTime', ctypes.c_longlong),
            ('TotalPageFaultCount', wintypes.DWORD),
            ('TotalProcesses', wintypes.DWORD),
            ('ActiveProcesses', wintypes.DWORD),
            ('TotalTerminatedProcesses', wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFOW),
        ctypes.POINTER(PROCESS_INFORMATION),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    kernel32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]

    def create_job_object() -> int:
        """Create a job object that kills everything still in it when its last
        handle is closed, so that no part of the browser can outlive us."""
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return 0
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(wintypes.HANDLE(job), JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS, ctypes.byref(info), ctypes.sizeof(info)):
            kernel32.CloseHandle(wintypes.HANDLE(job))
            return 0
        return job

    class WindowsProcess(Process):
        def __init__(self, pid_or_handle: int, read_fd: int, write_fd: int, log_path: str, job: int = 0) -> None:
            super().__init__(pid_or_handle, read_fd, write_fd, log_path)
            self.job = job

        def poll(self) -> int | None:
            if self.returncode is None and self.handle:
                code = wintypes.DWORD()
                if kernel32.GetExitCodeProcess(wintypes.HANDLE(self.handle), ctypes.byref(code)) and code.value != STILL_ACTIVE:
                    self.returncode = code.value
            return self.returncode

        def live_descendants(self) -> int:
            """The number of processes of the browser that are still running."""
            if not self.job:
                return 0
            info = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
            if not kernel32.QueryInformationJobObject(
                wintypes.HANDLE(self.job), JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION_CLASS, ctypes.byref(info), ctypes.sizeof(info), None
            ):
                return 0
            return info.ActiveProcesses

        def wait(self, timeout: float) -> int | None:
            # The browser is a tree of processes, one for the browser itself and
            # more for its tabs and its GPU and utility work. They keep files in
            # the profile directory open, and Windows refuses to delete a file
            # that is open, so wait for all of them, not just the one we
            # started, which can even be a launcher process that exits early.
            deadline = time.monotonic() + timeout
            if self.returncode is None and self.handle:
                kernel32.WaitForSingleObject(wintypes.HANDLE(self.handle), max(int(timeout * 1000), 0))
            if self.poll() is None:
                return None
            while self.live_descendants() and time.monotonic() < deadline:
                time.sleep(0.05)
            return None if self.live_descendants() else self.returncode

        def kill(self) -> None:
            if self.job:
                kernel32.TerminateJobObject(wintypes.HANDLE(self.job), 1)
            elif self.poll() is None and self.handle:
                kernel32.TerminateProcess(wintypes.HANDLE(self.handle), 1)
            self.wait(5)

        def cleanup(self, close_pipes: bool) -> None:
            super().cleanup(close_pipes)
            if self.handle:
                kernel32.CloseHandle(wintypes.HANDLE(self.handle))
                self.handle = 0
            if self.job:
                # Anything left in the job is killed by this
                kernel32.CloseHandle(wintypes.HANDLE(self.job))
                self.job = 0

    def spawn_windows(argv: Sequence[str], env: Mapping[str, str], log_path: str) -> WindowsProcess:
        """Start the browser with its command pipe on fd 3 and its response pipe on fd 4."""
        command_read, command_write = os.pipe()
        response_read, response_write = os.pipe()
        log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        null_fd = os.open(os.devnull, os.O_RDONLY)
        pi = PROCESS_INFORMATION()
        job = create_job_object()
        try:
            null_handle, log_handle = msvcrt.get_osfhandle(null_fd), msvcrt.get_osfhandle(log_fd)
            child_read, child_write = msvcrt.get_osfhandle(command_read), msvcrt.get_osfhandle(response_write)
            for handle in (null_handle, log_handle, child_read, child_write):
                os.set_handle_inheritable(handle, True)
            block = crt_handle_block(
                (null_handle, log_handle, log_handle, child_read, child_write),
                (FOPEN | FDEV, FOPEN | FDEV, FOPEN | FDEV, FOPEN | FPIPE, FOPEN | FPIPE),
            )
            buf = (ctypes.c_byte * len(block)).from_buffer_copy(block)
            si = STARTUPINFOW()
            si.cb = ctypes.sizeof(STARTUPINFOW)
            si.dwFlags = STARTF_USESTDHANDLES
            si.hStdInput, si.hStdOutput, si.hStdError = null_handle, log_handle, log_handle
            si.cbReserved2 = len(block)
            si.lpReserved2 = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))
            # The browser also accepts the pipes through the environment, set
            # them so that it works whether or not the Windows launcher process
            # is in play
            env = dict(env, PW_PIPE_READ=str(child_read), PW_PIPE_WRITE=str(child_write))
            environment = ctypes.create_unicode_buffer(''.join(f'{k}={v}\0' for k, v in env.items()) + '\0')
            if not kernel32.CreateProcessW(
                argv[0],
                ctypes.create_unicode_buffer(subprocess.list2cmdline(argv)),
                None,
                None,
                True,  # the child inherits the handles marked inheritable above
                # The process starts suspended so that it is in the job object
                # before it gets the chance to create any children of its own
                CREATE_UNICODE_ENVIRONMENT | CREATE_NEW_PROCESS_GROUP | CREATE_SUSPENDED,
                ctypes.cast(environment, ctypes.c_void_p),
                None,
                ctypes.byref(si),
                ctypes.byref(pi),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if job and not kernel32.AssignProcessToJobObject(wintypes.HANDLE(job), pi.hProcess):
                    debug(f'Failed to put the camoufox browser into a job object: {ctypes.WinError(ctypes.get_last_error())}')
                    kernel32.CloseHandle(wintypes.HANDLE(job))
                    job = 0
                if kernel32.ResumeThread(pi.hThread) == 0xFFFFFFFF:
                    raise ctypes.WinError(ctypes.get_last_error())
            except BaseException:
                kernel32.TerminateProcess(pi.hProcess, 1)
                kernel32.CloseHandle(pi.hProcess)
                raise
            finally:
                kernel32.CloseHandle(pi.hThread)
        except BaseException:
            if job:
                kernel32.CloseHandle(wintypes.HANDLE(job))
            for fd in (command_write, response_read):
                close_fd(fd)
            raise
        finally:
            # The child has its own copies of these now
            for fd in (command_read, response_write, log_fd, null_fd):
                close_fd(fd)
        return WindowsProcess(pi.hProcess, response_read, command_write, log_path, job)
# }}}


def spawn(argv: Sequence[str], env: Mapping[str, str], log_path: str) -> Process:
    if iswindows:
        return spawn_windows(argv, env, log_path)  # type: ignore[name-defined]
    return spawn_posix(argv, env, log_path)


def remove_profile_dir(path: str, timeout: float = PROFILE_REMOVE_TIMEOUT) -> None:
    """Delete a browser profile directory, waiting for it to become deletable.

    On Windows a file cannot be deleted while any process has it open, and the
    handles that keep a freshly written profile open outlive the browser that
    wrote it: a virus scanner or the search indexer picks the files up as they
    are created and holds them for a while, and a file that is deleted while
    open keeps its directory entry, so removing the directory itself fails
    with ENOTEMPTY until the last handle goes away. None of those handles are
    ours to close, so the only thing to do is keep trying, which takes at most
    a second or two in practice. Every step of this blocks, so it must be run
    in a worker thread rather than on the event loop.
    """
    deadline = time.monotonic() + timeout
    delay = 0.01
    while True:
        try:
            shutil.rmtree(make_long_path_useable(path))
            return
        except FileNotFoundError:
            return
        except OSError as err:
            if time.monotonic() >= deadline:
                # Whatever is holding the profile open is not going to let go,
                # so hand it to the atexit worker, which will delete it once
                # this process, and hopefully the culprit, are gone
                debug(f'Failed to delete the camoufox profile directory {path} with error: {err}')
                remove_folder_atexit(path)
                return
            time.sleep(delay)
            delay = min(2 * delay, 0.5)


# }}}

# The protocol {{{


class Connection:
    """Dispatches Juggler protocol messages to and from the browser."""

    def __init__(self) -> None:
        self.transport: Transport | None = None
        self.message_id = 0
        self.replies: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.event_handlers: dict[str, Callable[[str, dict[str, Any]], None]] = {}
        self.root_handler: Callable[[str, dict[str, Any]], None] | None = None
        self.closed_error: BrowserClosedError | None = None
        self.on_closed: Callable[[], None] | None = None

    def start(self, process: Process, loop: asyncio.AbstractEventLoop) -> None:
        self.transport = Transport(process.read_fd, process.write_fd, loop, self.message_received, self.connection_lost)

    def message_received(self, raw: bytes) -> None:
        try:
            message = json.loads(raw)
        except ValueError:
            debug(f'Ignoring unparseable message from the browser: {raw[:256]!r}')
            return
        if (message_id := message.get('id')) is not None:
            if (future := self.replies.pop(message_id, None)) is not None and not future.done():
                future.set_result(message)
            return
        method, params = message.get('method', ''), message.get('params') or {}
        session_id = message.get('sessionId')
        if session_id:
            if (handler := self.event_handlers.get(session_id)) is not None:
                handler(method, params)
        elif self.root_handler is not None:
            self.root_handler(method, params)

    def connection_lost(self) -> None:
        self.closed_error = BrowserClosedError('The browser process exited')
        for future in self.replies.values():
            if not future.done():
                future.set_exception(self.closed_error)
        self.replies.clear()
        if self.on_closed is not None:
            self.on_closed()

    def send_nowait(self, method: str, params: Mapping[str, Any] | None = None, session_id: str = '') -> int:
        if self.closed_error is not None:
            raise self.closed_error
        assert self.transport is not None
        self.message_id += 1
        message: dict[str, Any] = {'id': self.message_id, 'method': method, 'params': params or {}}
        if session_id:
            message['sessionId'] = session_id
        self.transport.send(message)
        return self.message_id

    async def send(self, method: str, params: Mapping[str, Any] | None = None, session_id: str = '', timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        message_id = self.send_nowait(method, params, session_id)
        self.replies[message_id] = future
        try:
            async with asyncio.timeout(timeout):
                message = await future
        except TimeoutError:
            self.replies.pop(message_id, None)
            raise TimeoutExceeded(f'{method} did not complete in {timeout} seconds')
        if (error := message.get('error')) is not None:
            raise ProtocolError(method, error.get('message') or 'Unknown error', error.get('data') or '')
        # A method with no return value produces a message with no result at all
        return message.get('result') or {}

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()


class Event(NamedTuple):
    method: str
    params: dict[str, Any]


class EventWaiter:
    """Waits for a protocol event matching a predicate."""

    def __init__(self) -> None:
        self.waiters: list[tuple[Callable[[str, Mapping[str, Any]], bool], asyncio.Future[Event]]] = []

    def dispatch(self, method: str, params: dict[str, Any]) -> None:
        for entry in tuple(self.waiters):
            predicate, future = entry
            if future.done():
                self.waiters.remove(entry)
                continue
            try:
                matched = predicate(method, params)
            except Exception:
                matched = False
            if matched:
                future.set_result(Event(method, params))
                self.waiters.remove(entry)

    def expect(self, predicate: Callable[[str, Mapping[str, Any]], bool]) -> asyncio.Future[Event]:
        future: asyncio.Future[Event] = asyncio.get_running_loop().create_future()
        self.waiters.append((predicate, future))
        return future

    def abort(self, error: Exception) -> None:
        for _, future in self.waiters:
            if not future.done():
                future.set_exception(error)
        self.waiters.clear()


async def wait_for(future: asyncio.Future[Any], timeout: float, what: str) -> Any:  # noqa: ANN401
    try:
        async with asyncio.timeout(timeout):
            return await future
    except TimeoutError:
        future.cancel()
        raise TimeoutExceeded(f'Timed out after {timeout} seconds waiting for {what}')


# }}}

# JavaScript run inside pages {{{

REMOVE_JS = '''(selector) => {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) node.remove();
    return nodes.length;
}'''

SET_ATTRIBUTE_JS = '''(selector, name, value) => {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) node.setAttribute(name, value);
    return nodes.length;
}'''

DELETE_ATTRIBUTE_JS = '''(selector, name) => {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) node.removeAttribute(name);
    return nodes.length;
}'''

APPEND_CHILD_JS = '''(selector, tag, attributes, text) => {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) {
        const child = node.ownerDocument.createElement(tag);
        for (const name of Object.keys(attributes)) child.setAttribute(name, attributes[name]);
        if (text) child.appendChild(node.ownerDocument.createTextNode(text));
        node.appendChild(child);
    }
    return nodes.length;
}'''

INSERT_HTML_JS = '''(selector, html, position) => {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) node.insertAdjacentHTML(position, html);
    return nodes.length;
}'''

SET_TEXT_JS = '''(selector, text) => {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) node.textContent = text;
    return nodes.length;
}'''

WAIT_FOR_SELECTOR_JS = '''(selector, timeout, visible) => new Promise((resolve) => {
    const match = () => {
        for (const el of document.querySelectorAll(selector)) {
            if (!visible) return el;
            const rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0 && getComputedStyle(el).visibility !== 'hidden') return el;
        }
        return null;
    };
    const found = match();
    if (found) { resolve(found); return; }
    let observer = null, timer = null;
    const done = (value) => {
        if (observer) observer.disconnect();
        if (timer !== null) clearTimeout(timer);
        resolve(value);
    };
    observer = new MutationObserver(() => { const el = match(); if (el) done(el); });
    observer.observe(document.documentElement, {childList: true, subtree: true, attributes: true});
    timer = setTimeout(() => done(null), timeout);
    const again = match();
    if (again) done(again);
})'''

# Text can only be inserted into an element that can hold it, and inserting it
# into anything else quietly does nothing at all, see Keyboard.insert_text().
# The types listed are the ones an input element cannot hold text for.
FOCUSED_IS_EDITABLE_JS = '''() => {
    const node = document.activeElement;
    if (!node || node === document.body) return false;
    if (node.isContentEditable) return true;
    const name = node.localName;
    if (name === 'textarea') return !node.disabled && !node.readOnly;
    if (name !== 'input') return false;
    const kind = (node.type || 'text').toLowerCase();
    const uneditable = ['checkbox', 'radio', 'button', 'submit', 'reset', 'file', 'image', 'range', 'color', 'hidden'];
    return !node.disabled && !node.readOnly && !uneditable.includes(kind);
}'''

# Scripts run behind Xray wrappers, which forbid reading the contents of a typed
# array, so the bytes are turned into base64 by the browser itself rather than by
# walking a Uint8Array. It has to be an async function because the promise
# fetch() hands out is invisible to the browser, see Page.evaluate().
FETCH_JS = '''async (url) => {
    const response = await fetch(url, {credentials: 'include'});
    const blob = await response.blob();
    const dataURL = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(blob);
    });
    return {
        status: response.status,
        contentType: response.headers.get('content-type') || '',
        base64: dataURL.slice(dataURL.indexOf(',') + 1),
    };
}'''

# }}}


# Human like mouse input {{{

# The browser can generate humanized cursor paths itself, and camoufox's
# humanize property switches that on, but it is not used here and Browser does
# not switch it on. It does so with a fixed ten milliseconds between the points
# of every path, no way to vary that or skip it for an individual movement, and
# it does nothing about the timing of the click itself. Worse, the points it
# generates are its own business: they are fractional, consecutive ones can
# land on the same pixel, and a movement onto the pixel the cursor is already
# on is never answered, see Mouse.dispatch. The two cannot be combined either,
# since the browser expands every single mousemove it is sent into a full path
# of its own. So paths are generated here instead.

# The number the protocol uses for each mouse button and the bit the DOM uses
# to report that button as being held down
MOUSE_BUTTONS = {'left': (0, 1), 'middle': (1, 4), 'right': (2, 2)}
# The bits the protocol uses for the modifier keys
MODIFIERS = {'alt': 1, 'control': 2, 'shift': 4, 'meta': 8}

VIEWPORT_MARGIN = 1.0  # pixels of the edge of the viewport that are never aimed at, see clamp_to_viewport()
MIN_MOVE_TIME = 0.05  # seconds, the quickest a movement is ever performed
MAX_MOVE_TIME = 0.9  # seconds, about as long as a hand takes to cross a large window
# One position per screen refresh. Sending them faster than the browser paints
# them costs a round trip each without the page seeing a different cursor.
MOVE_STEP_TIME = 0.016  # seconds between consecutive positions along a path
MAX_MOVE_STEPS = 24  # every position along a path costs a round trip to the browser
SETTLE_TIME = (0.02, 0.09)  # seconds the hand rests on the target before pressing
CLICK_DWELL = (0.045, 0.125)  # seconds a button is held down for
DOUBLE_CLICK_INTERVAL = (0.07, 0.16)  # seconds between the clicks of a multiple click
OVERSHOOT_DISTANCE = 250.0  # pixels, a hand does not overshoot a target closer than this
OVERSHOOT_PROBABILITY = 0.5

# The source of randomness for cursor paths, click timing and the rhythm of
# typing. Tests pass their own seeded generator to human_trajectory() and to
# human_typing_plan() to get reproducible paths and keystrokes.
MOTION_RNG = random.Random()


def mouse_button(name: str) -> tuple[int, int]:
    """The protocol's number for a mouse button and the DOM's bit for it."""
    try:
        return MOUSE_BUTTONS[name]
    except KeyError:
        raise ValueError(f'{name!r} is not a known mouse button, expected one of: {", ".join(MOUSE_BUTTONS)}')


def modifier_mask(names: Iterable[str]) -> int:
    """The bitmask for a collection of modifier key names."""
    ans = 0
    for name in names:
        try:
            ans |= MODIFIERS[name]
        except KeyError:
            raise ValueError(f'{name!r} is not a known modifier key, expected one of: {", ".join(MODIFIERS)}')
    return ans


def cubic_bezier(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float], t: float) -> tuple[float, float]:
    """The point at position t along the cubic Bezier curve with the given control points."""
    u = 1.0 - t
    a, b, c, d = u * u * u, 3.0 * u * u * t, 3.0 * u * t * t, t * t * t
    return a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]


def ease(t: float) -> float:
    """Map progress along a path onto progress through time.

    A hand does not move at a constant speed, it accelerates away from where it
    started and slows down as it closes on its target. This is the usual
    quintic curve for that, biased so that the acceleration is brisker than the
    deceleration, which is what aiming at something actually looks like.
    """
    return (t * t * t * (t * (t * 6.0 - 15.0) + 10.0)) ** 0.85


def curve_through(start: tuple[float, float], end: tuple[float, float], steps: int, rng: random.Random) -> list[tuple[float, float]]:
    """steps positions along a gently bowed path from start to end.

    The path is a cubic Bezier whose two control points are pushed off the
    straight line between the ends, which is the arc a hand sweeping a mouse
    makes. Positions are sampled with the velocity profile of :func:`ease` and
    jittered by a pixel or so of tremor. start itself is not included and the
    last position is exactly end.
    """
    dx, dy = end[0] - start[0], end[1] - start[1]
    distance = math.hypot(dx, dy)
    if not distance:
        return [end] * steps
    ux, uy = dx / distance, dy / distance  # along the straight line
    nx, ny = -uy, ux  # at right angles to it
    # The further a hand travels the more it bows the path, but proportionally less
    arc = min(0.12 * distance, 2.0 * math.sqrt(distance) + 2.0)
    sign = rng.choice((-1.0, 1.0))
    # Both control points are usually pushed the same way, giving a simple arc,
    # and occasionally opposite ways, giving the gentle S a wrist sometimes makes
    offsets = (sign * arc * rng.uniform(0.25, 1.0), sign * (-1.0 if rng.random() < 0.2 else 1.0) * arc * rng.uniform(0.25, 1.0))
    fractions = (rng.uniform(0.15, 0.4), rng.uniform(0.6, 0.9))
    controls = [(start[0] + ux * distance * f + nx * o, start[1] + uy * distance * f + ny * o) for f, o in zip(fractions, offsets, strict=True)]
    tremor = min(1.5, 0.1 * math.sqrt(distance))
    ans = []
    for i in range(1, steps + 1):
        t = ease(i / steps)
        x, y = cubic_bezier(start, controls[0], controls[1], end, t)
        # The tremor is faded out at both ends so that the movement starts and
        # finishes exactly where it is supposed to
        shake = tremor * math.sin(math.pi * t)
        ans.append((x + rng.uniform(-shake, shake), y + rng.uniform(-shake, shake)))
    ans[-1] = end
    return ans


def human_trajectory(
    start: tuple[float, float], end: tuple[float, float], *, max_time: float = MAX_MOVE_TIME, rng: random.Random | None = None
) -> list[tuple[float, float, float]]:
    """A human like path for the cursor to follow from start to end.

    Returns ``(x, y, t)`` triples, where t is the number of seconds after the
    movement begins at which the cursor should be at ``(x, y)``. The last
    position is always exactly end. An empty list means the cursor is already
    close enough that nothing needs to be sent.

    :param max_time: the longest the movement may take, in seconds
    :param rng: the source of randomness, pass a seeded one for reproducible paths
    """
    r = MOTION_RNG if rng is None else rng
    dx, dy = end[0] - start[0], end[1] - start[1]
    distance = math.hypot(dx, dy)
    if distance < 1.0:  # the browser discards a movement within the same pixel
        return []
    # Fitts's law: the time taken to point at something grows with the
    # logarithm of how far away it is rather than in proportion to it
    duration = (0.09 + 0.075 * math.log2(distance / 12.0 + 1.0)) * r.uniform(0.8, 1.35)
    steps = min(max(round(duration / MOVE_STEP_TIME), 2), MAX_MOVE_STEPS)
    if distance > OVERSHOOT_DISTANCE and r.random() < OVERSHOOT_PROBABILITY:
        # A hand moving quickly tends to shoot past a distant target and then
        # make a second, small movement back onto it
        amount = min(0.04 * distance, 24.0) + r.uniform(2.0, 8.0)
        ux, uy = dx / distance, dy / distance
        sideways = r.uniform(-0.5, 0.5) * amount
        aim = (end[0] + ux * amount - uy * sideways, end[1] + uy * amount + ux * sideways)
        correcting = max(2, steps // 5)
        points = curve_through(start, aim, max(2, steps - correcting), r) + curve_through(aim, end, correcting, r)
        duration *= 1.2  # the correction is a second movement, it takes its own time
    else:
        points = curve_through(start, end, steps, r)
    duration = min(max(duration, MIN_MOVE_TIME), max_time)
    # Pointer events do not arrive on a perfectly regular clock
    weights = [r.uniform(0.85, 1.15) for _ in points]
    total = sum(weights)
    ans, elapsed = [], 0.0
    for (x, y), weight in zip(points, weights, strict=True):
        elapsed += weight
        ans.append((x, y, duration * elapsed / total))
    ans[-1] = (ans[-1][0], ans[-1][1], duration)  # the division above is not exact
    return ans


def quad_area(corners: Sequence[tuple[float, float]]) -> float:
    """The area of a polygon, by the shoelace formula."""
    ans = 0.0
    for i, (x1, y1) in enumerate(corners):
        x2, y2 = corners[(i + 1) % len(corners)]
        ans += x1 * y2 - x2 * y1
    return abs(ans) / 2.0


def quad_contains(corners: Sequence[tuple[float, float]], point: tuple[float, float]) -> bool:
    """Whether point lies inside the convex polygon corners."""
    sign = 0
    for i, (x1, y1) in enumerate(corners):
        x2, y2 = corners[(i + 1) % len(corners)]
        cross = (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)
        if cross:
            current = 1 if cross > 0 else -1
            if sign and current != sign:
                return False
            sign = current
    return True


def whole_pixel(value: float) -> float:
    """The whole pixel nearest to value.

    Halves go up, the way the browser rounds a coordinate, rather than to even,
    the way :func:`round` does.
    """
    return float(math.floor(value + 0.5))


def point_to_aim_at(corners: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """A whole pixel in the middle of a convex polygon.

    Mouse events are always dispatched at whole pixels, see
    :meth:`Mouse.dispatch`, so the middle is snapped onto one. A thin or
    slanted quad need not contain the pixel nearest its middle, so the
    neighbouring ones are tried before giving up and using it anyway.
    """
    x = sum(corner[0] for corner in corners) / len(corners)
    y = sum(corner[1] for corner in corners) / len(corners)
    candidates = ((whole_pixel(x), whole_pixel(y)), *((float(px), float(py)) for px in (math.floor(x), math.ceil(x)) for py in (math.floor(y), math.ceil(y))))
    for candidate in candidates:
        if quad_contains(corners, candidate):
            return candidate
    return candidates[0]


def clamp_to_viewport(x: float, y: float, width: float, height: float) -> tuple[float, float]:
    """The whole pixel nearest to (x, y) that is safely inside a viewport of the given size.

    An event aimed outside the viewport is not delivered to the page. Rather
    than say so, the browser moves the cursor off the page altogether and stops
    keeping track of where it is, which leaves it somewhere neither we nor the
    browser expects. Paths bow and overshoot, so one that runs along an edge of
    the viewport does stray outside it.

    An event aimed at the very edge of the viewport is worse: the browser
    decides where the edge is from the size of the window it draws the page in,
    which differs by a fraction of a pixel from the ``window.innerWidth`` and
    ``window.innerHeight`` the page reports, so an event on the last row or
    column can be delivered as the cursor leaving the page instead of moving
    within it, and then it is never acknowledged, see :class:`InputWedged`.
    That fraction is unknowable from out here, so :data:`VIEWPORT_MARGIN`
    pixels of the edge are left alone.
    """

    def clamp(value: float, size: float) -> float:
        high = max(size - 1.0 - VIEWPORT_MARGIN, 0.0)
        return min(max(whole_pixel(value), min(VIEWPORT_MARGIN, high)), high)

    return clamp(x, width), clamp(y, height)


def clamp_quad(quad: Mapping[str, Mapping[str, float]], width: float, height: float) -> list[tuple[float, float]]:
    """The corners of a quad from the protocol, clipped to a viewport of the given size."""
    return [(min(max(float(p['x']), 0.0), width), min(max(float(p['y']), 0.0), height)) for p in (quad['p1'], quad['p2'], quad['p3'], quad['p4'])]


class Mouse:
    """Moves the cursor and clicks, the way a hand does.

    Available as :attr:`Page.mouse`. Coordinates are in CSS pixels measured
    from the top left corner of the viewport, and the cursor always comes to
    rest on a whole one of them, see :meth:`dispatch`.
    """

    def __init__(self, page: Page) -> None:
        self.page = page
        # Where the browser thinks the cursor is. It starts in the top left
        # corner and moves only when we tell it to.
        self.x, self.y = 0.0, 0.0
        # Whether that is still to be trusted. An event that was not answered
        # may or may not have moved the cursor before it was given up on.
        self.position_known = True
        self.buttons = 0  # the bitmask of the buttons currently held down

    def __repr__(self) -> str:
        where = f'({self.x:.0f}, {self.y:.0f})' if self.position_known else 'an unknown position'
        return f'<Mouse at {where}>'

    @property
    def position(self) -> tuple[float, float]:
        """The whole pixel the cursor is currently on."""
        return self.x, self.y

    async def dispatch(self, event_type: str, x: float, y: float, *, button: int = 0, click_count: int = 0, modifiers: int = 0) -> None:
        """Send a single mouse event to the page, at the whole pixel nearest to (x, y).

        The browser does not reply until the event has reached the page, and a
        fractional coordinate is snapped to a pixel of the browser window,
        whose grid is not necessarily the one this coordinate is measured on,
        so sending one risks an event that never arrives anywhere and a command
        that never completes, see :meth:`move_onto_pixel`. An event that has
        not been answered within :data:`INPUT_TIMEOUT` never will be, and it
        takes every later event down with it, see :class:`InputWedged`.
        """
        self.page.check_accepts_input()
        try:
            await self.page.send(
                'Page.dispatchMouseEvent',
                {
                    'type': event_type,
                    'x': whole_pixel(x),
                    'y': whole_pixel(y),
                    'button': button,
                    'buttons': self.buttons,
                    'modifiers': modifiers,
                    'clickCount': click_count,
                },
                timeout=INPUT_TIMEOUT,
            )
        except TimeoutExceeded as err:
            self.position_known = False
            self.page.input_wedged = True
            raise InputWedged(
                f'The browser did not acknowledge a {event_type} at ({whole_pixel(x):.0f}, {whole_pixel(y):.0f}) within'
                f' {INPUT_TIMEOUT} seconds, so this page can no longer be given input. {await self.page.input_diagnostics()}'
            ) from err
        except BaseException:
            self.position_known = False
            raise

    async def move_onto_pixel(self, x: float, y: float, modifiers: int = 0) -> None:
        """Move the cursor onto the whole pixel nearest to (x, y).

        Nothing is sent if the cursor is already on that pixel. A movement that
        does not take the cursor to a new pixel never reaches the page, and the
        browser acknowledges a mouse event only once the page has seen it, so
        such a movement is never answered at all and would instead be waited on
        until the command times out.
        """
        px, py = whole_pixel(x), whole_pixel(y)
        if not self.position_known or (px, py) != (self.x, self.y):
            await self.dispatch('mousemove', px, py, modifiers=modifiers)
            self.x, self.y = px, py
            self.position_known = True

    async def move(self, x: float, y: float, *, human: bool | None = None, max_time: float | None = None, modifiers: Sequence[str] = ()) -> None:
        """Move the cursor onto the whole pixel nearest to (x, y).

        The destination and every position on the way to it are moved inside
        the viewport if they are not already, see :func:`clamp_to_viewport`.
        Raises :class:`InputWedged` without sending or waiting for anything if
        the page has already stopped acknowledging input.

        :param human: follow a human like path instead of jumping straight
            there. The default, None, means do so.
        :param max_time: the longest the movement may take, in seconds. The
            default, None, means the browser's, see :class:`Browser`.
        :param modifiers: the modifier keys to hold down, see :data:`MODIFIERS`
        """
        self.page.check_accepts_input()
        mask = modifier_mask(modifiers)
        if human is None:
            human = True
        if max_time is None:
            max_time = self.page.browser.max_move_time
        width, height = await self.page.viewport()
        x, y = clamp_to_viewport(x, y, width, height)
        if human:
            started = time.monotonic()
            for px, py, at in human_trajectory((self.x, self.y), (x, y), max_time=max_time):
                if (delay := started + at - time.monotonic()) > 0:
                    await asyncio.sleep(delay)
                await self.move_onto_pixel(*clamp_to_viewport(px, py, width, height), mask)
        # The steps of a path that land on the pixel the cursor is already on
        # are skipped, including the last one, so the journey is finished here
        await self.move_onto_pixel(x, y, mask)

    async def down(self, button: str = 'left', *, click_count: int = 1, modifiers: Sequence[str] = ()) -> None:
        """Press a mouse button where the cursor currently is.

        The cursor is moved out of the edge of the viewport first if it is
        still in the top left corner it starts in and has not been moved since,
        because a button pressed there is never acknowledged, see
        :func:`clamp_to_viewport`. Anywhere it has been moved to is already
        clear of the edges.
        """
        number, bit = mouse_button(button)
        self.page.check_accepts_input()
        await self.move_onto_pixel(*clamp_to_viewport(self.x, self.y, *await self.page.viewport()), modifier_mask(modifiers))
        self.buttons |= bit
        try:
            await self.dispatch('mousedown', self.x, self.y, button=number, click_count=click_count, modifiers=modifier_mask(modifiers))
        except BaseException:
            self.buttons &= ~bit
            raise

    async def up(self, button: str = 'left', *, click_count: int = 1, modifiers: Sequence[str] = ()) -> None:
        """Release a mouse button where the cursor currently is."""
        number, bit = mouse_button(button)
        self.page.check_accepts_input()
        self.buttons &= ~bit
        try:
            await self.dispatch('mouseup', self.x, self.y, button=number, click_count=click_count, modifiers=modifier_mask(modifiers))
        except BaseException:
            self.buttons |= bit
            raise

    async def click(
        self,
        x: float,
        y: float,
        *,
        button: str = 'left',
        click_count: int = 1,
        delay: float | None = None,
        human: bool | None = None,
        max_time: float | None = None,
        modifiers: Sequence[str] = (),
    ) -> None:
        """Move the cursor to (x, y) and click there.

        :param button: one of ``left``, ``middle`` or ``right``
        :param click_count: 2 for a double click, 3 for a triple click
        :param delay: how long to hold the button down for, in seconds. The
            default, None, means a randomly chosen human like duration.
        :param human: see :meth:`move`
        """
        mouse_button(button)  # fail before moving if the button name is not valid
        if click_count < 1:
            raise ValueError(f'{click_count} is not a valid number of clicks')
        await self.move(x, y, human=human, max_time=max_time, modifiers=modifiers)
        # A hand comes to rest on its target before the finger presses
        await asyncio.sleep(MOTION_RNG.uniform(*SETTLE_TIME))
        for i in range(click_count):
            if i:
                await asyncio.sleep(MOTION_RNG.uniform(*DOUBLE_CLICK_INTERVAL))
            await self.down(button, click_count=i + 1, modifiers=modifiers)
            await asyncio.sleep(MOTION_RNG.uniform(*CLICK_DWELL) if delay is None else delay)
            await self.up(button, click_count=i + 1, modifiers=modifiers)


# }}}


# Human like keyboard input {{{

# Key events name a physical key, so the tables below are those of a US
# layout, the one the fingerprints generated here always claim. There is no
# numpad and no other layout: the point of them is to type into forms, not to
# emulate a keyboard.


class KeyInfo(NamedTuple):
    """The fields a page sees for a single key."""

    key: str  # the value the page sees as event.key
    code: str  # the physical key, event.code
    key_code: int  # the legacy event.keyCode
    location: int = 0  # 1 for the left hand copy of a modifier, see NAMED_KEYS
    shifted: bool = False  # whether shift has to be held down to produce this key


# The four rows of the layout, unshifted and shifted, from which every table
# below is derived: which key produces a character, which shifted character
# that key also produces, which keys are next to it and which hand types it
KEY_ROWS = ('`1234567890-=', 'qwertyuiop[]\\', "asdfghjkl;'", 'zxcvbnm,./')
SHIFTED_KEY_ROWS = ('~!@#$%^&*()_+', 'QWERTYUIOP{}|', 'ASDFGHJKL:"', 'ZXCVBNM<>?')
# The event.code of each key of each row
ROW_CODES = (
    ('Backquote', *(f'Digit{d}' for d in '1234567890'), 'Minus', 'Equal'),
    (*(f'Key{c}' for c in 'QWERTYUIOP'), 'BracketLeft', 'BracketRight', 'Backslash'),
    (*(f'Key{c}' for c in 'ASDFGHJKL'), 'Semicolon', 'Quote'),
    (*(f'Key{c}' for c in 'ZXCVBNM'), 'Comma', 'Period', 'Slash'),
)
# The legacy event.keyCode of each key of each row. A letter uses the code
# point of its capital, the rest are the fixed numbers a browser reports.
ROW_KEY_CODES = (
    (192, 49, 50, 51, 52, 53, 54, 55, 56, 57, 48, 189, 187),
    (*(ord(c) for c in 'QWERTYUIOP'), 219, 221, 220),
    (*(ord(c) for c in 'ASDFGHJKL'), 186, 222),
    (*(ord(c) for c in 'ZXCVBNM'), 188, 190, 191),
)
# How many keys at the start of each row the left hand types
ROW_LEFT_HAND = (6, 5, 5, 5)

# The keys that are not characters. Firefox reports a modifier as its left
# hand copy, which is the one a hand reaches for by default.
NAMED_KEYS: dict[str, KeyInfo] = {
    'Enter': KeyInfo('Enter', 'Enter', 13),
    'Tab': KeyInfo('Tab', 'Tab', 9),
    'Backspace': KeyInfo('Backspace', 'Backspace', 8),
    'Delete': KeyInfo('Delete', 'Delete', 46),
    'Escape': KeyInfo('Escape', 'Escape', 27),
    'ArrowLeft': KeyInfo('ArrowLeft', 'ArrowLeft', 37),
    'ArrowUp': KeyInfo('ArrowUp', 'ArrowUp', 38),
    'ArrowRight': KeyInfo('ArrowRight', 'ArrowRight', 39),
    'ArrowDown': KeyInfo('ArrowDown', 'ArrowDown', 40),
    'Home': KeyInfo('Home', 'Home', 36),
    'End': KeyInfo('End', 'End', 35),
    'PageUp': KeyInfo('PageUp', 'PageUp', 33),
    'PageDown': KeyInfo('PageDown', 'PageDown', 34),
    'Insert': KeyInfo('Insert', 'Insert', 45),
    'CapsLock': KeyInfo('CapsLock', 'CapsLock', 20),
    'ContextMenu': KeyInfo('ContextMenu', 'ContextMenu', 93),
    'Shift': KeyInfo('Shift', 'ShiftLeft', 16, 1),
    'Control': KeyInfo('Control', 'ControlLeft', 17, 1),
    'Alt': KeyInfo('Alt', 'AltLeft', 18, 1),
    'Meta': KeyInfo('Meta', 'MetaLeft', 224, 1),
    **{f'F{i}': KeyInfo(f'F{i}', f'F{i}', 111 + i) for i in range(1, 13)},
}
NAMED_KEYS_BY_LOWER = {name.lower(): info for name, info in NAMED_KEYS.items()}
# The names people actually write for the keys above
KEY_ALIASES = {
    'esc': 'Escape',
    'del': 'Delete',
    'return': 'Enter',
    'space': ' ',
    'spacebar': ' ',
    'up': 'ArrowUp',
    'down': 'ArrowDown',
    'left': 'ArrowLeft',
    'right': 'ArrowRight',
    'pgup': 'PageUp',
    'pgdn': 'PageDown',
    'ctrl': 'Control',
    'cmd': 'Meta',
    'command': 'Meta',
    'super': 'Meta',
    'win': 'Meta',
    'windows': 'Meta',
    'option': 'Alt',
    'menu': 'ContextMenu',
}
MODIFIER_KEY_NAMES = ('Shift', 'Control', 'Alt', 'Meta')
# The chord that selects everything in the focused field. Which one it is
# depends on the machine the browser actually runs on, not on the operating
# system its fingerprint claims, since the key handling is the real one.
SELECT_ALL_CHORD = 'meta+a' if ismacos else 'control+a'

DEFAULT_TYPING_WPM = 55.0  # words per minute, a moderately quick typist who is not a professional one
CHARS_PER_WORD = 5.0  # the conventional definition of a word when measuring typing speed
KEY_INTERVAL_SPREAD = 0.34  # the sigma of the lognormal distribution the gaps between keystrokes are drawn from
MIN_KEY_INTERVAL = 0.02  # seconds, no two keystrokes are ever closer together than this
MAX_KEY_INTERVAL = 2.5  # seconds, the tail of the distribution is cut off here
KEY_DWELL = (0.045, 0.11)  # seconds a key is held down for
KEY_REPEAT_INTERVAL = (0.07, 0.16)  # seconds between two presses of the same key
SHIFT_LEAD = (0.04, 0.11)  # seconds between pressing shift and the key it shifts
SHIFT_TRAIL = (0.02, 0.06)  # seconds shift stays down after the last key it shifted
SAME_HAND_PENALTY = 1.22  # two keys in a row typed with the same hand are slower than alternating ones
SAME_KEY_PENALTY = 1.4  # a doubled letter is slower still
AWKWARD_KEY_PENALTY = 1.3  # digits, punctuation and symbols, which are typed far less often than letters
SHIFTED_KEY_PENALTY = 1.25  # a capital or a symbol costs the time to reach for shift
WORD_PAUSE_PROBABILITY = 0.12  # how often the space between two words becomes a pause for thought
WORD_PAUSE = (0.2, 0.75)  # seconds of that pause, at DEFAULT_TYPING_WPM
LINE_PAUSE = (0.1, 0.4)  # seconds of pause after a newline, at DEFAULT_TYPING_WPM
MISTAKE_NOTICE = (0.12, 0.5)  # seconds between typing a wrong character and noticing it
MISTAKE_REPAIR = (0.08, 0.3)  # seconds between deleting a wrong character and typing the right one
# Characters that belong to the character before them rather than standing on
# their own: the zero width joiner and the two variation selectors
ATTACHING_CHARS = '\u200d\ufe0e\ufe0f'


def build_key_tables() -> tuple[dict[str, KeyInfo], dict[str, str], dict[str, tuple[str, ...]], frozenset[str]]:
    """The tables of the layout, built from its rows.

    Returns the key each character is produced by, the shifted character each
    key also produces, the characters either side of each one and the codes of
    the keys the left hand types. Tab and the newlines are included as the keys
    that produce them so that a string containing them can simply be typed.
    """
    keys: dict[str, KeyInfo] = {
        ' ': KeyInfo(' ', 'Space', 32),
        '\t': KeyInfo('Tab', 'Tab', 9),
        '\n': KeyInfo('Enter', 'Enter', 13),
        '\r': KeyInfo('Enter', 'Enter', 13),
    }
    shifted: dict[str, str] = {}
    neighbours: dict[str, tuple[str, ...]] = {}
    left: set[str] = set()
    for plain, shift_row, codes, key_codes, left_count in zip(KEY_ROWS, SHIFTED_KEY_ROWS, ROW_CODES, ROW_KEY_CODES, ROW_LEFT_HAND, strict=True):
        for i, (ch, shift_ch, code, key_code) in enumerate(zip(plain, shift_row, codes, key_codes, strict=True)):
            keys[ch] = KeyInfo(ch, code, key_code)
            keys[shift_ch] = KeyInfo(shift_ch, code, key_code, shifted=True)
            shifted[ch] = shift_ch
            if i < left_count:
                left.add(code)
            for source in (plain, shift_row):
                neighbours[source[i]] = tuple(source[j] for j in (i - 1, i + 1) if 0 <= j < len(source))
    return keys, shifted, neighbours, frozenset(left)


PRINTABLE_KEYS, SHIFTED_KEYS, KEY_NEIGHBOURS, LEFT_HAND_CODES = build_key_tables()


def key_for_character(ch: str) -> KeyInfo | None:
    """The key press that produces the character ch, or None if no key does.

    A character from a script the layout knows nothing about, Cyrillic or
    Chinese for instance, has no key that produces it and has to be inserted as
    text instead, see :meth:`Keyboard.insert_text`. An accented Latin character
    is a middle case: it is not on a US layout either, but the key for the
    letter it decomposes to is the one a US International layout produces it
    with, as a dead key or AltGr sequence, so it is typed as that key carrying
    the accented character as its value, which is exactly what such a sequence
    looks like to a page. A character with no such decomposition, ``ø`` or
    ``ł``, is left to be inserted as text.
    """
    if (info := PRINTABLE_KEYS.get(ch)) is not None:
        return info
    decomposed = unicodedata.normalize('NFD', ch)
    if len(decomposed) > 1 and all(unicodedata.combining(c) for c in decomposed[1:]):
        if (info := PRINTABLE_KEYS.get(decomposed[0])) is not None:
            return info._replace(key=ch)
    return None


def key_info(name: str) -> KeyInfo:
    """The key event fields for a key named by the character it produces or by name.

    ``a``, ``A`` and ``!`` are the keys that produce them, the rest are named,
    case insensitively and with the usual aliases, so ``Enter``, ``esc``,
    ``ctrl`` and ``ArrowLeft`` are all understood, see :data:`NAMED_KEYS`.
    """
    if (info := PRINTABLE_KEYS.get(name)) is not None:  # a and A are different keys, so the case matters here
        return info
    canonical = KEY_ALIASES.get(name.lower(), name)
    if (info := PRINTABLE_KEYS.get(canonical)) is not None:
        return info
    if (info := NAMED_KEYS_BY_LOWER.get(canonical.lower())) is not None:
        return info
    if len(canonical) == 1 and (info := key_for_character(canonical)) is not None:
        return info
    raise ValueError(f'{name!r} is not a known key, expected a single character or one of: {", ".join(NAMED_KEYS)}')


def parse_chord(spec: str) -> tuple[tuple[str, ...], str]:
    """The modifiers to hold down and the key to press for a chord such as ``ctrl+shift+a``.

    A single character is always the key itself, so ``+`` is the plus key
    rather than a chord with nothing in it, and a chord can end with that key:
    ``shift++``.
    """
    if not spec:
        raise ValueError('An empty string is not a key')
    if len(spec) == 1:
        return (), spec
    segments = spec.split('+')
    if segments[-1] == '':  # the last plus was the key itself rather than a separator
        segments = segments[:-1]
        if segments and segments[-1] == '':
            segments = segments[:-1]
        segments.append('+')
    *modifier_names, key = segments
    modifiers = []
    for modifier in modifier_names:
        info = key_info(modifier)
        if info.key not in MODIFIER_KEY_NAMES:
            raise ValueError(f'{modifier!r} is not a modifier key, expected one of: {", ".join(MODIFIER_KEY_NAMES)}')
        if info.key not in modifiers:
            modifiers.append(info.key)
    key_info(key)  # fail now rather than with the modifiers already held down
    return tuple(modifiers), key


def graphemes(text: str) -> list[str]:
    """text split into the units a single keystroke produces.

    A combining mark, a variation selector and a zero width joiner all belong
    to the character before them, so they are kept with it rather than being
    typed on their own. The text is not normalized, so joining the result gives
    back exactly what was passed in.
    """
    ans: list[str] = []
    for ch in text:
        if ans and (unicodedata.combining(ch) or ch in ATTACHING_CHARS or ans[-1].endswith('\u200d')):
            ans[-1] += ch
        else:
            ans.append(ch)
    return ans


def key_hand(ch: str) -> str:
    """Which hand types the character ch: ``left``, ``right`` or neither."""
    info = key_for_character(ch)
    if info is None or info.code == 'Space':  # the space bar is hit by whichever thumb is idle
        return ''
    return 'left' if info.code in LEFT_HAND_CODES else 'right'


def is_awkward_key(ch: str) -> bool:
    """Whether ch is one of the keys a hand is less practised at reaching for."""
    return not ch.isalpha() and ch != ' '


def typing_interval(previous: str, current: str, median: float, rng: random.Random) -> float:
    """The seconds between pressing the key for previous and the key for current.

    Keystroke gaps are spread out around a median rather than being regular,
    with the same tail as real typing, and what is being typed moves that
    median about: a hand alternating between its two halves is quicker than one
    doubling back on itself, a capital costs the reach for shift, anything that
    is not a letter is less practised, and the gap between two words is
    sometimes a pause for thought rather than a keystroke at all.
    """
    factor = 1.0
    info = key_for_character(current)
    if info is not None and info.shifted:
        factor *= SHIFTED_KEY_PENALTY
    if is_awkward_key(current):
        factor *= AWKWARD_KEY_PENALTY
    if previous:
        if previous == current:
            factor *= SAME_KEY_PENALTY
        elif (hand := key_hand(previous)) and hand == key_hand(current):
            factor *= SAME_HAND_PENALTY
    ans = rng.lognormvariate(math.log(median * factor), KEY_INTERVAL_SPREAD)
    # A quick typist does not stop to think for as long as a slow one, so the
    # pauses are scaled with the speed rather than being the same however fast
    # the typing is, which would make a high speed mean much less than it says
    pause = median / (60.0 / (DEFAULT_TYPING_WPM * CHARS_PER_WORD))
    if previous == ' ' and rng.random() < WORD_PAUSE_PROBABILITY:
        ans += pause * rng.uniform(*WORD_PAUSE)
    elif previous in ('\n', '\r'):
        ans += pause * rng.uniform(*LINE_PAUSE)
    return min(max(ans, MIN_KEY_INTERVAL), MAX_KEY_INTERVAL)


class Keystroke(NamedTuple):
    """One keystroke of a planned burst of typing."""

    key: str  # the key to press, or '' to insert text without pressing anything
    text: str  # the characters this keystroke produces, empty for one that produces none
    delay: float  # seconds after the previous keystroke was pressed before this one is
    dwell: float  # seconds the key is held down for


def human_typing_plan(text: str, *, wpm: float = DEFAULT_TYPING_WPM, mistakes: float = 0.0, rng: random.Random | None = None) -> list[Keystroke]:
    """A human like way of typing text out, one keystroke at a time.

    A character no key produces becomes a keystroke with no key, to be inserted
    as text instead, see :func:`key_for_character`. Joining the text of every
    keystroke gives back exactly what was passed in, unless mistakes are asked
    for, in which case the extra characters are each taken back out again by
    the backspace that follows them.

    :param wpm: how fast to type, in words per minute. Text that is awkward to
        type comes out somewhat below this, the way it does for a hand.
    :param mistakes: the chance, per character, of pressing a neighbouring key
        by accident, noticing and correcting it with backspace
    :param rng: the source of randomness, pass a seeded one for reproducible typing
    """
    if wpm <= 0:
        raise ValueError(f'{wpm} is not a valid typing speed')
    if not 0.0 <= mistakes <= 1.0:
        raise ValueError(f'{mistakes} is not a valid chance of a mistake')
    r = MOTION_RNG if rng is None else rng
    median = 60.0 / (wpm * CHARS_PER_WORD)
    ans: list[Keystroke] = []
    previous = ''

    def keystroke(unit: str, delay: float) -> Keystroke:
        key = unit if len(unit) == 1 and key_for_character(unit) is not None else ''
        # A key held down longer than the gap to the next one would still be
        # down when that one is pressed, which is a roll rather than a keystroke
        return Keystroke(key, unit, delay, min(r.uniform(*KEY_DWELL), delay * 0.7))

    for unit in graphemes(text):
        delay = typing_interval(previous, unit, median, r)
        if mistakes and (nearby := KEY_NEIGHBOURS.get(unit)) and r.random() < mistakes:
            wrong = r.choice(nearby)
            ans.append(keystroke(wrong, delay))
            ans.append(Keystroke('Backspace', '', r.uniform(*MISTAKE_NOTICE), r.uniform(*KEY_DWELL)))
            delay = r.uniform(*MISTAKE_REPAIR)
        ans.append(keystroke(unit, delay))
        previous = unit
    return ans


async def sleep_until(when: float) -> None:
    """Wait until the monotonic clock reaches when, or return at once if it already has."""
    if (delay := when - time.monotonic()) > 0:
        await asyncio.sleep(delay)


class Keyboard:
    """Presses keys and types text, the way a hand does.

    Available as :attr:`Page.keyboard`. A key is named either by the character
    it produces, ``a``, ``A`` or ``!``, or by name, ``Enter`` or ``ctrl``, and a
    chord is written with pluses, ``ctrl+shift+a``, see :func:`key_info` and
    :func:`parse_chord`.

    Keystrokes go to whatever the page has focused, which is nothing at all
    until something is clicked or focused, so type into a field through
    :meth:`Element.type` or :meth:`Page.type` rather than through this.
    """

    def __init__(self, page: Page) -> None:
        self.page = page
        # The keys currently held down, in the order they were pressed
        self.pressed: list[str] = []

    def __repr__(self) -> str:
        return f'<Keyboard holding {", ".join(self.pressed) if self.pressed else "nothing"}>'

    @property
    def modifiers(self) -> tuple[str, ...]:
        """The modifier keys currently held down."""
        return tuple(key for key in self.pressed if key in MODIFIER_KEY_NAMES)

    async def dispatch(self, event_type: str, info: KeyInfo, *, repeat: bool = False) -> None:
        """Send a single key event to the page.

        Key events are dispatched from the same queue as mouse events and the
        browser answers one only once the page has seen it, so an event the
        page never sees is never answered and takes every later input event down
        with it, see :meth:`Mouse.dispatch` and :class:`InputWedged`.

        The text the key produces is not sent: the browser works it out from the
        key itself, which is what makes the page see the same composition and
        input events it would see from a real keyboard.
        """
        self.page.check_accepts_input()
        try:
            await self.page.send(
                'Page.dispatchKeyEvent',
                {'type': event_type, 'key': info.key, 'code': info.code, 'keyCode': info.key_code, 'location': info.location, 'repeat': repeat},
                timeout=INPUT_TIMEOUT,
            )
        except TimeoutExceeded as err:
            self.page.input_wedged = True
            raise InputWedged(
                f'The browser did not acknowledge a {event_type} for the {info.key} key within {INPUT_TIMEOUT} seconds,'
                f' so this page can no longer be given input. {await self.page.input_diagnostics()}'
            ) from err

    async def down(self, key: str, *, repeat: bool = False) -> None:
        """Press a key and hold it down.

        A key that is already held down is pressed again as an auto repeat, the
        way a keyboard with a key held down on it behaves.
        """
        info = key_info(key)
        self.page.check_accepts_input()
        already_held = info.key in self.pressed
        if not already_held:
            self.pressed.append(info.key)
        try:
            await self.dispatch('keydown', info, repeat=repeat or already_held)
        except BaseException:
            if not already_held:
                self.pressed.remove(info.key)
            raise

    async def up(self, key: str) -> None:
        """Release a key."""
        info = key_info(key)
        self.page.check_accepts_input()
        was_held = info.key in self.pressed
        if was_held:
            self.pressed.remove(info.key)
        try:
            await self.dispatch('keyup', info)
        except BaseException:
            if was_held:
                self.pressed.append(info.key)
            raise

    async def release(self, keys: Sequence[str], *, best_effort: bool = False) -> None:
        """Release keys, the last one pressed first.

        :param best_effort: report a key that could not be released rather than
            raising, for use while unwinding from an error that must not be
            replaced by the one releasing it runs into
        """
        for key in reversed(keys):
            try:
                await self.up(key)
            except Exception as err:
                if not best_effort:
                    raise
                debug(f'Failed to release the {key} key: {err}')

    async def tap(self, key: str, dwell: float | None = None) -> None:
        """Press a key and release it again, holding it down for a human like time."""
        await self.down(key)
        await asyncio.sleep(MOTION_RNG.uniform(*KEY_DWELL) if dwell is None else dwell)
        await self.up(key)

    async def press(self, key: str, *, delay: float | None = None, count: int = 1) -> None:
        """Press a key, or a chord such as ``ctrl+a``, count times.

        Any modifier of the chord that is not already held down is pressed
        before the key and released after it, and shift produces the shifted
        key, so ``shift+a`` types ``A``.

        :param delay: how long to hold the key down for, in seconds. The
            default, None, means a randomly chosen human like duration.
        :param count: press the key more than once, with a human like gap in between
        """
        modifiers, name = parse_chord(key)
        if count < 1:
            raise ValueError(f'{count} is not a valid number of key presses')
        self.page.check_accepts_input()
        if ('Shift' in modifiers or 'Shift' in self.pressed) and (twin := SHIFTED_KEYS.get(name)):
            name = twin
        held = [modifier for modifier in modifiers if modifier not in self.pressed]
        for modifier in held:
            await self.down(modifier)
            # A hand has the modifier down before it reaches the key it shifts
            await asyncio.sleep(MOTION_RNG.uniform(*SHIFT_LEAD))
        try:
            for i in range(count):
                if i:
                    await asyncio.sleep(MOTION_RNG.uniform(*KEY_REPEAT_INTERVAL))
                await self.tap(name, delay)
        except BaseException:
            await self.release(held, best_effort=True)
            raise
        if held:
            await asyncio.sleep(MOTION_RNG.uniform(*SHIFT_TRAIL))
            await self.release(held)

    async def commit_text(self, text: str) -> None:
        """Insert text into the focused element without checking that there is one."""
        self.page.check_accepts_input()
        try:
            await self.page.send('Page.insertText', {'text': text}, timeout=INPUT_TIMEOUT)
        except TimeoutExceeded as err:
            self.page.input_wedged = True
            raise InputWedged(
                f'The browser did not acknowledge the insertion of {text!r} within {INPUT_TIMEOUT} seconds,'
                f' so this page can no longer be given input. {await self.page.input_diagnostics()}'
            ) from err

    async def insert_text(self, text: str) -> None:
        """Insert text into the focused element in one go, without pressing any keys.

        The page sees composition and input events but no key events, which is
        how text committed by an input method arrives. Nothing at all happens if
        the page has no editable element focused, so that is checked first
        rather than leaving the text to vanish silently. The text goes to the
        main frame, so an element inside an iframe cannot be typed into.
        """
        if not text:
            return
        self.page.check_accepts_input()
        if not await self.page.call(FOCUSED_IS_EDITABLE_JS):
            raise Error('The page has no editable element focused, so text cannot be inserted into it')
        await self.commit_text(text)

    async def type(self, text: str, *, wpm: float | None = None, delay: float | None = None, human: bool | None = None, mistakes: float | None = None) -> None:
        """Type text into whatever the page has focused.

        Every character a US keyboard can produce is typed as a real key press,
        with the rhythm of a hand rather than of a clock, see
        :func:`human_typing_plan`. A character no key produces, from a non Latin
        script for instance, is inserted as text instead, see
        :meth:`insert_text`, so it reaches the page but without key events.

        Raises :class:`Error` if the page has nothing editable focused, since
        the keystrokes would otherwise be thrown away without a word.

        :param wpm: how fast to type, in words per minute. The default, None,
            means the browser's, see :class:`Browser`.
        :param delay: a fixed gap between keystrokes, in seconds, instead of a
            human like one
        :param human: vary the rhythm of the keystrokes the way a hand does.
            The default, None, means do so unless a fixed delay was given.
        :param mistakes: the chance, per character, of pressing a neighbouring
            key and correcting it with backspace. The default, None, means the
            browser's, see :class:`Browser`.
        """
        self.page.check_accepts_input()
        if not text:
            return
        if human is None:
            human = delay is None
        if human:
            browser = self.page.browser
            plan = human_typing_plan(text, wpm=browser.typing_wpm if wpm is None else wpm, mistakes=browser.typing_mistakes if mistakes is None else mistakes)
        else:
            gap = 0.0 if delay is None else delay
            plan = [Keystroke(unit if len(unit) == 1 and key_for_character(unit) is not None else '', unit, gap, 0.0) for unit in graphemes(text)]
        # Keystrokes sent to a page with nothing editable focused are simply
        # thrown away, so typing into one is a mistake worth reporting rather
        # than a burst of events that quietly does nothing. Use press() to send
        # keys somewhere other than a field, a keyboard shortcut for instance.
        if not await self.page.call(FOCUSED_IS_EDITABLE_JS):
            raise Error(f'The page has no editable element focused, so {text!r} cannot be typed into it')
        # Keystrokes are due at times measured from the start of the burst, so
        # that the round trip each of them costs comes out of the gap to the
        # next one instead of being added to it
        due = time.monotonic()
        shifted = False  # whether shift is being held down for a run of shifted keys
        try:
            for keystroke in plan:
                due += keystroke.delay
                if not keystroke.key:
                    await sleep_until(due)
                    await self.commit_text(keystroke.text)
                    continue
                needs_shift = key_info(keystroke.key).shifted
                if needs_shift and not shifted:
                    await sleep_until(due - MOTION_RNG.uniform(*SHIFT_LEAD))
                    await self.down('Shift')
                    shifted = True
                elif shifted and not needs_shift:
                    # Shift is held down for a whole run of capitals rather than
                    # being pressed again for each one of them
                    await sleep_until(due - MOTION_RNG.uniform(*SHIFT_TRAIL))
                    await self.up('Shift')
                    shifted = False
                await sleep_until(due)
                await self.down(keystroke.key)
                await asyncio.sleep(keystroke.dwell)
                await self.up(keystroke.key)
        except BaseException:
            if shifted:
                await self.release(('Shift',), best_effort=True)
            raise
        if shifted:
            await asyncio.sleep(MOTION_RNG.uniform(*SHIFT_TRAIL))
            await self.up('Shift')


# }}}


class Resource(NamedTuple):
    """The bytes of something the page loaded, such as an image."""

    url: str
    content_type: str
    data: bytes


class Element:
    """A handle to a DOM node in a page."""

    def __init__(self, page: Page, object_id: str) -> None:
        self.page, self.object_id = page, object_id
        self.disposed = False

    def __repr__(self) -> str:
        return f'<Element {self.object_id}{" (disposed)" if self.disposed else ""}>'

    def check_alive(self) -> None:
        if self.disposed:
            raise Error('This element handle has been disposed')

    async def call(self, function_declaration: str, *args: Any, by_value: bool = True) -> Any:  # noqa: ANN401
        """Call a JavaScript function with this element as its first argument."""
        self.check_alive()
        return await self.page.call_with_handles(function_declaration, [{'objectId': self.object_id}, *[{'value': a} for a in args]], by_value=by_value)

    async def html(self) -> str:
        return await self.call('(node) => node.outerHTML')

    async def inner_html(self) -> str:
        return await self.call('(node) => node.innerHTML')

    async def text(self) -> str:
        return await self.call('(node) => node.textContent')

    async def attribute(self, name: str) -> str | None:
        return await self.call('(node, name) => node.getAttribute(name)', name)

    async def attributes(self) -> dict[str, str]:
        return await self.call('(node) => Object.fromEntries(Array.from(node.attributes).map((a) => [a.name, a.value]))')

    async def set_attribute(self, name: str, value: str) -> None:
        await self.call('(node, name, value) => node.setAttribute(name, value)', name, value)

    async def delete_attribute(self, name: str) -> None:
        await self.call('(node, name) => node.removeAttribute(name)', name)

    async def set_text(self, text: str) -> None:
        await self.call('(node, text) => { node.textContent = text; }', text)

    async def append_child(self, tag: str, attributes: Mapping[str, str] | None = None, text: str = '') -> None:
        await self.call(
            '''(node, tag, attributes, text) => {
                const child = node.ownerDocument.createElement(tag);
                for (const name of Object.keys(attributes)) child.setAttribute(name, attributes[name]);
                if (text) child.appendChild(node.ownerDocument.createTextNode(text));
                node.appendChild(child);
            }''',
            tag,
            dict(attributes or {}),
            text,
        )

    async def insert_html(self, html: str, position: str = 'beforeend') -> None:
        await self.call('(node, html, position) => node.insertAdjacentHTML(position, html)', html, position)

    async def remove(self) -> None:
        await self.call('(node) => node.remove()')
        await self.dispose()

    async def find(self, css_selector: str) -> Element | None:
        handle = await self.call('(node, selector) => node.querySelector(selector)', css_selector, by_value=False)
        return handle

    async def scroll_into_view(self) -> None:
        """Scroll this element into the viewport, if it is not already fully visible."""
        self.check_alive()
        await self.page.send('Page.scrollIntoViewIfNeeded', {'frameId': self.page.main_frame, 'objectId': self.object_id})

    async def clickable_point(self) -> tuple[float, float]:
        """The coordinates of a point on this element that a click will land on.

        The point is in CSS pixels measured from the top left corner of the
        viewport. Raises :class:`Error` if the element has no visible area
        inside the viewport, so scroll it into view first.
        """
        self.check_alive()
        result = await self.page.send('Page.getContentQuads', {'frameId': self.page.main_frame, 'objectId': self.object_id})
        width, height = await self.page.viewport()
        # An element can be laid out as several boxes, for instance a link
        # broken across two lines, any of which is as good to click on as the
        # bounding box of the lot, which might not even be over the element
        quads = [corners for quad in result.get('quads') or () if quad_area(corners := clamp_quad(quad, width, height)) > 1]
        if not quads:
            raise Error(f'{self} has no visible area inside the viewport that can be clicked')
        return point_to_aim_at(quads[0])

    async def point_to_click(self) -> tuple[float, float]:
        """Scroll this element into view and find a point on it to aim at.

        Retried a few times because an element that has only just been scrolled
        to, or that the page is animating, can move under the cursor.
        """
        for attempt in range(3):
            if attempt:
                await asyncio.sleep(0.05)
            await self.scroll_into_view()
            try:
                return await self.clickable_point()
            except Error:
                if attempt == 2:
                    raise
        raise AssertionError('unreachable')

    async def hover(self, *, human: bool | None = None, max_time: float | None = None, modifiers: Sequence[str] = ()) -> None:
        """Move the cursor onto this element, scrolling it into view first."""
        self.page.check_accepts_input()
        x, y = await self.point_to_click()
        await self.page.mouse.move(x, y, human=human, max_time=max_time, modifiers=modifiers)

    async def click(
        self,
        *,
        button: str = 'left',
        click_count: int = 1,
        delay: float | None = None,
        human: bool | None = None,
        max_time: float | None = None,
        modifiers: Sequence[str] = (),
    ) -> None:
        """Click this element, scrolling it into view first.

        The cursor travels to the element along a human like path and the
        button is held down for a human like length of time, see
        :meth:`Mouse.click` for what the parameters mean.
        """
        self.page.check_accepts_input()
        x, y = await self.point_to_click()
        await self.page.mouse.click(x, y, button=button, click_count=click_count, delay=delay, human=human, max_time=max_time, modifiers=modifiers)

    async def focus(self) -> None:
        """Give this element the keyboard focus, without using the mouse."""
        await self.call('(node) => { node.focus(); }')

    async def value(self) -> str:
        """The text this element holds: the value of a form field or the text of anything else."""
        return await self.call('(node) => node.value ?? node.textContent ?? ""')

    async def press(self, key: str, *, delay: float | None = None, count: int = 1) -> None:
        """Press a key, or a chord such as ``ctrl+a``, with this element focused.

        The element is focused rather than clicked, so the caret is left
        wherever typing into it put it, see :meth:`Keyboard.press`.
        """
        self.page.check_accepts_input()
        await self.focus()
        await self.page.keyboard.press(key, delay=delay, count=count)

    async def type(
        self,
        text: str,
        *,
        click: bool = True,
        wpm: float | None = None,
        delay: float | None = None,
        human: bool | None = None,
        mistakes: float | None = None,
        max_time: float | None = None,
    ) -> None:
        """Type text into this element, at the caret.

        The text is appended to whatever the element already holds, see
        :meth:`fill` to replace that instead.

        :param click: reach the element by clicking on it, the way a human
            does, rather than focusing it from JavaScript
        :param max_time: the longest the cursor may take to get there, see :meth:`Mouse.move`
        """
        self.page.check_accepts_input()
        if click:
            await self.click(max_time=max_time)
        else:
            await self.focus()
        await self.page.keyboard.type(text, wpm=wpm, delay=delay, human=human, mistakes=mistakes)

    async def fill(
        self,
        text: str,
        *,
        click: bool = True,
        wpm: float | None = None,
        delay: float | None = None,
        human: bool | None = None,
        mistakes: float | None = None,
        max_time: float | None = None,
    ) -> None:
        """Replace the contents of this element with text, typing it out.

        What is already there is selected with the platform's select all
        accelerator and deleted rather than being assigned from JavaScript, so
        that a page which watches for key and input events, as anything built
        on a JavaScript framework does, sees what it is expecting. Pass an empty
        string to only clear it.
        """
        self.page.check_accepts_input()
        if click:
            await self.click(max_time=max_time)
        else:
            await self.focus()
        keyboard = self.page.keyboard
        await keyboard.press(SELECT_ALL_CHORD)
        await keyboard.press('Backspace')
        await keyboard.type(text, wpm=wpm, delay=delay, human=human, mistakes=mistakes)

    async def dispose(self) -> None:
        if self.disposed:
            return
        self.disposed = True
        try:
            await self.page.connection.send(
                'Runtime.disposeObject', {'executionContextId': self.page.execution_context, 'objectId': self.object_id}, self.page.session_id
            )
        except Error, KeyError:
            pass  # the context is already gone, so is the object


class Page:
    """A single tab in the browser."""

    def __init__(self, browser: Browser, session_id: str, target_id: str, opener_id: str = '') -> None:
        self.browser, self.session_id, self.target_id, self.opener_id = browser, session_id, target_id, opener_id
        self.connection = browser.connection
        self.main_frame = ''
        self.url = 'about:blank'
        self.closed = False
        self.events = EventWaiter()
        self.ready = asyncio.Event()
        # frame id -> id of the execution context for the main JavaScript world
        self.contexts: dict[str, str] = {}
        self.lifecycle: dict[str, set[str]] = {}
        # request id -> url and url -> request id, for retrieving response bodies
        self.request_urls: dict[str, str] = {}
        self.requests_by_url: dict[str, str] = {}
        self.content_types: dict[str, str] = {}
        # The size of the viewport, cached since every cursor movement needs it
        self.viewport_size: tuple[float, float] | None = None
        # Whether the browser has stopped acknowledging input events for this page
        self.input_wedged = False
        self.mouse = Mouse(self)
        self.keyboard = Keyboard(self)

    def __repr__(self) -> str:
        return f'<Page {self.target_id} {self.url}{" (closed)" if self.closed else ""}>'

    # Event handling {{{

    def handle_event(self, method: str, params: dict[str, Any]) -> None:
        match method:
            case 'Page.ready':
                self.ready.set()
            case 'Page.frameAttached':
                if not params.get('parentFrameId'):
                    self.main_frame = params['frameId']
            case 'Page.frameDetached':
                self.contexts.pop(params['frameId'], None)
                self.lifecycle.pop(params['frameId'], None)
            case 'Page.navigationCommitted':
                frame_id = params['frameId']
                self.lifecycle[frame_id] = set()
                if frame_id == self.main_frame:
                    self.url = params.get('url') or self.url
                    # A new document can have scrollbars where the old one had none
                    self.viewport_size = None
            case 'Page.eventFired':
                self.lifecycle.setdefault(params['frameId'], set()).add(params['name'])
            case 'Page.sameDocumentNavigation':
                if params['frameId'] == self.main_frame:
                    self.url = params.get('url') or self.url
            case 'Page.dialogOpened':
                # Nothing is driving the browser interactively, so a dialog left
                # open would block the page forever
                self.connection.send_nowait('Page.handleDialog', {'dialogId': params['dialogId'], 'accept': True}, self.session_id)
            case 'Page.crashed':
                self.events.abort(BrowserClosedError('The page crashed'))
            case 'Runtime.executionContextCreated':
                aux = params.get('auxData') or {}
                frame_id = aux.get('frameId')
                if frame_id and not aux.get('name'):  # the main world, not an isolated one
                    self.contexts[frame_id] = params['executionContextId']
            case 'Runtime.executionContextDestroyed':
                for frame_id, context in tuple(self.contexts.items()):
                    if context == params['executionContextId']:
                        del self.contexts[frame_id]
            case 'Runtime.executionContextsCleared':
                self.contexts.clear()
            case 'Network.requestWillBeSent':
                self.track_request(params['requestId'], params['url'])
            case 'Network.responseReceived':
                for header in params.get('headers') or ():
                    if header.get('name', '').lower() == 'content-type':
                        self.content_types[params['requestId']] = header.get('value') or ''
        self.events.dispatch(method, params)

    def track_request(self, request_id: str, url: str) -> None:
        if len(self.request_urls) >= MAX_TRACKED_REQUESTS:
            oldest = next(iter(self.request_urls))
            old_url = self.request_urls.pop(oldest)
            self.content_types.pop(oldest, None)
            if self.requests_by_url.get(old_url) == oldest:
                del self.requests_by_url[old_url]
        self.request_urls[request_id] = url
        self.requests_by_url[url] = request_id

    def detached(self) -> None:
        self.closed = True
        self.events.abort(BrowserClosedError('The page was closed'))
        self.ready.set()

    # }}}

    async def send(self, method: str, params: Mapping[str, Any] | None = None, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        if self.closed:
            raise BrowserClosedError('This page has been closed')
        return await self.connection.send(method, params, self.session_id, timeout)

    async def viewport(self) -> tuple[float, float]:
        """The size of the visible part of the page, in CSS pixels.

        Cached, and discarded when the page navigates, because every cursor
        movement needs it, see :func:`clamp_to_viewport`.
        """
        if self.viewport_size is None:
            width, height = await self.evaluate('[window.innerWidth, window.innerHeight]')
            self.viewport_size = float(width), float(height)
        return self.viewport_size

    def check_accepts_input(self) -> None:
        """Raise :class:`InputWedged` if the browser has stopped accepting input for this page.

        Called at the start of every input method, not just before each event
        is sent, so that a wedged page is reported without first walking a
        cursor path or asking the browser anything, neither of which it is
        going to answer.
        """
        if self.input_wedged:
            raise InputWedged(f'{self} stopped acknowledging input events, no more input can be delivered to it')

    async def input_diagnostics(self) -> str:
        """What can be discovered about a browser that stopped acknowledging input.

        Called only once an input event has already been given up on, so that
        the failure says which half of the browser is stuck rather than just
        that something is. Answers no question for longer than
        :data:`INPUT_DIAGNOSTIC_TIMEOUT` and never raises.
        """
        notes = []
        try:
            await self.evaluate('1', timeout=INPUT_DIAGNOSTIC_TIMEOUT)
        except Exception as err:
            notes.append(f'The page no longer runs JavaScript either ({err.__class__.__name__}), so the whole browser is stuck.')
        else:
            notes.append('The page still runs JavaScript, so only its input queue is stuck.')
        # A movement onto the pixel the cursor is already on is discarded by
        # the browser without being dispatched, so probe with a different one
        probe = (1.0, 1.0) if (self.mouse.x, self.mouse.y) != (1.0, 1.0) else (2.0, 2.0)
        try:
            await self.send(
                'Page.dispatchMouseEvent',
                {'type': 'mousemove', 'x': probe[0], 'y': probe[1], 'button': 0, 'buttons': 0, 'modifiers': 0, 'clickCount': 0},
                timeout=INPUT_DIAGNOSTIC_TIMEOUT,
            )
        except Exception as err:
            notes.append(f'A further mouse event was not acknowledged either ({err.__class__.__name__}), the input queue is stuck for good.')
        else:
            notes.append('A further mouse event was acknowledged, so only the one event was lost.')
        if (process := self.browser.process) is not None and (log := process.log_tail(10).strip()):
            notes.append(f'The tail of the browser log:\n{log}')
        return ' '.join(notes)

    async def wait_until_ready(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        try:
            async with asyncio.timeout(timeout):
                await self.ready.wait()
        except TimeoutError:
            raise TimeoutExceeded(f'The page was not ready within {timeout} seconds')
        if not self.main_frame:
            raise Error('The page became ready without reporting a main frame')

    # Evaluating JavaScript {{{

    @property
    def execution_context(self) -> str:
        try:
            return self.contexts[self.main_frame]
        except KeyError:
            raise Error('The page has no JavaScript execution context, it is probably still navigating')

    async def wait_for_execution_context(self, timeout: float = DEFAULT_TIMEOUT) -> str:
        """The execution context of the main frame, waiting for it to be created
        if the page has only just navigated."""
        if self.main_frame in self.contexts:
            return self.contexts[self.main_frame]

        def is_our_context(method: str, params: Mapping[str, Any]) -> bool:
            return method == 'Runtime.executionContextCreated' and (params.get('auxData') or {}).get('frameId') == self.main_frame

        await wait_for(self.events.expect(is_our_context), timeout, 'a JavaScript execution context')
        return self.execution_context

    def unwrap(self, result: Mapping[str, Any], by_value: bool) -> Any:  # noqa: ANN401
        if (details := result.get('exceptionDetails')) is not None:
            raise JavaScriptError(details.get('text') or details.get('stack') or repr(details.get('value')))
        obj = result.get('result') or {}
        if not by_value:
            if obj.get('objectId'):
                return Element(self, obj['objectId'])
            return obj.get('value')
        if (unserializable := obj.get('unserializableValue')) is not None:
            return {'Infinity': float('inf'), '-Infinity': float('-inf'), '-0': -0.0, 'NaN': float('nan')}[unserializable]
        return obj.get('value')

    async def evaluate(self, expression: str, *, by_value: bool = True, timeout: float = DEFAULT_TIMEOUT) -> Any:  # noqa: ANN401
        """Evaluate a JavaScript expression in the page and return its value.

        Pass by_value=False to get an :class:`Element` handle back for
        expressions that evaluate to a DOM node.

        If the expression evaluates to a promise, its resolved value is
        returned, but note that the browser can only see promises created by
        JavaScript in the page, not the ones handed out by DOM APIs. So
        ``fetch(url).then(...)`` never completes, while
        ``(async () => (await fetch(url)).status)()`` works. When in doubt, wrap
        the expression in an async function.
        """
        context = await self.wait_for_execution_context(timeout)
        result = await self.send('Runtime.evaluate', {'executionContextId': context, 'expression': expression, 'returnByValue': by_value}, timeout)
        return self.unwrap(result, by_value)

    async def call(self, function_declaration: str, *args: Any, by_value: bool = True, timeout: float = DEFAULT_TIMEOUT) -> Any:  # noqa: ANN401
        """Call a JavaScript function in the page, passing args to it.

        See :meth:`evaluate` for the caveat about functions that return a
        promise produced by a DOM API rather than by JavaScript.
        """
        return await self.call_with_handles(function_declaration, [{'value': a} for a in args], by_value=by_value, timeout=timeout)

    async def call_with_handles(
        self, function_declaration: str, args: Sequence[Mapping[str, Any]], *, by_value: bool = True, timeout: float = DEFAULT_TIMEOUT
    ) -> Any:  # noqa: ANN401
        context = await self.wait_for_execution_context(timeout)
        result = await self.send(
            'Runtime.callFunction',
            {'executionContextId': context, 'functionDeclaration': function_declaration, 'args': list(args), 'returnByValue': by_value},
            timeout,
        )
        return self.unwrap(result, by_value)

    # }}}

    # Navigation {{{

    def navigation_finished(self) -> asyncio.Future[Event]:
        return self.events.expect(
            lambda method, params: method in ('Page.navigationCommitted', 'Page.navigationAborted') and params.get('frameId') == self.main_frame
        )

    async def open(self, url: str, *, wait: str = 'load', timeout: float = DEFAULT_TIMEOUT, referer: str = '') -> None:
        """Load url in this tab.

        :param wait: how much of the load to wait for before returning. One of
            ``load`` (wait for all sub-resources), ``domcontentloaded`` (wait
            only for the DOM), ``commit`` (wait only for the server's response
            to start arriving) or ``none``.
        """
        await self.wait_until_ready(timeout)
        deadline = time.monotonic() + timeout
        navigate_params: dict[str, Any] = {'frameId': self.main_frame, 'url': url}
        if referer:
            navigate_params['referer'] = referer
        # The waiter has to be in place before the navigation starts, otherwise a
        # fast load can commit before we get around to listening for it
        finished = self.navigation_finished()
        try:
            result = await self.send('Page.navigate', navigate_params, timeout)
            navigation_id = result.get('navigationId')
            if navigation_id is None:  # a fragment only navigation, nothing loads
                self.url = url
                return
            if wait == 'none':
                return
            while True:
                event = await wait_for(finished, max(deadline - time.monotonic(), 0), f'the navigation to {url}')
                if event.params.get('navigationId') == navigation_id:
                    break
                finished = self.navigation_finished()
        finally:
            finished.cancel()
        if event.method == 'Page.navigationAborted':
            raise Error(f'Navigation to {url} was aborted: {event.params.get("errorText")}')
        if wait == 'commit':
            return
        await self.wait_for_load(wait, max(deadline - time.monotonic(), 0))

    async def wait_for_load(self, state: str = 'load', timeout: float = DEFAULT_TIMEOUT) -> None:
        """Wait until the main frame has fired the load or DOMContentLoaded event.

        The record of which events have fired is reset every time the frame
        navigates, so this waits for the *current* document.
        """
        name = {'load': 'load', 'domcontentloaded': 'DOMContentLoaded'}.get(state.lower())
        if name is None:
            raise ValueError(f'{state} is not a valid state to wait for, use load or domcontentloaded')
        if name in self.lifecycle.get(self.main_frame, ()):
            return
        await wait_for(
            self.events.expect(lambda method, params: method == 'Page.eventFired' and params['frameId'] == self.main_frame and params['name'] == name),
            timeout,
            f'the {name} event',
        )

    async def reload(self, *, wait: str = 'load', timeout: float = DEFAULT_TIMEOUT) -> None:
        loaded = self.events.expect(lambda method, params: method == 'Page.navigationCommitted' and params['frameId'] == self.main_frame)
        await self.send('Page.reload', {}, timeout)
        await wait_for(loaded, timeout, 'the page to reload')
        if wait != 'none':
            await self.wait_for_load(wait, timeout)

    async def go_back(self, *, wait: str = 'load', timeout: float = DEFAULT_TIMEOUT) -> bool:
        return await self.traverse_history('Page.goBack', wait, timeout)

    async def go_forward(self, *, wait: str = 'load', timeout: float = DEFAULT_TIMEOUT) -> bool:
        return await self.traverse_history('Page.goForward', wait, timeout)

    async def traverse_history(self, method: str, wait: str, timeout: float) -> bool:
        committed = self.events.expect(lambda m, params: m == 'Page.navigationCommitted' and params['frameId'] == self.main_frame)
        result = await self.send(method, {'frameId': self.main_frame}, timeout)
        if not result.get('success'):
            committed.cancel()
            return False
        await wait_for(committed, timeout, 'the history navigation to commit')
        if wait != 'none':
            await self.wait_for_load(wait, timeout)
        return True

    # }}}

    # Inspecting and modifying the DOM {{{

    async def html(self) -> str:
        """The current serialized HTML of the page, including any changes made to the DOM."""
        return await self.evaluate('document.documentElement.outerHTML')

    async def title(self) -> str:
        return await self.evaluate('document.title')

    async def current_url(self) -> str:
        return await self.evaluate('location.href')

    async def wait_for_selector(self, css_selector: str, *, timeout: float = DEFAULT_TIMEOUT, visible: bool = False) -> Element:
        """Wait for an element matching css_selector to appear and return it.

        A mutation observer is used, so this returns as soon as the element
        appears rather than polling. Pass visible=True to additionally require
        that the element has a non zero size and is not hidden.
        """
        handle = await self.call(WAIT_FOR_SELECTOR_JS, css_selector, int(timeout * 1000), visible, by_value=False, timeout=timeout + 5)
        if not isinstance(handle, Element):
            raise TimeoutExceeded(f'No element matching {css_selector!r} appeared within {timeout} seconds')
        return handle

    async def find(self, css_selector: str) -> Element | None:
        """The first element matching css_selector, or None."""
        handle = await self.call('(selector) => document.querySelector(selector)', css_selector, by_value=False)
        return handle if isinstance(handle, Element) else None

    async def find_all(self, css_selector: str) -> list[Element]:
        """Every element matching css_selector."""
        count = await self.call('(selector) => document.querySelectorAll(selector).length', css_selector)
        ans = []
        for i in range(int(count)):
            handle = await self.call('(selector, i) => document.querySelectorAll(selector)[i]', css_selector, i, by_value=False)
            if isinstance(handle, Element):
                ans.append(handle)
        return ans

    async def remove(self, css_selector: str) -> int:
        """Remove every element matching css_selector, returning how many were removed."""
        return int(await self.call(REMOVE_JS, css_selector))

    async def set_attribute(self, css_selector: str, name: str, value: str) -> int:
        """Set an attribute on every element matching css_selector."""
        return int(await self.call(SET_ATTRIBUTE_JS, css_selector, name, value))

    async def delete_attribute(self, css_selector: str, name: str) -> int:
        """Remove an attribute from every element matching css_selector."""
        return int(await self.call(DELETE_ATTRIBUTE_JS, css_selector, name))

    async def append_child(self, css_selector: str, tag: str, attributes: Mapping[str, str] | None = None, text: str = '') -> int:
        """Append a newly created element to every element matching css_selector."""
        return int(await self.call(APPEND_CHILD_JS, css_selector, tag, dict(attributes or {}), text))

    async def insert_html(self, css_selector: str, html: str, position: str = 'beforeend') -> int:
        """Insert a fragment of HTML relative to every element matching css_selector.

        :param position: one of ``beforebegin``, ``afterbegin``, ``beforeend`` or ``afterend``
        """
        if position not in ('beforebegin', 'afterbegin', 'beforeend', 'afterend'):
            raise ValueError(f'{position} is not a valid insert position')
        return int(await self.call(INSERT_HTML_JS, css_selector, html, position))

    async def set_text(self, css_selector: str, text: str) -> int:
        """Replace the contents of every element matching css_selector with text."""
        return int(await self.call(SET_TEXT_JS, css_selector, text))

    # }}}

    # Mouse input {{{

    async def hover(
        self, css_selector: str, *, timeout: float = DEFAULT_TIMEOUT, human: bool | None = None, max_time: float | None = None, modifiers: Sequence[str] = ()
    ) -> None:
        """Move the cursor onto the first visible element matching css_selector.

        Waits for the element to appear and become visible, then scrolls it
        into view, see :meth:`Element.hover`.
        """
        element = await self.wait_for_selector(css_selector, timeout=timeout, visible=True)
        try:
            await element.hover(human=human, max_time=max_time, modifiers=modifiers)
        finally:
            await element.dispose()

    async def click(
        self,
        css_selector: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        button: str = 'left',
        click_count: int = 1,
        delay: float | None = None,
        human: bool | None = None,
        max_time: float | None = None,
        modifiers: Sequence[str] = (),
    ) -> None:
        """Click the first visible element matching css_selector.

        Waits for the element to appear and become visible, then scrolls it
        into view and clicks it the way a human would, see
        :meth:`Element.click` and :meth:`Mouse.click`.
        """
        element = await self.wait_for_selector(css_selector, timeout=timeout, visible=True)
        try:
            await element.click(button=button, click_count=click_count, delay=delay, human=human, max_time=max_time, modifiers=modifiers)
        finally:
            await element.dispose()

    # }}}

    # Keyboard input {{{

    async def type(
        self,
        css_selector: str,
        text: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        click: bool = True,
        wpm: float | None = None,
        delay: float | None = None,
        human: bool | None = None,
        mistakes: float | None = None,
        max_time: float | None = None,
    ) -> None:
        """Type text into the first visible element matching css_selector.

        Waits for the element to appear and become visible, then clicks on it
        and types the way a human would, see :meth:`Element.type` and
        :meth:`Keyboard.type`.
        """
        element = await self.wait_for_selector(css_selector, timeout=timeout, visible=True)
        try:
            await element.type(text, click=click, wpm=wpm, delay=delay, human=human, mistakes=mistakes, max_time=max_time)
        finally:
            await element.dispose()

    async def fill(
        self,
        css_selector: str,
        text: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        click: bool = True,
        wpm: float | None = None,
        delay: float | None = None,
        human: bool | None = None,
        mistakes: float | None = None,
        max_time: float | None = None,
    ) -> None:
        """Replace the contents of the first visible element matching css_selector, typing text out.

        See :meth:`Element.fill`.
        """
        element = await self.wait_for_selector(css_selector, timeout=timeout, visible=True)
        try:
            await element.fill(text, click=click, wpm=wpm, delay=delay, human=human, mistakes=mistakes, max_time=max_time)
        finally:
            await element.dispose()

    async def press(self, css_selector: str, key: str, *, timeout: float = DEFAULT_TIMEOUT, delay: float | None = None, count: int = 1) -> None:
        """Press a key, or a chord such as ``ctrl+a``, with the first visible
        element matching css_selector focused, see :meth:`Keyboard.press`."""
        element = await self.wait_for_selector(css_selector, timeout=timeout, visible=True)
        try:
            await element.press(key, delay=delay, count=count)
        finally:
            await element.dispose()

    # }}}

    # Resources {{{

    def resource_urls(self, pattern: str = '') -> tuple[str, ...]:
        """The URLs of the resources this page has requested, optionally
        restricted to those matching the regular expression pattern."""
        urls = tuple(self.requests_by_url)
        if pattern:
            matches = re.compile(pattern).search
            urls = tuple(x for x in urls if matches(x))
        return urls

    async def get_resource(self, url: str, *, timeout: float = DEFAULT_TIMEOUT) -> Resource:
        """The bytes of a resource, such as an image, that this page loaded.

        The body is taken from the browser's own record of the response, so the
        resource is not fetched a second time. If the browser has already
        discarded it, it is re-fetched from within the page, which means it is
        fetched with the page's cookies and referrer.
        """
        request_id = self.requests_by_url.get(url)
        if request_id is not None:
            try:
                result = await self.send('Network.getResponseBody', {'requestId': request_id}, timeout)
            except ProtocolError:
                result = {}
            if result.get('base64body') is not None and not result.get('evicted'):
                return Resource(url, self.content_types.get(request_id, ''), base64.b64decode(result['base64body']))
        result = await self.call(FETCH_JS, url, timeout=timeout)
        if not isinstance(result, dict):
            raise Error(f'Failed to fetch {url} from the page')
        if not (200 <= int(result.get('status') or 0) < 300):
            raise Error(f'Fetching {url} from the page failed with HTTP status {result.get("status")}')
        return Resource(url, result.get('contentType') or '', base64.b64decode(result.get('base64') or ''))

    async def screenshot(self, *, mime_type: str = 'image/png', quality: int = 0, full_page: bool = False) -> bytes:
        """A screenshot of the page as image data."""
        if full_page:
            width, height = await self.evaluate(
                '[Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0),'
                ' Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0)]'
            )
        else:
            width, height = await self.evaluate('[window.innerWidth, window.innerHeight]')
        params: dict[str, Any] = {'mimeType': mime_type, 'clip': {'x': 0, 'y': 0, 'width': width, 'height': height}}
        if quality:
            params['quality'] = quality
        result = await self.send('Page.screenshot', params)
        return base64.b64decode(result['data'])

    # }}}

    async def close(self) -> None:
        """Close this tab."""
        if self.closed:
            return
        try:
            await self.send('Page.close', {'runBeforeUnload': False}, timeout=CLOSE_TIMEOUT)
        except Error, ProtocolError:
            pass
        self.detached()


class Browser:
    """A running Camoufox browser process.

    Use it as an async context manager::

        async with Browser(headless=True) as browser:
            await browser.page.open('https://example.com')

    :param headless: run without a visible window
    :param target_os: the operating system to impersonate, defaults to the one we are running on
    :param locale: the locale(s) to report to pages
    :param fonts: the font families to report, defaults to a random subset of the bundled ones
    :param window: a fixed (width, height) for the window instead of a random one
    :param humanize: move the cursor along a human like path rather than
        teleporting it, optionally giving the longest such a movement may take
        in seconds. This is what :class:`Mouse` does anyway, so the only thing
        this changes is that duration. The browser is never asked to generate
        the paths itself, see :func:`generate_config`.
    :param typing_wpm: how fast to type, in words per minute, see
        :meth:`Keyboard.type`. The default, 0, means :data:`DEFAULT_TYPING_WPM`.
    :param typing_mistakes: the chance, per character typed, of pressing a
        neighbouring key by accident and correcting it with backspace. Off by
        default, since a field that reformats or validates what is typed into it
        as it goes can react badly to a character that is only there for a moment.
    :param block_images: do not load images at all
    :param block_webrtc: disable WebRTC entirely
    :param enable_cache: keep previously loaded pages and requests around, using more memory
    :param proxy: a proxy to route all traffic through, as a dict with the keys
        ``type`` (one of http, https, socks, socks4), ``host``, ``port`` and
        optionally ``username``, ``password`` and ``bypass``
    :param config: camoufox config properties that override the generated ones
    :param firefox_user_prefs: Firefox preferences to set
    :param allow_prerelease: use pre-release builds of the browser
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        target_os: str = '',
        locale: str | Sequence[str] = '',
        fonts: Sequence[str] | None = None,
        window: tuple[int, int] | None = None,
        humanize: bool | float = False,
        typing_wpm: float = 0.0,
        typing_mistakes: float = 0.0,
        block_images: bool = False,
        block_webrtc: bool = False,
        enable_cache: bool = True,
        proxy: Mapping[str, Any] | None = None,
        config: Mapping[str, Any] | None = None,
        firefox_user_prefs: Mapping[str, Any] | None = None,
        allow_prerelease: bool = False,
        launch_timeout: float = LAUNCH_TIMEOUT,
        keep_log: bool = False,
    ) -> None:
        self.headless, self.target_os = headless, check_valid_os(target_os or current_os())
        self.locale, self.fonts, self.window = locale, fonts, window
        # The browser's own cursor humanizing is never used, so all this says
        # is how long a movement made by Mouse may take
        self.max_move_time = float(humanize) if isinstance(humanize, (int, float)) and not isinstance(humanize, bool) else MAX_MOVE_TIME
        if typing_wpm < 0 or not 0.0 <= typing_mistakes <= 1.0:
            raise ValueError(f'{typing_wpm} words per minute with a {typing_mistakes} chance of a mistake is not a valid way to type')
        self.typing_wpm = typing_wpm or DEFAULT_TYPING_WPM
        self.typing_mistakes = typing_mistakes
        self.block_images, self.block_webrtc, self.enable_cache = block_images, block_webrtc, enable_cache
        self.proxy, self.extra_config, self.allow_prerelease = proxy, config, allow_prerelease
        self.extra_user_prefs = firefox_user_prefs
        self.launch_timeout, self.keep_log = launch_timeout, keep_log
        self.connection = Connection()
        self.process: Process | None = None
        self.profile_dir = ''
        self.browser_context_id = ''
        self.config: dict[str, Any] = {}
        self.version = ''
        self.pages: dict[str, Page] = {}
        self.pending_pages: dict[str, asyncio.Future[Page]] = {}
        self.new_pages: list[Page] = []
        self.closed = False

    def __repr__(self) -> str:
        return f'<Camoufox Browser {self.version}{" (closed)" if self.closed else ""}>'

    async def __aenter__(self) -> Browser:
        await self.launch()
        return self

    async def __aexit__(self, *args: Any) -> None:  # noqa: ANN401
        await self.close()

    # Launching {{{

    def user_prefs(self) -> dict[str, Any]:
        prefs = dict(BASE_USER_PREFS)
        if self.enable_cache:
            prefs.update(CACHE_USER_PREFS)
        if self.block_images:
            prefs['permissions.default.image'] = 2
        if self.block_webrtc:
            prefs['media.peerconnection.enabled'] = False
        if self.extra_user_prefs:
            prefs.update(self.extra_user_prefs)
        return prefs

    def build_command_line(self, binary: str) -> list[str]:
        argv = [binary, '-no-remote', '-profile', self.profile_dir, '-juggler-pipe']
        if self.headless:
            argv.append('-headless')
        # -silent stops the browser opening a window of its own, every page is
        # created explicitly through the protocol instead
        argv.append('-silent')
        return argv

    def build_environment(self, resource_dir: str) -> dict[str, str]:
        env = dict(os.environ)
        env.update(config_environment(self.config))
        if not iswindows and not ismacos:
            # Only Linux needs to be told where the bundled fonts are, on the
            # other platforms camoufox restricts the font list itself
            env['FONTCONFIG_FILE'] = fontconfig_path(resource_dir, self.version, self.target_os)
        env.pop('MOZ_CRASHREPORTER', None)
        env['MOZ_CRASHREPORTER_DISABLE'] = '1'
        return env

    async def launch(self) -> None:
        """Start the browser process and open its first, empty, tab."""
        if self.process is not None:
            raise Error('This browser has already been launched')
        loop = asyncio.get_running_loop()
        install = await loop.run_in_executor(None, lambda: camoufox_installer(allow_prerelease=self.allow_prerelease))
        binary, self.version = install.path, install.version
        resource_dir = camoufox_resource_dir(binary)
        self.config = await loop.run_in_executor(
            None,
            lambda: generate_config(
                resource_dir,
                self.version,
                target_os=self.target_os,
                window=self.window,
                fonts=self.fonts,
                locale=self.locale,
                extra=self.extra_config,
            ),
        )
        self.profile_dir = tempfile.mkdtemp(prefix='camoufox-profile-')
        log_path = os.path.join(self.profile_dir, 'browser-log.txt')
        env = self.build_environment(resource_dir)
        self.connection.root_handler = self.handle_event
        self.connection.on_closed = self.connection_closed
        try:
            self.process = await loop.run_in_executor(None, lambda: spawn(self.build_command_line(binary), env, log_path))
            self.connection.start(self.process, loop)
            await self.enable(loop)
        except BaseException:
            await self.close()
            raise

    async def enable(self, loop: asyncio.AbstractEventLoop) -> None:
        prefs = [{'name': name, 'value': value} for name, value in self.user_prefs().items()]
        try:
            await self.connection.send('Browser.enable', {'attachToDefaultContext': False, 'userPrefs': prefs}, timeout=self.launch_timeout)
        except (TimeoutExceeded, BrowserClosedError) as err:
            assert self.process is not None
            raise Error(f'The camoufox browser failed to start: {err}\nBrowser log:\n{self.process.log_tail()}') from err
        result = await self.connection.send('Browser.createBrowserContext', {'removeOnDetach': True})
        self.browser_context_id = result['browserContextId']
        if self.proxy:
            await self.set_proxy(self.proxy)
        await self.new_page()

    def handle_event(self, method: str, params: dict[str, Any]) -> None:
        match method:
            case 'Browser.attachedToTarget':
                info = params['targetInfo']
                page = Page(self, params['sessionId'], info['targetId'], info.get('openerId') or '')
                self.pages[info['targetId']] = page
                self.connection.event_handlers[page.session_id] = page.handle_event
                if (future := self.pending_pages.pop(info['targetId'], None)) is not None and not future.done():
                    future.set_result(page)
                else:
                    self.new_pages.append(page)
            case 'Browser.detachedFromTarget':
                page = self.pages.pop(params['targetId'], None)
                if page is not None:
                    self.connection.event_handlers.pop(page.session_id, None)
                    page.detached()

    def connection_closed(self) -> None:
        self.closed = True
        error = BrowserClosedError('The browser process exited')
        for page in self.pages.values():
            page.detached()
        for future in self.pending_pages.values():
            if not future.done():
                future.set_exception(error)
        self.pending_pages.clear()

    # }}}

    @property
    def page(self) -> Page:
        """The first open tab. There is always at least one until the browser is closed."""
        for page in self.pages.values():
            if not page.closed:
                return page
        raise Error('The browser has no open pages')

    @property
    def open_pages(self) -> tuple[Page, ...]:
        return tuple(page for page in self.pages.values() if not page.closed)

    async def new_page(self, url: str = '', *, wait: str = 'load', timeout: float = DEFAULT_TIMEOUT) -> Page:
        """Open a new tab, optionally loading url in it.

        Note that the new tab is not brought to the front. Camoufox refuses to
        activate windows, since doing so is one of the things that gives an
        automated browser away, so tabs are addressed by their handle rather
        than by being focused.
        """
        result = await self.connection.send('Browser.newPage', {'browserContextId': self.browser_context_id}, timeout=timeout)
        target_id = result['targetId']
        page = self.pages.get(target_id)
        if page is None:
            future: asyncio.Future[Page] = asyncio.get_running_loop().create_future()
            self.pending_pages[target_id] = future
            page = await wait_for(future, timeout, 'the new tab to attach')
        if page in self.new_pages:
            self.new_pages.remove(page)
        await page.wait_until_ready(timeout)
        if url:
            await page.open(url, wait=wait, timeout=timeout)
        return page

    async def popup_pages(self) -> tuple[Page, ...]:
        """Tabs the pages themselves opened, for example by a link with target=_blank."""
        ans = tuple(self.new_pages)
        self.new_pages.clear()
        return ans

    # Browser wide settings {{{

    async def set_proxy(self, proxy: Mapping[str, Any]) -> None:
        params = {
            'browserContextId': self.browser_context_id,
            'type': proxy.get('type') or 'http',
            'host': proxy['host'],
            'port': int(proxy['port']),
            'bypass': list(proxy.get('bypass') or ()),
        }
        for key in ('username', 'password'):
            if proxy.get(key):
                params[key] = proxy[key]
        await self.connection.send('Browser.setContextProxy', params)

    async def set_extra_headers(self, headers: Mapping[str, str]) -> None:
        await self.connection.send(
            'Browser.setExtraHTTPHeaders',
            {'browserContextId': self.browser_context_id, 'headers': [{'name': k, 'value': v} for k, v in headers.items()]},
        )

    async def cookies(self) -> list[dict[str, Any]]:
        result = await self.connection.send('Browser.getCookies', {'browserContextId': self.browser_context_id})
        return result.get('cookies') or []

    async def set_cookies(self, cookies: Iterable[Mapping[str, Any]]) -> None:
        await self.connection.send('Browser.setCookies', {'browserContextId': self.browser_context_id, 'cookies': [dict(c) for c in cookies]})

    async def clear_cookies(self) -> None:
        await self.connection.send('Browser.clearCookies', {'browserContextId': self.browser_context_id})

    async def user_agent(self) -> str:
        result = await self.connection.send('Browser.getInfo')
        return result.get('userAgent') or ''

    # }}}

    def reap(self, process: Process, transport: Transport | None) -> None:
        """Wait for the browser to exit, killing it if it will not, and release
        the pipes. Every step of this blocks, so it runs in a worker thread."""
        # Closing the command pipe is what actually makes the browser shut
        # down cleanly, without it the pipe reader thread inside the browser
        # hangs and the process dies of a segfault instead
        self.connection.close()
        if process.wait(CLOSE_TIMEOUT) is None:
            debug('The camoufox browser did not exit when asked, killing it')
            process.kill()
        if transport is not None:
            transport.shutdown()
        process.cleanup(close_pipes=transport is None)
        if self.keep_log:
            debug(f'The camoufox browser log is at {process.log_path}')

    async def close(self) -> None:
        """Shut the browser down, cleaning up its profile directory."""
        loop = asyncio.get_running_loop()
        process, self.process = self.process, None
        if process is not None:
            try:
                # Ask politely first. The browser never answers this, it just
                # starts exiting, so do not wait for a reply.
                if not self.closed:
                    self.connection.send_nowait('Browser.close')
            except Error, OSError:
                pass
            transport = self.connection.transport
            await loop.run_in_executor(None, self.reap, process, transport)
        self.closed = True
        self.pages.clear()
        if self.profile_dir and not self.keep_log:
            # Deleting the profile retries for a while on Windows, so it must
            # not run on the event loop either
            profile_dir, self.profile_dir = self.profile_dir, ''
            await loop.run_in_executor(None, remove_profile_dir, profile_dir)


async def main(args: Sequence[str] = tuple(sys.argv)) -> None:
    """Load the URLs given on the command line and print out some information
    about them, for testing this module by hand."""
    urls = [x for x in args[1:] if not x.startswith('-')]
    async with Browser(headless='--headful' not in args, keep_log='--keep-log' in args) as browser:
        print('User agent:', await browser.user_agent())
        for i, url in enumerate(urls):
            page = browser.page if i == 0 else await browser.new_page()
            await page.open(url)
            print(f'{url}: {await page.title()}')
            html = await page.html()
            print(f'  {len(html)} bytes of HTML, {len(page.resource_urls())} resources requested')
            for resource_url in page.resource_urls(r'\.(png|jpe?g|gif|svg|webp)(\?|$)')[:3]:
                try:
                    resource = await page.get_resource(resource_url)
                except Error as err:
                    print(f'  failed to get {resource_url}: {err}')
                else:
                    print(f'  {len(resource.data)} bytes of {resource.content_type} from {resource_url}')


if __name__ == '__main__':
    asyncio.run(main())
