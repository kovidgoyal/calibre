# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid@kovidgoyal.net>

"""E-book management software"""

import os
import re
import sys
import time
import warnings
from functools import lru_cache, partial
from math import floor
from typing import IO, TYPE_CHECKING, Any, TextIO, TypedDict, Unpack, cast, overload

from polyglot.builtins import hasenv

if not hasenv('CALIBRE_SHOW_DEPRECATION_WARNINGS'):
    warnings.simplefilter('ignore', DeprecationWarning)
try:
    os.getcwd()
except OSError:
    os.chdir(os.path.expanduser('~'))

from calibre.constants import (  # ruff: ignore[unused-import]
    __appname__,
    __author__,
    __version__,
    config_dir,
    filesystem_encoding,
    is_debugging,
    isbsd,
    isfrozen,
    islinux,
    ismacos,
    iswindows,
    plugins,
    preferred_encoding,
)
from calibre.startup import initialize_calibre

initialize_calibre()
from calibre.prints import prints
from calibre.utils.icu import safe_chr
from calibre.utils.resources import get_path as P

if TYPE_CHECKING:
    import ctypes
    import logging
    from collections.abc import Collection, Iterator, Mapping
    from datetime import date

    from calibre.utils.browser import Browser

    class PrintKwargs(TypedDict, total=False):
        sep: str | None
        end: str | None
        file: TextIO | None
        flush: bool


_mt_inited = False


def _init_mimetypes() -> None:
    global _mt_inited
    import mimetypes

    mimetypes.init([P('mime.types')])
    _mt_inited = True


@lru_cache(4096)
def guess_type(*args: *tuple[str, *tuple[bool, ...]], **kwargs: bool) -> tuple[str | None, str | None]:
    import mimetypes

    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.guess_type(*args, **kwargs)


def guess_all_extensions(*args: *tuple[str, *tuple[bool, ...]], **kwargs: bool) -> list[str]:
    import mimetypes

    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.guess_all_extensions(*args, **kwargs)


def guess_extension(*args: *tuple[str, *tuple[bool, ...]], **kwargs: bool) -> str | None:
    import mimetypes

    if not _mt_inited:
        _init_mimetypes()
    ext = mimetypes.guess_extension(*args, **kwargs)
    if not ext and args and args[0] == 'application/x-palmreader':  # ty: ignore[redundant-condition]
        ext = '.pdb'
    return ext


def get_types_map() -> dict[str, str]:
    import mimetypes

    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.types_map


def to_unicode(raw: str | bytes, encoding: str = 'utf-8', errors: str = 'strict') -> str:
    if isinstance(raw, str):
        return raw
    return raw.decode(encoding, errors)


def patheq(p1: str | None, p2: str | None) -> bool:
    p = os.path

    def d(x: str) -> str:
        return p.normcase(p.normpath(p.realpath(p.normpath(x))))

    if not p1 or not p2:
        return False
    return d(p1) == d(p2)


def unicode_path(path: str | bytes, abs: bool = False) -> str:
    if isinstance(path, bytes):
        path = path.decode(filesystem_encoding)
    if abs:
        path = os.path.abspath(path)
    return path


def osx_version() -> tuple[int, int, int] | None:
    if ismacos:
        import platform

        src = platform.mac_ver()[0]
        m = re.match(r'(\d+)\.(\d+)\.(\d+)', src)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))


def confirm_config_name(name: str) -> str:
    return name + '_again'


_filename_sanitize_unicode = frozenset(
    (
        '\\',
        '|',
        '?',
        '*',
        '<',  # no2to3
        '"',
        ':',
        '>',
        '+',
        '/',
    )
    + tuple(map(chr, range(32)))
)  # no2to3


