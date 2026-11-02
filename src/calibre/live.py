#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import ast
import os
import re
import sys
import types
from compression import gzip
from contextlib import suppress
from datetime import datetime, timedelta
from enum import Enum, auto
from http import HTTPStatus
from importlib import import_module
from queue import Queue
from threading import Lock, Thread
from typing import TYPE_CHECKING, TypeGuard, cast

import apsw

from calibre.constants import cache_dir, numeric_version
from calibre.utils.date import utcnow
from calibre.utils.https import HTTPError, get_https_resource_securely
from calibre.utils.iso8601 import parse_iso8601

if TYPE_CHECKING:
    import unittest
    from collections.abc import Callable

download_queue: Queue[str | None] = Queue()
default_timeout = object()
DEFAULT_TIMEOUT = 5
worker: Thread | None = None
worker_lock = Lock()
fetcher: Callable[..., tuple[str, bytes] | tuple[None, None]] | None = None
db_path: str | None = None
old_interval = timedelta(days=1)
module_version = 1
minimum_calibre_version = 5, 7, 0


class Strategy(Enum):
    download_now = auto()
    download_if_old = auto()
    fast = auto()


def start_worker() -> None:
    global worker
    with worker_lock:
        if worker is None:
            worker = Thread(name='LiveDownloader', target=download_worker, daemon=True)
            worker.start()


def stop_worker(timeout: float | None = 2 * DEFAULT_TIMEOUT) -> None:
    global worker
    with worker_lock:
        if worker is not None:
            download_queue.put(None)
            w = worker
            worker = None
            w.join(timeout)


def async_stop_worker() -> Callable[[], None]:
    t = Thread(name='StopLiveDownloadWorker', target=stop_worker, daemon=True)
    t.start()
    return t.join


def report_failure(full_name: str) -> None:
    print(f'Failed to download live module {full_name}', file=sys.stderr)
    import traceback

    traceback.print_exc()


def download_worker() -> None:
    while True:
        x = download_queue.get()
        if x is None:
            break
        try:
            latest_data_for_module(x)
        except Exception:
            report_failure(x)


def queue_for_download(full_name: str) -> None:
    download_queue.put(full_name)


def parse_metadata(full_name: str, raw_bytes: bytes) -> tuple[int, tuple[int, int, int]]:
    q = raw_bytes[:2048]
    m = re.search(rb'^module_version\s*=\s*(\d+)', q, flags=re.MULTILINE)
    if m is None:
        raise ValueError(f'No module_version in downloaded source of {full_name}')
    module_version = int(m.group(1))

    m = re.search(rb'^minimum_calibre_version\s*=\s*(.+?)$', q, flags=re.MULTILINE)
    minimum_calibre_version = 0, 0, 0
    if m is not None:
        minimum_calibre_version = ast.literal_eval(m.group(1).decode('utf-8'))
        if (
            not isinstance(minimum_calibre_version, tuple)
            or len(minimum_calibre_version) != 3
            or not isinstance(minimum_calibre_version[0], int)
            or not isinstance(minimum_calibre_version[1], int)
            or not isinstance(minimum_calibre_version[2], int)
        ):
            raise ValueError(f'minimum_calibre_version invalid: {minimum_calibre_version!r}')

    return module_version, minimum_calibre_version


def fetch_module(full_name: str, etag: str | None = None, timeout: object = default_timeout, url: str | None = None) -> tuple[str, bytes] | tuple[None, None]:
    if timeout is default_timeout:
        timeout = DEFAULT_TIMEOUT
    if url is None:
        path = '/'.join(full_name.split('.')) + '.py'
        url = 'https://code.calibre-ebook.com/src/' + path
    headers = {'accept-encoding': 'gzip'}
    if etag:
        headers['if-none-match'] = f'"{etag}"'
    try:
        res = get_https_resource_securely(url, headers=headers, get_response=True, timeout=cast('float', timeout))
    except HTTPError as e:
        if e.code == HTTPStatus.NOT_MODIFIED:
            return None, None
        raise
    etag = res.headers['etag']
    etag = etag.removeprefix('W/')
    etag = etag[1:-1]
    if res.headers['content-encoding'] == 'gzip':
        data = gzip.GzipFile(fileobj=res).read()
    else:
        data = res.read()
    return etag, data


