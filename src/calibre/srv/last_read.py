#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import os
from contextlib import suppress
from threading import Lock
from time import time_ns
from typing import TYPE_CHECKING, Literal, TypedDict, cast, overload

import apsw

from calibre.constants import cache_dir

if TYPE_CHECKING:
    from collections.abc import Iterable

    from apsw import Bindings, SQLiteValue, SQLiteValues


class RecentlyReadEntry(TypedDict):
    library_id: str
    book_id: int
    format: str
    cfi: str
    epoch: int
    pos_frac: float
    tooltip: str


creation_sql = '''
CREATE TABLE IF NOT EXISTS last_read_positions ( id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_id TEXT NOT NULL,
    book INTEGER NOT NULL,
    format TEXT NOT NULL COLLATE NOCASE,
    user TEXT NOT NULL,
    cfi TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    pos_frac REAL NOT NULL DEFAULT 0,
    tooltip TEXT NOT NULL,
    UNIQUE(user, library_id, book, format)
);
CREATE INDEX IF NOT EXISTS users_id ON last_read_positions (user);
'''

lock = Lock()


class LastReadCache:
    def __init__(self, path: str = '', limit: int = 5) -> None:
        self.limit = limit
        self.conn = apsw.Connection(path or os.path.join(cache_dir(), 'srv-last-read.sqlite'))
        self.execute(creation_sql)

    @overload
    def get(self, sql: str, bindings: Bindings | None = None, /, *, all: Literal[True] = True) -> list[SQLiteValues]: ...
    @overload
    def get(self, sql: str, bindings: Bindings | None = None, /, *, all: Literal[False]) -> SQLiteValue: ...
    @overload
    def get(self, sql: str, bindings: Bindings | None = None, /, *, all: bool) -> list[SQLiteValues] | SQLiteValue: ...
    def get(self, sql: str, bindings: Bindings | None = None, /, *, all: bool = True) -> list[SQLiteValues] | SQLiteValue:
        ans = self.conn.cursor().execute(sql, bindings)
        if all:
            return ans.fetchall()
        with suppress(StopIteration, IndexError):
            return next(ans)[0]

    def execute(self, sql: str, bindings: Bindings | None = None) -> apsw.Cursor:
        cursor = self.conn.cursor()
        return cursor.execute(sql, bindings)

    def add_last_read_position(self, library_id: str, book_id: int, fmt: str, user: str, cfi: str | None, pos_frac: float, tooltip: str) -> int | None:
        with lock, self.conn:
            if not cfi:
                self.execute(
                    'DELETE FROM last_read_positions WHERE library_id=? AND book=? AND format=? AND user=?',
                    (library_id, book_id, fmt, user),
                )
            else:
                epoch = time_ns()
                self.execute(
                    'INSERT OR REPLACE INTO last_read_positions(library_id,book,format,user,cfi,epoch,pos_frac,tooltip) VALUES (?,?,?,?,?,?,?,?)',
                    (library_id, book_id, fmt, user, cfi, epoch, pos_frac, tooltip),
                )
                items = tuple(self.get('SELECT id FROM last_read_positions WHERE user=? ORDER BY id DESC', (user,), all=True))
                if len(items) > self.limit:
                    self.execute('DELETE FROM last_read_positions WHERE user=? AND id <= ?', (user, items[self.limit][0]))
                return epoch

    def get_recently_read(self, user: str) -> list[RecentlyReadEntry]:
        with lock:
            ans: list[RecentlyReadEntry] = []
            for library_id, book, fmt, cfi, epoch, pos_frac, tooltip in cast(
                'Iterable[tuple[str, int, str, str, int, float, str]]',
                self.execute(
                    'SELECT library_id,book,format,cfi,epoch,pos_frac,tooltip FROM last_read_positions WHERE user=? ORDER BY epoch DESC',
                    (user,),
                ),
            ):
                ans.append({
                    'library_id': library_id,
                    'book_id': book,
                    'format': fmt,
                    'cfi': cfi,
                    'epoch': epoch,
                    'pos_frac': pos_frac,
                    'tooltip': tooltip,
                })
            return ans


path_cache: dict[str, LastReadCache] = {}


def last_read_cache(path: str = '') -> LastReadCache:
    with lock:
        ans = path_cache.get(path)
        if ans is None:
            ans = path_cache[path] = LastReadCache(path)
    return ans