def sanitize_file_name(name: str | bytes, substitute: str | bytes = '_') -> str:
    """
    Sanitize the filename `name`. All invalid characters are replaced by `substitute`.
    The set of invalid characters is the union of the invalid characters in Windows,
    macOS and Linux. Also removes leading and trailing whitespace.
    **WARNING:** This function also replaces path separators, so only pass file names
    and not full paths to it.
    """
    if isinstance(name, bytes):
        name = name.decode(filesystem_encoding, 'replace')
    if isinstance(substitute, bytes):
        substitute = substitute.decode(filesystem_encoding, 'replace')
    chars = (substitute if c in _filename_sanitize_unicode else c for c in name)
    one = ''.join(chars)
    one = re.sub(r'\s', ' ', one).strip()
    bname, ext = os.path.splitext(one)
    one = re.sub(r'^\.+$', '_', bname)
    one = one.replace('..', substitute)
    one += ext
    # Windows doesn't like path components that end with a period or space
    if one and one[-1] in ('.', ' '):
        one = one[:-1] + '_'
    # Names starting with a period are hidden on Unix
    if one.startswith('.'):
        one = '_' + one[1:]
    return one


sanitize_file_name2 = sanitize_file_name_unicode = sanitize_file_name


class CommandLineError(Exception):
    pass


def setup_cli_handlers(logger: logging.Logger, level: int) -> None:
    import logging

    if hasenv('CALIBRE_WORKER') and logger.handlers:
        return
    logger.setLevel(level)
    if level == logging.WARNING:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        handler.setLevel(logging.WARNING)
    elif level == logging.INFO:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter())
        handler.setLevel(logging.INFO)
    elif level == logging.DEBUG:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(filename)s:%(lineno)s: %(message)s'))

    logger.addHandler(handler)


def load_library[T: ctypes.CDLL](name: str, cdll: ctypes.LibraryLoader[T]) -> T:
    if iswindows:
        return cdll.LoadLibrary(name)
    if ismacos:
        name += '.dylib'
        if hasattr(sys, 'frameworks_dir'):
            return cdll.LoadLibrary(os.path.join(sys.frameworks_dir, name))
        return cdll.LoadLibrary(name)
    return cdll.LoadLibrary(name + '.so')


def extract(path: str, dir: str) -> None:
    extractor = None
    # First use the file header to identify its type
    with open(path, 'rb') as f:
        id_ = f.read(3)
    if id_ == b'Rar':
        from calibre.utils.unrar import extract as rarextract

        extractor = rarextract
    elif id_.startswith(b'PK'):
        from calibre.libunzip import extract as zipextract

        extractor = zipextract
    elif id_.startswith(b'7z'):
        from calibre.utils.seven_zip import extract as seven_extract

        extractor = seven_extract
    if extractor is None:
        # Fallback to file extension
        ext = os.path.splitext(path)[1][1:].lower()
        if ext in ('zip', 'cbz', 'epub', 'oebzip'):
            from calibre.libunzip import extract as zipextract

            extractor = zipextract
        elif ext in ('cbr', 'rar'):
            from calibre.utils.unrar import extract as rarextract

            extractor = rarextract
        elif ext in ('cb7', '7z'):
            from calibre.utils.seven_zip import extract as seven_extract

            extractor = seven_extract
    if extractor is None:
        raise Exception('Unknown archive type')
    extractor(path, dir)


def get_proxies(debug: bool = True) -> dict[str, str]:
    from urllib.request import getproxies

    proxies = getproxies()
    for key, proxy in list(proxies.items()):
        if not proxy or '..' in proxy or key == 'auto':
            del proxies[key]
            continue
        if proxy.startswith(key + '://'):
            proxy = proxy[len(key) + 3 :]
        if key == 'https' and proxy.startswith('http://'):
            proxy = proxy[7:]
        proxy = proxy.removesuffix('/')
        if len(proxy) > 4:
            proxies[key] = proxy
        else:
            prints('Removing invalid', key, 'proxy:', proxy)
            del proxies[key]

    if proxies and debug:
        prints('Using proxies:', proxies)
    return proxies


