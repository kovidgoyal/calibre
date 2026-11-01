# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

"""
Wrapper for multi-threaded access to a single sqlite database connection. Serializes
all calls.
"""

import os
import reprlib
import sqlite3 as sqlite
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from functools import partial
from queue import Queue
from sqlite3 import IntegrityError, OperationalError
from threading import RLock, Thread
from typing import TYPE_CHECKING, Literal, cast, overload

from calibre import force_unicode, prints
from calibre.constants import DEBUG, iswindows, plugins, plugins_loc
from calibre.ebooks.metadata import author_to_author_sort, title_sort
from calibre.utils.date import UNDEFINED_DATE, isoformat, local_tz, parse_date
from calibre.utils.icu import sort_key
from calibre_extensions import speedup as _c_speedup
from polyglot.builtins import cmp

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence
    from typing import Concatenate as ConcatenateParams

    #: A value as returned from the sqlite database, after conversion by the registered converters
    type SQLValue = str | int | float | bytes | datetime | None
    #: A row as returned from the database, see the row_factory in :func:`do_connect`
    type SQLRow = list[SQLValue]
    type SQLBindings = Sequence[object] | dict[str, object]

global_lock = RLock()


def _c_convert_timestamp(val: bytes) -> datetime | None:
    if not val:
        return None
    try:
        # NOTE: The C parse_date() only accepts str so this always fails and
        # falls back to the python parse_date() below. Passing str would
        # change behavior as the C parser drops fractional seconds.
        ret = _c_speedup.parse_date(val.strip())  # ty: ignore[invalid-argument-type]
    except Exception:
        ret = None
    if ret is None:
        return parse_date(val, as_utc=False)
    year, month, day, hour, minutes, seconds, tzsecs = ret
    try:
        return datetime(year, month, day, hour, minutes, seconds, tzinfo=timezone(timedelta(seconds=tzsecs))).astimezone(local_tz)
    except OverflowError:
        return UNDEFINED_DATE.astimezone(local_tz)


def _py_convert_timestamp(val: bytes) -> datetime | None:
    if val:
        tzsecs = 0
        try:
            sign = {'+': 1, '-': -1}.get(val[-6], None)
            if sign is not None:
                tzsecs = 60 * ((int(val[-5:-3]) * 60 + int(val[-2:])) * sign)
            year = int(val[0:4])
            month = int(val[5:7])
            day = int(val[8:10])
            hour = int(val[11:13])
            min = int(val[14:16])
            sec = int(val[17:19])
            return datetime(year, month, day, hour, min, sec, tzinfo=timezone(timedelta(seconds=tzsecs)))
        except Exception:
            pass
        return parse_date(val, as_utc=False)
    return None


convert_timestamp = _py_convert_timestamp if _c_speedup is None else _c_convert_timestamp


def adapt_datetime(dt: datetime) -> str:
    return isoformat(dt, sep=' ')


sqlite.register_adapter(datetime, adapt_datetime)
sqlite.register_converter('timestamp', convert_timestamp)


def convert_bool(val: bytes) -> bool:
    return val != '0'


sqlite.register_adapter(bool, lambda x: 1 if x else 0)
sqlite.register_converter('bool', convert_bool)
sqlite.register_converter('BOOL', convert_bool)


class DynamicFilter:
    def __init__(self, name: str) -> None:
        self.name = name
        self.ids: frozenset[int] = frozenset()

    def __call__(self, id_: int) -> int:
        return int(id_ in self.ids)

    def change(self, ids: Iterable[int]) -> None:
        self.ids = frozenset(ids)


class Concatenate:
    """String concatenation aggregator for sqlite"""

    def __init__(self, sep: str = ',') -> None:
        self.sep = sep
        self.ans: list[str] = []

    def step(self, value: str | None) -> None:
        if value is not None:
            self.ans.append(value)

    def finalize(self) -> str | None:
        try:
            if not self.ans:
                return None
            return self.sep.join(self.ans)
        except Exception:
            import traceback

            traceback.print_exc()
            raise