def cache_path() -> str:
    return db_path or os.path.join(cache_dir(), 'live.sqlite')


def db() -> apsw.Connection:
    ans = apsw.Connection(cache_path())
    ans.cursor().execute('pragma busy_timeout=2000')
    return ans


def table_definition() -> str:
    return '''
    CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            full_name TEXT NOT NULL UNIQUE,
            etag TEXT NOT NULL,
            module_version INTEGER NOT NULL DEFAULT 1,
            minimum_calibre_version TEXT NOT NULL DEFAULT "0,0,0",
            data BLOB NOT NULL
    );
    '''


def write_to_cache(full_name: str, etag: str, data: bytes) -> None:
    module_version, minimum_calibre_version = parse_metadata(full_name, data)
    mcv = ','.join(map(str, minimum_calibre_version))
    db().cursor().execute(
        table_definition() + 'INSERT OR REPLACE INTO modules (full_name, etag, data, date, atime, module_version, minimum_calibre_version)'
        ' VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?)',
        (full_name, etag, data, module_version, mcv),
    )


def read_from_cache(full_name: str) -> tuple[str | None, bytes | None, datetime | None]:
    rowid = etag = data = date = None
    c = db().cursor()
    with suppress(StopIteration):
        rowid, etag, data, date = next(c.execute(table_definition() + 'SELECT id, etag, data, date FROM modules WHERE full_name=? LIMIT 1', (full_name,)))
    if rowid is not None:
        with suppress(apsw.BusyError):
            c.execute('UPDATE modules SET atime=CURRENT_TIMESTAMP WHERE id=?', (rowid,))
    if date is not None:
        date = parse_iso8601(date, assume_utc=True)
    return etag, data, date


def clear_cache() -> None:
    db().cursor().execute(table_definition() + 'DELETE FROM modules')


def load_module_from_data(full_name: str, data: bytes) -> types.ModuleType:
    m = import_module(full_name)
    ans = types.ModuleType(m.__name__)
    ans.__package__ = m.__package__
    ans.__file__ = m.__file__
    compiled = compile(data, full_name, 'exec', dont_inherit=True)
    exec(compiled, ans.__dict__)
    return ans


def latest_data_for_module(full_name: str, timeout: object = default_timeout) -> bytes | None:
    cached_etag, cached_data = read_from_cache(full_name)[:2]
    downloaded_etag, downloaded_data = (fetcher or fetch_module)(full_name, etag=cached_etag, timeout=timeout)
    if downloaded_data is not None:
        write_to_cache(full_name, cast('str', downloaded_etag), downloaded_data)
        cached_etag, cached_data = downloaded_etag, downloaded_data
    return cached_data


def download_module(full_name: str, timeout: object = default_timeout, strategy: Strategy = Strategy.download_now) -> types.ModuleType | None:
    if strategy is Strategy.download_now:
        return load_module_from_data(full_name, cast('bytes', latest_data_for_module(full_name, timeout=timeout)))
    cached_etag, cached_data, date = read_from_cache(full_name)
    if date is None or (utcnow() - date) > old_interval:
        return load_module_from_data(full_name, cast('bytes', latest_data_for_module(full_name, timeout=timeout)))
    if cached_data is not None:
        return load_module_from_data(full_name, cached_data)


def get_cached_module(full_name: str) -> types.ModuleType | None:
    cached_etag, cached_data = read_from_cache(full_name)[:2]
    if cached_data:
        return load_module_from_data(full_name, cached_data)


def cached_is_suitable(cached: types.ModuleType | None, installed: types.ModuleType) -> TypeGuard[types.ModuleType]:
    try:
        v = cast('types.ModuleType', cached).module_version
    except Exception:
        v = -1
    try:
        cv = cast('types.ModuleType', cached).minimum_calibre_version
    except Exception:
        cv = numeric_version
    return cv <= numeric_version and v > installed.module_version