def get_parsed_proxy(typ: str = 'http', debug: bool = True) -> dict[str, str | int | None] | None:
    proxies = get_proxies(debug)
    proxy = proxies.get(typ, None)
    if proxy:
        pattern = re.compile(
            (
                r'(?:ptype://)?'
                r'(?:(?P<user>\w+):(?P<pass>.*)@)?'
                r'(?P<host>[\w\-\.]+)'
                r'(?::(?P<port>\d+))?'
            ).replace('ptype', typ)
        )

        match = pattern.match(proxies[typ])
        if match:
            try:
                ans = {
                    'host': match.group('host'),
                    'port': match.group('port'),
                    'user': match.group('user'),
                    'pass': match.group('pass'),
                }
                if ans['port']:
                    ans['port'] = int(ans['port'])
            except Exception:
                if debug:
                    import traceback

                    traceback.print_exc()
            else:
                if debug:
                    prints('Using http proxy', str(ans))
                return ans


def get_proxy_info(proxy_scheme: str, proxy_string: str) -> dict[str, str | int | None] | None:
    """
    Parse all proxy information from a proxy string (as returned by
    get_proxies). The returned dict will have members set to None when the info
    is not available in the string. If an exception occurs parsing the string
    this method returns None.
    """
    from urllib.parse import urlparse

    try:
        proxy_url = f'{proxy_scheme}://{proxy_string}'
        urlinfo = urlparse(proxy_url)
        ans = {
            'scheme': urlinfo.scheme,
            'hostname': urlinfo.hostname,
            'port': urlinfo.port,
            'username': urlinfo.username,
            'password': urlinfo.password,
        }
    except Exception:
        return None
    return ans


def is_mobile_ua(ua: str) -> bool:
    return 'Mobile/' in ua or 'Mobile ' in ua


def random_user_agent(choose: int | None = None, allow_ie: bool = True) -> str:
    from calibre.utils.random_ua import choose_randomly_by_popularity, common_user_agents

    ua_list = common_user_agents()
    ua_list = tuple(x for x in ua_list if not is_mobile_ua(x))
    if not allow_ie:
        ua_list = tuple(x for x in ua_list if 'Trident/' not in x)
    if choose is not None:
        return ua_list[choose]
    return choose_randomly_by_popularity(ua_list)


def browser(
    honor_time: bool = True,
    max_time: float = 2,
    user_agent: str | None = None,
    verify_ssl_certificates: bool = True,
    handle_refresh: bool = True,
    **kw: object,
) -> Browser:
    """
    Create a mechanize browser for web scraping. The browser handles cookies,
    refresh requests and ignores robots.txt. Also uses proxy if available.

    :param honor_time: If True honors pause time in refresh requests
    :param max_time: Maximum time in seconds to wait during a refresh request
    :param verify_ssl_certificates: If false SSL certificates errors are ignored
    """
    from calibre.utils.browser import Browser

    opener = Browser(verify_ssl=verify_ssl_certificates)
    opener.set_handle_refresh(handle_refresh, max_time=max_time, honor_time=honor_time)
    opener.set_handle_robots(False)
    if user_agent is None:
        user_agent = random_user_agent(0, allow_ie=False)
    elif user_agent == 'common_words/based':
        from calibre.utils.random_ua import common_english_word_ua

        user_agent = common_english_word_ua()
    opener.addheaders = [('User-agent', user_agent)]
    proxies = get_proxies()
    to_add = {}
    http_proxy = proxies.get('http', None)
    if http_proxy:
        to_add['http'] = http_proxy
    https_proxy = proxies.get('https', None)
    if https_proxy:
        to_add['https'] = https_proxy
    if to_add:
        opener.set_proxies(to_add)

    return opener


def fit_image(width: float, height: float, pwidth: float, pheight: float) -> tuple[bool, int, int]:
    """
    Fit image in box of width pwidth and height pheight.
    @param width: Width of image
    @param height: Height of image
    @param pwidth: Width of box
    @param pheight: Height of box
    @return: scaled, new_width, new_height. scaled is True iff new_width and/or new_height is different from width or height.
    """
    if height < 1 or width < 1:
        return False, int(width), int(height)
    scaled = height > pheight or width > pwidth
    if height > pheight:
        corrf = pheight / float(height)
        width, height = floor(corrf * width), pheight
    if width > pwidth:
        corrf = pwidth / float(width)
        width, height = pwidth, floor(corrf * height)
    if height > pheight:
        corrf = pheight / float(height)
        width, height = floor(corrf * width), pheight

    return scaled, int(width), int(height)


