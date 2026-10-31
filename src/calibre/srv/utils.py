#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import errno
import os
import reprlib
import socket
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from email.utils import formatdate
from http.cookies import SimpleCookie
from operator import itemgetter
from typing import IO, TYPE_CHECKING, Literal, cast, overload
from urllib.parse import parse_qs
from urllib.parse import quote as urlquote

from calibre import prints
from calibre.constants import iswindows
from calibre.srv.errors import HTTPNotFound
from calibre.utils.localization import get_translator
from calibre.utils.logging import ThreadSafeLog
from calibre.utils.shared_file import share_open
from calibre.utils.socket_inheritance import set_socket_inherit
from polyglot.binary import as_hex_unicode as encode_name  # ruff: ignore[unused-import]
from polyglot.binary import from_hex_unicode as decode_name  # ruff: ignore[unused-import]
from polyglot.builtins import as_unicode

if TYPE_CHECKING:
    from calibre.db.cache import Cache
    from calibre.srv.handler import Context
    from calibre.srv.http_response import RequestData
    from calibre_extensions.translator import Translator

    # Maps a BCP 47 language code to the result of get_translator()
    type TranslatorCache = dict[str, tuple[bool, str, Translator]]

HTTP1 = 'HTTP/1.0'
HTTP11 = 'HTTP/1.1'
DESIRED_SEND_BUFFER_SIZE = 16 * 1024  # windows 7 uses an 8KB sndbuf


def connection_header_tokens(value: str) -> set[str]:
    return {x.strip().lower() for x in value.split(',') if x.strip()}


def http_date(timeval: float | None = None) -> str:
    return str(formatdate(timeval=timeval, usegmt=True))


class MultiDict[V](dict[str, list[V]]):  # {{{
    # Assigning to a key appends a value and reading a key returns the last
    # value, so the item methods intentionally differ from those of dict

    def __setitem__(self, key: str, val: V) -> None:  # ty: ignore[invalid-method-override]
        vals = dict.get(self, key, [])
        vals.append(val)
        dict.__setitem__(self, key, vals)

    def __getitem__(self, key: str) -> V:  # ty: ignore[invalid-method-override]
        return dict.__getitem__(self, key)[-1]

    @staticmethod
    def create_from_query_string(qs: str | bytes) -> MultiDict[str]:
        ans: MultiDict[str] = MultiDict()
        qs = as_unicode(qs)
        for k, v in parse_qs(qs, keep_blank_values=True).items():
            dict.__setitem__(ans, as_unicode(k), [as_unicode(x) for x in v])
        return ans

    def update_from_listdict(self, ld: Mapping[str, Iterable[V]]) -> None:
        for key, values in ld.items():
            for val in values:
                self[key] = val

    def items(self, duplicates: bool = True) -> Iterator[tuple[str, V]]:  # ty: ignore[invalid-method-override]
        f = dict.items
        for k, v in f(self):
            if duplicates:
                for x in v:
                    yield k, x
            else:
                yield k, v[-1]

    iteritems = items

    def values(self, duplicates: bool = True) -> Iterator[V]:  # ty: ignore[invalid-method-override]
        f = dict.values
        for v in f(self):
            if duplicates:
                yield from v
            else:
                yield v[-1]

    itervalues = values

    def set(self, key: str, val: V, replace_all: bool = False) -> None:
        if replace_all:
            dict.__setitem__(self, key, [val])
        else:
            self[key] = val

    @overload
    def get(self, key: str, default: None = None, all: Literal[False] = False) -> V | None: ...
    @overload
    def get[D](self, key: str, default: D, all: Literal[False] = False) -> V | D: ...
    @overload
    def get(self, key: str, default: object = None, *, all: Literal[True]) -> list[V]: ...
    @overload
    def get(self, key: str, default: object, all: Literal[True]) -> list[V]: ...
    def get(self, key: str, default: object = None, all: bool = False) -> object:  # ty: ignore[invalid-method-override]
        if all:
            try:
                return dict.__getitem__(self, key)
            except KeyError:
                return []
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    @overload
    def pop(self, key: str, default: None = None, all: Literal[False] = False) -> V | None: ...
    @overload
    def pop[D](self, key: str, default: D, all: Literal[False] = False) -> V | D: ...
    @overload
    def pop(self, key: str, default: object = None, *, all: Literal[True]) -> list[V]: ...
    @overload
    def pop(self, key: str, default: object, all: Literal[True]) -> list[V]: ...
    def pop(self, key: str, default: object = None, all: bool = False) -> object:  # ty: ignore[invalid-method-override]
        ans = dict.pop(self, key, default)
        if ans is default:
            return [] if all else default
        ans = cast('list[V]', ans)
        return ans if all else ans[-1]

    def __repr__(self) -> str:
        return '{' + ', '.join(f'{reprlib.repr(k)}: {reprlib.repr(v)}' for k, v in self.items()) + '}'

    __str__ = __unicode__ = __repr__

    def pretty(self, leading_whitespace: str = '') -> str:
        return leading_whitespace + ('\n' + leading_whitespace).join(
            f'{k}: {(repr(v) if isinstance(v, bytes) else v)}' for k, v in sorted(self.items(), key=itemgetter(0))
        )