def load_module(full_name: str, strategy: Strategy = Strategy.download_now, timeout: object = default_timeout) -> types.ModuleType:
    """
    Load the specified module from the calibre servers. strategy controls
    whether to check for the latest version immediately or eventually
    (strategies other that download_now).  Note that you must call
    start_worker() for eventual checking to work. Remember to call
    stop_worker() at exit as well.
    """
    installed = import_module(full_name)
    try:
        if strategy is Strategy.fast:
            cached = get_cached_module(full_name)
            queue_for_download(full_name)
        else:
            cached = download_module(full_name, timeout=timeout, strategy=strategy)
        if cached_is_suitable(cached, installed):
            installed = cached
    except Exception:
        report_failure(full_name)
    return installed


def find_tests() -> unittest.TestSuite:
    import hashlib
    import tempfile
    import unittest

    class LiveTest(unittest.TestCase):
        ae = unittest.TestCase.assertEqual

        def setUp(self) -> None:
            global db_path, fetcher
            fd, db_path = tempfile.mkstemp()
            os.close(fd)
            fetcher = self.fetch_module
            self.fetched_module_version = 99999
            self.sentinel_value = 1
            self.fetch_counter = 0
            self.orig_old_interval = old_interval

        @property
        def live_data(self) -> bytes:
            data = f'module_version = {self.fetched_module_version}\nminimum_calibre_version = (1, 2, 3)\nsentinel = {self.sentinel_value}'
            return data.encode('ascii')

        def fetch_module(self, full_name: str, etag: str | None = None, timeout: object = default_timeout) -> tuple[str, bytes] | tuple[None, None]:
            self.fetch_counter += 1
            data = self.live_data
            q = hashlib.md5(data).hexdigest()
            if etag and q == etag:
                return None, None
            return q, data

        def tearDown(self) -> None:
            global db_path, fetcher, old_interval
            if db_path:
                os.remove(db_path)
            db_path = fetcher = None
            old_interval = self.orig_old_interval

        def assert_cache_empty(self) -> None:
            self.ae(read_from_cache('live.test'), (None, None, None))

        def test_live_cache(self) -> None:
            self.assert_cache_empty()
            data = self.live_data
            write_to_cache('live.test', 'etag', data)
            self.ae(read_from_cache('live.test')[:2], ('etag', data))

        def test_module_loading(self) -> None:
            global old_interval
            self.assert_cache_empty()
            m = load_module('calibre.live', strategy=Strategy.fast)
            self.assertEqual(m.module_version, module_version)
            self.assert_cache_empty()
            self.ae(self.fetch_counter, 0)
            start_worker()
            stop_worker()
            self.ae(self.fetch_counter, 1)
            m = load_module('calibre.live', strategy=Strategy.fast)
            self.assertEqual(m.module_version, self.fetched_module_version)
            self.ae(self.fetch_counter, 1)
            m = load_module('calibre.live', strategy=Strategy.download_if_old)
            self.assertEqual(m.module_version, self.fetched_module_version)
            self.ae(self.fetch_counter, 1)
            m = load_module('calibre.live', strategy=Strategy.download_now)
            self.assertEqual(m.module_version, self.fetched_module_version)
            self.ae(self.fetch_counter, 2)
            old_interval = timedelta(days=-1)
            m = load_module('calibre.live', strategy=Strategy.download_if_old)
            self.assertEqual(m.module_version, self.fetched_module_version)
            self.ae(self.fetch_counter, 3)
            old_interval = self.orig_old_interval
            clear_cache()
            m = load_module('calibre.live', strategy=Strategy.download_if_old)
            self.assertEqual(m.module_version, self.fetched_module_version)
            self.ae(self.fetch_counter, 4)

    return unittest.defaultTestLoader.loadTestsFromTestCase(LiveTest)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