class CurrentDir:
    def __init__(self, path: str) -> None:
        self.path = path
        self.cwd: str | None = None

    def __enter__(self, *args: object) -> str:
        self.cwd = os.getcwd()
        os.chdir(self.path)
        return self.cwd

    def __exit__(self, *args: object) -> None:
        try:
            if self.cwd is not None:
                os.chdir(self.cwd)
        except OSError:
            # The previous CWD no longer exists
            pass


_ncpus: int | None = None


def detect_ncpus() -> int:
    global _ncpus
    if _ncpus is None:
        _ncpus = max(1, os.cpu_count() or 1)
    return _ncpus


relpath = os.path.relpath


def walk(dir: str) -> Iterator[str]:
    """A nice interface to os.walk"""
    for record in os.walk(dir):
        for f in record[-1]:
            yield os.path.join(record[0], f)


def strftime(fmt: str, t: time.struct_time | date | None = None) -> str:
    """A version of strftime that returns unicode strings and tries to handle dates
    before 1900"""
    if not fmt:
        return ''
    if t is None:
        t = time.localtime()
    if hasattr(t, 'timetuple'):
        t = t.timetuple()
    early_year = t[0] < 1900
    if early_year:
        replacement = 1900 if t[0] % 4 == 0 else 1901
        fmt = fmt.replace('%Y', '_early year hack##')
        t = list(t)  # ty: ignore[invalid-assignment]
        orig_year = t[0]  # ty: ignore[not-subscriptable]
        t[0] = replacement  # ty: ignore[invalid-assignment]
        t = time.struct_time(t)  # ty: ignore[invalid-argument-type]
    ans = None
    if isinstance(fmt, bytes):
        fmt = fmt.decode('mbcs' if iswindows else 'utf-8', 'replace')
    ans = time.strftime(fmt, t)
    if early_year:
        ans = ans.replace('_early year hack##', str(orig_year))
    return ans


def my_unichr(num: int) -> str:
    try:
        return safe_chr(num)
    except ValueError, OverflowError:
        return '?'


XML_ENTITIES = {'"': '&quot;', "'": '&apos;', '<': '&lt;', '>': '&gt;', '&': '&amp;'}


def entity_to_unicode(
    match: re.Match[str], exceptions: Collection[str] = (), encoding: str | None = None, result_exceptions: Mapping[str, str] | None = None
) -> str:
    """
    :param match: A match object such that '&'+match.group(1)';' is the entity.

    :param exceptions: A list of entities to not convert (Each entry is the name of the entity, e.g. 'apos' or '#1234)'

    :param encoding: The encoding to use to decode numeric entities between 128 and 256.
    If None, the Unicode UCS encoding is used. A common encoding is cp1252.

    :param result_exceptions: A mapping of characters to entities. If the result
    is in result_exceptions, result_exception[result] is returned instead.
    Convenient way to specify exception for things like < or > that can be
    specified by various actual entities.
    """
    from calibre.ebooks.html_entities import entity_to_unicode_in_python
    from calibre_extensions.fast_html_entities import replace_all_entities

    if result_exceptions is None:
        result_exceptions = {}
    if not encoding and not exceptions and (not result_exceptions or result_exceptions is XML_ENTITIES):
        return cast('str', replace_all_entities(match.group(), result_exceptions is XML_ENTITIES))
    return entity_to_unicode_in_python(match, exceptions, encoding, result_exceptions)


xml_entity_to_unicode = partial(entity_to_unicode, result_exceptions=XML_ENTITIES)


@lru_cache(2)
def entity_regex() -> re.Pattern[str]:
    return re.compile(r'&(\S+?);')


def replace_entities[T: (str, bytes)](raw: T, encoding: str | None = None) -> T:
    from calibre_extensions.fast_html_entities import replace_all_entities

    return cast('T', replace_all_entities(raw))