class SortedConcatenate:
    """String concatenation aggregator for sqlite, sorted by supplied index"""

    sep = ','

    def __init__(self) -> None:
        self.ans: dict[int, str] = {}

    def step(self, ndx: int, value: str | None) -> None:
        if value is not None:
            self.ans[ndx] = value

    def finalize(self) -> str | None:
        try:
            if len(self.ans) == 0:
                return None
            return self.sep.join(map(self.ans.__getitem__, sorted(self.ans.keys())))
        except Exception:
            import traceback

            traceback.print_exc()
            raise


class SortedConcatenateBar(SortedConcatenate):
    sep = '|'


class SortedConcatenateAmper(SortedConcatenate):
    sep = '&'


class IdentifiersConcat:
    """String concatenation aggregator for the identifiers map"""

    def __init__(self) -> None:
        self.ans: list[str] = []

    def step(self, key: str, val: str) -> None:
        self.ans.append(f'{key}:{val}')

    def finalize(self) -> str:
        try:
            return ','.join(self.ans)
        except Exception:
            import traceback

            traceback.print_exc()
            raise


class AumSortedConcatenate:
    """String concatenation aggregator for the author sort map"""

    def __init__(self) -> None:
        self.ans: dict[int, str] = {}

    def step(self, ndx: int, author: str | None, sort: str, link: str) -> None:
        if author is not None:
            self.ans[ndx] = ':::'.join((author, sort, link))  # ruff: ignore[static-join-to-f-string]

    def finalize(self) -> str | None:
        try:
            keys = tuple(self.ans)
            l = len(keys)
            if l == 0:
                return None
            if l == 1:
                return self.ans[keys[0]]
            return ':#:'.join([self.ans[v] for v in sorted(keys)])
        except Exception:
            import traceback

            traceback.print_exc()
            raise


class Connection(sqlite.Connection):
    @overload
    def get(self, sql: str, bindings: SQLBindings = ..., /, *, all: Literal[True] = True) -> list[SQLRow]: ...
    @overload
    def get(self, sql: str, bindings: SQLBindings = ..., /, *, all: Literal[False]) -> SQLValue: ...
    @overload
    def get(self, sql: str, bindings: SQLBindings = ..., /, *, all: bool) -> list[SQLRow] | SQLValue: ...
    def get(self, sql: str, bindings: SQLBindings = (), /, *, all: bool = True) -> list[SQLRow] | SQLValue:
        cursor = self.execute(sql, bindings)
        if not all:
            ans = cursor.fetchone()
            if not ans:
                ans = [None]
            return ans[0]
        return cursor.fetchall()


def _author_to_author_sort(x: str | None) -> str:
    if not x:
        return ''
    return author_to_author_sort(x.replace('|', ','))


def pynocase(one: str | bytes, two: str | bytes, encoding: str = 'utf-8') -> int:
    if isinstance(one, bytes):
        try:
            one = one.decode(encoding, 'replace')
        except Exception:
            pass
    if isinstance(two, bytes):
        try:
            two = two.decode(encoding, 'replace')
        except Exception:
            pass
    return cmp(one.lower(), two.lower())


def icu_collator(s1: str, s2: str) -> int:
    return cmp(sort_key(force_unicode(s1, 'utf-8')), sort_key(force_unicode(s2, 'utf-8')))


def load_c_extensions(conn: sqlite.Connection, debug: bool = DEBUG) -> bool:
    try:
        conn.enable_load_extension(True)
        ext_path = os.path.join(plugins_loc, 'sqlite_custom.' + ('pyd' if iswindows else 'so'))
        conn.load_extension(ext_path)
        conn.enable_load_extension(False)
        return True
    except Exception as e:
        if debug:
            print('Failed to load high performance sqlite C extension')
            print(e)
    return False