# }}}


def error_codes(*errnames: str) -> set[int]:
    """Return error numbers for error names, ignoring non-existent names"""
    ans: set[int | None] = {getattr(errno, x, None) for x in errnames}
    ans.discard(None)
    return cast('set[int]', ans)


socket_errors_eintr = error_codes('EINTR', 'WSAEINTR')

socket_errors_socket_closed = error_codes(  # errors indicating a disconnected connection
    'EPIPE',
    'EBADF',
    'WSAEBADF',
    'ENOTSOCK',
    'WSAENOTSOCK',
    'ENOTCONN',
    'WSAENOTCONN',
    'ESHUTDOWN',
    'WSAESHUTDOWN',
    'ETIMEDOUT',
    'WSAETIMEDOUT',
    'ECONNREFUSED',
    'WSAECONNREFUSED',
    'ECONNRESET',
    'WSAECONNRESET',
    'ECONNABORTED',
    'WSAECONNABORTED',
    'ENETRESET',
    'WSAENETRESET',
    'EHOSTDOWN',
    'EHOSTUNREACH',
)
socket_errors_nonblocking = error_codes('EAGAIN', 'EWOULDBLOCK', 'WSAEWOULDBLOCK')


def start_cork(sock: socket.socket) -> None:
    if hasattr(socket, 'TCP_CORK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 1)


def stop_cork(sock: socket.socket) -> None:
    if hasattr(socket, 'TCP_CORK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 0)


def create_sock_pair() -> tuple[socket.socket, socket.socket]:
    """Create socket pair."""
    client_sock, srv_sock = socket.socketpair()
    set_socket_inherit(client_sock, False), set_socket_inherit(srv_sock, False)
    return client_sock, srv_sock


def parse_http_list(header_val: str) -> Iterator[str]:
    """Parse lists as described by RFC 2068 Section 2.

    In particular, parse comma-separated lists where the elements of
    the list may include quoted-strings.  A quoted-string could
    contain a comma.  A non-quoted string could have quotes in the
    middle.  Neither commas nor quotes count if they are escaped.
    Only double-quotes count, not single-quotes.
    """
    if isinstance(header_val, bytes):
        # Only str works, as iterating over bytes yields ints, which cannot be
        # appended to part
        slash, dquote, comma = b'\\",'
        empty: str = b''  # ty: ignore[invalid-assignment]
    else:
        slash, dquote, comma = '\\",'
        empty = ''

    part = empty
    escape = quote = False
    for cur in header_val:
        if escape:
            part += cur
            escape = False
            continue
        if quote:
            if cur == slash:
                escape = True
                continue
            elif cur == dquote:
                quote = False
            part += cur
            continue

        if cur == comma:
            yield part.strip()
            part = empty
            continue

        if cur == dquote:
            quote = True

        part += cur

    if part:
        yield part.strip()


def parse_http_dict(header_val: str | None) -> dict[str, str]:
    'Parse an HTTP comma separated header with items of the form a=1, b="xxx" into a dictionary'
    if not header_val:
        return {}
    ans: dict[str, str] = {}
    sep, dquote = b'="' if isinstance(header_val, bytes) else '="'
    for item in parse_http_list(header_val):
        k, v = item.partition(sep)[::2]  # ty: ignore[no-matching-overload]
        if k:
            if v.startswith(dquote) and v.endswith(dquote):
                v = v[1:-1]
            ans[k] = v
    return ans


def sort_q_values(header_val: str | None) -> Sequence[str]:
    "Get sorted items from an HTTP header of type: a;q=0.5, b;q=0.7..."
    if not header_val:
        return []

    def item(x: str) -> tuple[str, float]:
        e, r = x.partition(';')[::2]
        p, v = r.partition('=')[::2]
        q = 1.0
        if p == 'q' and v:
            try:
                q = max(0.0, min(1.0, float(v.strip())))
            except Exception:
                pass
        return e.strip(), q

    return tuple(map(itemgetter(0), sorted(map(item, parse_http_list(header_val)), key=itemgetter(1), reverse=True)))


def eintr_retry_call[**P, T](func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    while True:
        try:
            return func(*args, **kwargs)
        except OSError as e:
            if getattr(e, 'errno', None) in socket_errors_eintr:
                continue
            raise


def get_translator_for_lang(cache: TranslatorCache, bcp_47_code: str) -> tuple[bool, str, Translator]:
    try:
        return cache[bcp_47_code]
    except KeyError:
        pass
    cache[bcp_47_code] = ans = get_translator(bcp_47_code)
    return ans


def encode_path(*components: str) -> str:
    "Encode the path specified as a list of path components using URL encoding"
    return '/' + '/'.join(urlquote(x.encode('utf-8'), '') for x in components)


class Cookie(SimpleCookie):
    def _BaseCookie__set(self, key: str, real_value: str, coded_value: str) -> None:
        return SimpleCookie._BaseCookie__set(self, key, real_value, coded_value)  # type: ignore


def custom_fields_to_display(db: Cache) -> frozenset[str]:
    return frozenset(db.field_metadata.ignorable_field_keys())


# Logging {{{


class ServerLog(ThreadSafeLog):
    exception_traceback_level = ThreadSafeLog.WARN


class RotatingStream:
    stream: IO[str]

    def __init__(self, filename: str, max_size: int | None = None, history: int = 5) -> None:
        self.filename, self.history, self.max_size = filename, history, max_size
        if iswindows:
            self.filename = '\\\\?\\' + os.path.abspath(self.filename)
        self.set_output()

    def set_output(self) -> None:
        if iswindows:
            self.stream = share_open(self.filename, 'a', newline='')
        else:
            # see https://bugs.python.org/issue27805
            self.stream = open(os.open(self.filename, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC, mode=0o666), 'w')  # ruff: ignore[open-file-with-context-handler]
        try:
            self.stream.tell()
        except OSError:
            # Happens if filename is /dev/stdout for example
            self.max_size = None

    def flush(self) -> None:
        self.stream.flush()

    def prints(self, level: int, *args: object, **kwargs: object) -> None:
        kwargs['file'] = self.stream
        prints(*args, **kwargs)
        self.rollover()

    def rename(self, src: str, dest: str) -> None:
        try:
            if iswindows:
                from calibre_extensions import winutil

                winutil.move_file(src, dest)
            else:
                os.rename(src, dest)
        except OSError as e:
            if e.errno != errno.ENOENT:  # the source of the rename does not exist
                raise

    def rollover(self) -> None:
        if not self.max_size or self.stream.tell() <= self.max_size:
            return
        self.stream.close()
        for i in range(self.history - 1, 0, -1):
            src, dest = f'{self.filename}.{i}', f'{self.filename}.{i + 1}'
            self.rename(src, dest)
        self.rename(self.filename, f'{self.filename}.1')
        self.set_output()

    def clear(self) -> dict[str, OSError] | None:
        if self.filename in ('/dev/stdout', '/dev/stderr'):
            return
        self.stream.close()
        failed: dict[str, OSError] = {}
        try:
            os.remove(self.filename)
        except OSError as e:
            failed[self.filename] = e
        import glob

        for f in glob.glob(self.filename + '.*'):
            try:
                os.remove(f)
            except OSError as e:
                failed[f] = e
        self.set_output()
        return failed


class RotatingLog(ServerLog):
    def __init__(self, filename: str, max_size: int | None = None, history: int = 5) -> None:
        ServerLog.__init__(self)
        self.outputs = [RotatingStream(filename, max_size, history)]

    def flush(self) -> None:
        for o in self.outputs:
            o.flush()


# }}}


class HandleInterrupt:  # {{{
    # On windows socket functions like accept(), recv(), send() are not
    # interrupted by a Ctrl-C in the console. So to make Ctrl-C work we have to
    # use this special context manager. See the echo server example at the
    # bottom of srv/loop.py for how to use it.

    def __init__(self, action: Callable[[], object] | None) -> None:
        if not iswindows:
            return  # Interrupts work fine on POSIX
        self.action = action
        from ctypes import WINFUNCTYPE, windll
        from ctypes.wintypes import BOOL, DWORD

        kernel32 = windll.LoadLibrary('kernel32')

        # <http://msdn.microsoft.com/en-us/library/ms686016.aspx>
        PHANDLER_ROUTINE = WINFUNCTYPE(BOOL, DWORD)
        self.SetConsoleCtrlHandler = kernel32.SetConsoleCtrlHandler
        self.SetConsoleCtrlHandler.argtypes = (PHANDLER_ROUTINE, BOOL)
        self.SetConsoleCtrlHandler.restype = BOOL

        @PHANDLER_ROUTINE
        def handle(event: int) -> int:
            if event == 0:  # CTRL_C_EVENT
                if self.action is not None:
                    self.action()
                    self.action = None
                    return 1
            return 0

        self.handle = handle

    def __enter__(self) -> None:
        if iswindows:
            if self.SetConsoleCtrlHandler(self.handle, 1) == 0:
                import ctypes

                raise ctypes.WinError()

    def __exit__(self, *args: object) -> None:
        if iswindows:
            if self.SetConsoleCtrlHandler(self.handle, 0) == 0:
                import ctypes

                raise ctypes.WinError()


# }}}


class Accumulator:  # {{{
    "Optimized replacement for BytesIO when the usage pattern is many writes followed by a single getvalue()"

    def __init__(self) -> None:
        self._buf: list[bytes] = []
        self.total_length = 0

    def append(self, b: bytes) -> None:
        self._buf.append(b)
        self.total_length += len(b)

    def getvalue(self) -> bytes:
        ans = b''.join(self._buf)
        self._buf = []
        self.total_length = 0
        return ans


# }}}


def is_recipe_fmt(fmt: str) -> bool:
    # Recipes are python source code, so they must never be accepted from or
    # processed on behalf of remote clients as they allow code execution
    fmt = fmt.lower().lstrip('.').removeprefix('original_')
    return fmt in ('recipe', 'downloaded_recipe')


def get_db(ctx: Context, rd: RequestData, library_id: str | None) -> Cache:
    db = ctx.get_library(rd, library_id)
    if db is None:
        raise HTTPNotFound(f'Library {library_id!r} not found')
    return db


def get_library_data(ctx: Context, rd: RequestData, strict_library_id: bool = False) -> tuple[Cache, str, dict[str, str], str]:
    # Endpoints that change the database must never fall back to the default
    # library when asked for one that does not exist
    library_id = rd.query.get('library_id')
    library_map, default_library = ctx.library_info(rd)
    if library_id not in library_map:
        if (strict_library_id or rd.needs_db_write) and library_id:
            raise HTTPNotFound(f'No library with id: {library_id}')
        library_id = default_library
    db = get_db(ctx, rd, library_id)
    return db, library_id, library_map, default_library


class Offsets:
    "Calculate offsets for a paginated view"

    def __init__(self, offset: int, delta: int, total: int) -> None:
        offset = max(offset, 0)
        if offset >= total:
            raise HTTPNotFound(f'Invalid offset: {offset!r}')
        last_allowed_index = total - 1
        last_current_index = offset + delta - 1
        self.slice_upper_bound = offset + delta
        self.offset = offset
        self.next_offset = last_current_index + 1
        if self.next_offset > last_allowed_index:
            self.next_offset = -1
        self.previous_offset = self.offset - delta
        self.previous_offset = max(self.previous_offset, 0)
        self.last_offset = (last_allowed_index // delta) * delta


_use_roman: bool | None = None


def get_use_roman() -> bool:
    global _use_roman
    if _use_roman is None:
        from calibre.gui2 import config

        _use_roman = config['use_roman_numerals_for_series_number']
    return _use_roman