def xml_replace_entities[T: (str, bytes)](raw: T, encoding: str | None = None) -> T:
    from calibre_extensions.fast_html_entities import replace_all_entities

    return cast('T', replace_all_entities(raw, True))


def prepare_string_for_xml(raw: str, attribute: bool = False) -> str:
    raw = replace_entities(raw)
    raw = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if attribute:
        raw = raw.replace('"', '&quot;').replace("'", '&apos;')
    return raw


def isbytestring(obj: object) -> bool:
    return isinstance(obj, bytes)


@overload
def force_unicode(obj: str | bytes, enc: str = ...) -> str: ...
@overload
def force_unicode[T](obj: T | bytes, enc: str = ...) -> T | str: ...
def force_unicode(obj: object, enc: str = preferred_encoding) -> object:
    if isinstance(obj, bytes):
        try:
            obj = obj.decode(enc)
        except Exception:
            try:
                obj = obj.decode(filesystem_encoding if enc == preferred_encoding else preferred_encoding)
            except Exception:
                try:
                    obj = obj.decode('utf-8')
                except Exception:
                    obj = repr(obj)
                    if isinstance(obj, bytes):
                        obj = obj.decode('utf-8')
    return obj


def as_unicode(obj: object, enc: str = preferred_encoding) -> str:
    if not isinstance(obj, bytes):
        try:
            obj = str(obj)
        except Exception:
            try:
                obj = str(obj)
            except Exception:
                obj = repr(obj)
    return force_unicode(obj, enc=enc)


def url_slash_cleaner(url: str) -> str:
    """
    Removes redundant /'s from url's.
    """
    return re.sub(r'(?<!:)/{2,}', '/', url)


def human_readable(size: float, sep: str = ' ') -> str:
    """Convert a size in bytes into a human readable form"""
    divisor, suffix = 1, 'B'
    for i, candidate in enumerate(('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB')):
        if size < (1 << ((i + 1) * 10)):
            divisor, suffix = (1 << (i * 10)), candidate
            break
    size = str(float(size) / divisor)  # ty: ignore[invalid-assignment]
    if size.find('.') > -1:  # ty: ignore[unresolved-attribute]
        size = size[: size.find('.') + 2]  # ty: ignore[not-subscriptable, unresolved-attribute]
    size = size.removesuffix('.0')  # ty: ignore[unresolved-attribute]
    return size + sep + suffix


def ipython(user_ns: dict[str, object] | None = None) -> None:
    from calibre.utils.ipython import ipython

    ipython(user_ns=user_ns)


def fsync(fileobj: IO[Any]) -> None:
    fileobj.flush()
    os.fsync(fileobj.fileno())
    if islinux and getattr(fileobj, 'name', None):
        # On Linux kernels after 5.1.9 and 4.19.50 using fsync without any
        # following activity causes Kindles to eject. Instead of fixing this in
        # the obvious way, which is to have the kernel send some harmless
        # filesystem activity after the FSYNC, the kernel developers seem to
        # think the correct solution is to disable FSYNC using a mount flag
        # which users will have to turn on manually. So instead we create some
        # harmless filesystem activity, and who cares about performance.
        # See https://bugs.launchpad.net/calibre/+bug/1834641
        # and https://bugzilla.kernel.org/show_bug.cgi?id=203973
        # To check for the existence of the bug, simply run:
        # python -c "p = '/run/media/kovid/Kindle/driveinfo.calibre'; f = open(p, 'r+b'); os.fsync(f.fileno());"
        # this will cause the Kindle to disconnect.
        try:
            os.utime(fileobj.name, None)
        except Exception:
            import traceback

            traceback.print_exc()


class TimedPrint:
    startup_time: float = -1

    def __call__(self, *a: object, **kw: Unpack[PrintKwargs]) -> None:
        if not is_debugging():
            return
        from time import monotonic

        if self.startup_time == -1:
            self.startup_time = monotonic()
        print(f'[{monotonic() - self.startup_time:.2f}]', *a, **kw)


timed_print = TimedPrint()