def do_connect(path: str, row_factory: bool | None = None) -> Connection:
    conn = sqlite.connect(path, factory=Connection)
    conn.execute('pragma cache_size=-5000')
    encoding = conn.execute('pragma encoding').fetchone()[0]
    conn.create_aggregate('sortconcat', 2, SortedConcatenate)  # ty: ignore[invalid-argument-type] typeshed only allows single int argument aggregates
    conn.create_aggregate('sortconcat_bar', 2, SortedConcatenateBar)  # ty: ignore[invalid-argument-type] typeshed only allows single int argument aggregates
    conn.create_aggregate('sortconcat_amper', 2, SortedConcatenateAmper)  # ty: ignore[invalid-argument-type] typeshed only allows single int argument aggregates
    conn.create_aggregate('identifiers_concat', 2, IdentifiersConcat)  # ty: ignore[invalid-argument-type] typeshed only allows single int argument aggregates
    load_c_extensions(conn)
    conn.row_factory = sqlite.Row if row_factory else (lambda cursor, row: list(row))
    conn.create_aggregate('concat', 1, Concatenate)  # ty: ignore[invalid-argument-type] typeshed only allows single int argument aggregates
    conn.create_aggregate('aum_sortconcat', 4, AumSortedConcatenate)  # ty: ignore[invalid-argument-type] typeshed only allows single int argument aggregates
    conn.create_collation('PYNOCASE', partial(pynocase, encoding=encoding))
    conn.create_function('title_sort', 1, title_sort)
    conn.create_function('author_to_author_sort', 1, _author_to_author_sort)
    conn.create_function('uuid4', 0, lambda: str(uuid.uuid4()))
    # Dummy functions for dynamically created filters
    conn.create_function('books_list_filter', 1, lambda x: 1)
    conn.create_collation('icucollate', icu_collator)
    plugins.load_sqlite3_extension(conn, 'sqlite_extension')
    return conn


class DBThread(Thread):
    CLOSE = '-------close---------'

    def __init__(self, path: str, row_factory: bool | None) -> None:
        Thread.__init__(self, daemon=True)
        self.path = path
        self.unhandled_error: tuple[BaseException | None, str] = (None, '')
        self.row_factory = row_factory
        self.requests: Queue[tuple[str, Sequence[object], Mapping[str, object]]] = Queue(1)
        self.results: Queue[tuple[bool, object]] = Queue(1)
        self.conn: Connection | None = None

    def connect(self) -> None:
        self.conn = do_connect(self.path, self.row_factory)

    def run(self) -> None:
        try:
            self.connect()
            while True:
                func, args, kwargs = self.requests.get()
                if func == self.CLOSE:
                    assert self.conn is not None
                    self.conn.close()
                    break
                if func == 'dump':
                    try:
                        assert self.conn is not None
                        ok, res = True, tuple(self.conn.iterdump())
                    except Exception as err:
                        ok, res = False, (err, traceback.format_exc())
                elif func == 'create_dynamic_filter':
                    try:
                        f = DynamicFilter(cast('str', args[0]))
                        assert self.conn is not None
                        self.conn.create_function(cast('str', args[0]), 1, f)
                        ok, res = True, f
                    except Exception as err:
                        ok, res = False, (err, traceback.format_exc())
                else:
                    bfunc = getattr(self.conn, func)
                    try:
                        for i in range(3):
                            try:
                                ok, res = True, bfunc(*args, **kwargs)
                                break
                            except OperationalError as err:
                                # Retry if unable to open db file
                                e = str(err)
                                if 'unable to open' not in e or i == 2:
                                    if 'unable to open' in e:
                                        prints(
                                            'Unable to open database for func',
                                            func,
                                            reprlib.repr(args),
                                            reprlib.repr(kwargs),
                                        )
                                    raise
                            time.sleep(0.5)
                    except Exception as err:
                        ok, res = False, (err, traceback.format_exc())
                self.results.put((ok, res))
        except Exception as err:
            self.unhandled_error = (err, traceback.format_exc())


class DatabaseException(Exception):
    def __init__(self, err: BaseException | str | None, tb: str) -> None:
        tb = '\n\t'.join(('\tRemote' + tb).splitlines())
        try:
            msg = str(err) + '\n' + tb
        except Exception:
            msg = repr(err) + '\n' + tb
        Exception.__init__(self, msg)
        self.orig_err = err
        self.orig_tb = tb


def proxy[**P, R](fn: Callable[ConcatenateParams[ConnectionProxy, P], R]) -> Callable[ConcatenateParams[ConnectionProxy, P], R]:
    """Decorator to call methods on the database connection in the proxy thread"""

    def run(self: ConnectionProxy, *args: P.args, **kwargs: P.kwargs) -> R:
        if self.closed:
            raise DatabaseException('Connection closed', '')
        with global_lock:
            if self.proxy.unhandled_error[0] is not None:
                raise DatabaseException(*self.proxy.unhandled_error)
            self.proxy.requests.put((fn.__name__, args, kwargs))  # ty: ignore[unresolved-attribute] always a function
            ok, res = self.proxy.results.get()
            if not ok:
                failure = cast('tuple[BaseException, str]', res)
                if isinstance(failure[0], IntegrityError):
                    raise IntegrityError(str(failure[0]))
                raise DatabaseException(*failure)
            return cast('R', res)

    return run


class ConnectionProxy:
    # The bodies of the methods decorated with @proxy are never executed, the
    # decorator runs the method of the same name on the sqlite Connection
    # object in the DBThread instead.

    def __init__(self, proxy: DBThread) -> None:
        self.proxy = proxy
        self.closed = False

    def close(self) -> None:
        if self.proxy.unhandled_error[0] is None:
            self.proxy.requests.put((self.proxy.CLOSE, [], {}))
            self.closed = True

    @overload
    def get(self, sql: str, bindings: SQLBindings = ..., /, *, all: Literal[True] = True) -> list[SQLRow]: ...
    @overload
    def get(self, sql: str, bindings: SQLBindings = ..., /, *, all: Literal[False]) -> SQLValue: ...
    @overload
    def get(self, sql: str, bindings: SQLBindings = ..., /, *, all: bool) -> list[SQLRow] | SQLValue: ...
    @proxy
    def get(self, sql: str, bindings: SQLBindings = (), /, *, all: bool = True) -> list[SQLRow] | SQLValue:
        raise NotImplementedError()

    @proxy
    def commit(self) -> None:
        raise NotImplementedError()

    @proxy
    def execute(self, sql: str, bindings: SQLBindings = (), /) -> sqlite.Cursor:
        raise NotImplementedError()

    @proxy
    def executemany(self, sql: str, seq_of_bindings: Iterable[SQLBindings], /) -> sqlite.Cursor:
        raise NotImplementedError()

    @proxy
    def executescript(self, sql_script: str, /) -> sqlite.Cursor:
        raise NotImplementedError()

    @proxy
    def create_aggregate(self, name: str, n_arg: int, aggregate_class: Callable[[], object], /) -> None:
        raise NotImplementedError()

    @proxy
    def create_function(self, name: str, narg: int, func: Callable[..., object] | None, /) -> None:
        raise NotImplementedError()

    @proxy
    def cursor(self) -> sqlite.Cursor:
        raise NotImplementedError()

    @proxy
    def dump(self) -> tuple[str, ...]:
        raise NotImplementedError()

    @proxy
    def create_dynamic_filter(self, name: str, /) -> DynamicFilter:
        raise NotImplementedError()


def connect(dbpath: str, row_factory: bool | None = None) -> ConnectionProxy:
    conn = ConnectionProxy(DBThread(dbpath, row_factory))
    conn.proxy.start()
    while conn.proxy.unhandled_error[0] is None and conn.proxy.conn is None:
        time.sleep(0.01)
    if conn.proxy.unhandled_error[0] is not None:
        raise DatabaseException(*conn.proxy.unhandled_error)
    return conn


def test() -> None:
    c = sqlite.connect(':memory:')
    if load_c_extensions(c, True):
        print('Loaded C extension successfully')
