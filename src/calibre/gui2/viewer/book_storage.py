#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Persistence for the per book storage used to implement localStorage for
# scripts in books. The storage is always saved in a file in the viewer config
# directory keyed by the path to the book, and additionally in the calibre
# library for books that are in a library. See calibre.db.book_storage

import json
import os
import sys
from functools import lru_cache
from queue import Queue, ShutDown
from threading import Thread
from typing import TypedDict

from calibre.db.book_storage import BookStorageEntry, InvalidBookStorage, new_book_storage_entry, newest_book_storage, validate_book_storage
from calibre.utils.filenames import atomic_rename


class CalibreData(TypedDict):
    library_id: str | None
    book_id: int | None
    book_fmt: str | None


class SaveRequest(TypedDict):
    entry: BookStorageEntry
    path_key: str
    book_library_details: dict[str, object] | None
    sync_annots_user: str
    calibre_data: CalibreData


@lru_cache(maxsize=2)
def book_storage_dir() -> str:
    from calibre.gui2.viewer.web_view import viewer_config_dir

    return os.path.join(viewer_config_dir, 'book-storage')


def book_storage_path(path_key: str, base: str | None = None) -> str:
    return os.path.join(base or book_storage_dir(), path_key + '.json')


def load_book_storage_from_file(path_key: str, base: str | None = None) -> BookStorageEntry | None:
    path = book_storage_path(path_key, base)
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except FileNotFoundError:
        return None
    try:
        return validate_book_storage(json.loads(raw))
    except (ValueError, InvalidBookStorage) as err:
        print(f'Ignoring invalid book storage in {path} with error: {err}', file=sys.stderr)
        return None


def save_book_storage_to_file(path_key: str, entry: BookStorageEntry, base: str | None = None) -> None:
    path = book_storage_path(path_key, base)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(json.dumps(entry, ensure_ascii=False).encode('utf-8'))
    atomic_rename(tmp, path)


def load_book_storage(
    path_key: str,
    book_library_details: dict[str, object] | None,
    sync_annots_user: str = '',
    calibre_book_data: dict[str, object] | None = None,
) -> BookStorageEntry:
    """
    Return the newest of the storage entries for the book from the local file
    and the calibre library. calibre_book_data is present when the viewer is
    launched from calibre and contains the storage read from the library by
    calibre.
    """
    from calibre.gui2.viewer.integration import load_book_storage_from_library

    candidates = [load_book_storage_from_file(path_key)]
    if calibre_book_data is not None:
        raw = calibre_book_data.get('book_storage')
        if raw is not None:
            try:
                candidates.append(validate_book_storage(raw))
            except InvalidBookStorage as err:
                print(f'Ignoring invalid book storage from calibre with error: {err}', file=sys.stderr)
    elif book_library_details is not None:
        candidates.append(load_book_storage_from_library(book_library_details))
        if sync_annots_user:
            candidates.append(load_book_storage_from_library(book_library_details, user_type='web', user=sync_annots_user))
    return newest_book_storage(*candidates) or new_book_storage_entry(timestamp=0)


def save_book_storage(req: SaveRequest) -> None:
    from calibre.gui2.viewer.integration import save_book_storage_to_library

    save_book_storage_to_file(req['path_key'], req['entry'])
    if (bld := req['book_library_details']) is not None:
        save_book_storage_to_library(bld, req['entry'], req['sync_annots_user'], calibre_data=req['calibre_data'])


class BookStorageSaveWorker(Thread):
    """
    Save book storage in a background thread. When multiple save requests for
    the same book are queued, only the most recent one is saved.
    """

    def __init__(self):
        Thread.__init__(self, name='BookStorageSaveWorker')
        self.daemon = True
        self.queue: Queue[SaveRequest] = Queue()

    def shutdown(self) -> None:
        self.queue.shutdown(immediate=False)
        self.join()

    def run(self) -> None:
        while True:
            try:
                pending = {}
                req = self.queue.get()
                pending[req['path_key']] = req
                while not self.queue.empty():
                    req = self.queue.get_nowait()
                    pending[req['path_key']] = req
            except ShutDown:
                if not pending:
                    break
            for req in pending.values():
                try:
                    save_book_storage(req)
                except Exception:
                    import traceback

                    traceback.print_exc()

    def save(
        self,
        entry: BookStorageEntry,
        path_key: str,
        book_library_details: dict[str, object] | None,
        sync_annots_user: str = '',
        calibre_data: CalibreData | None = None,
    ) -> None:
        self.queue.put({
            'entry': entry,
            'path_key': path_key,
            'book_library_details': book_library_details,
            'sync_annots_user': sync_annots_user,
            'calibre_data': calibre_data or {'library_id': None, 'book_id': None, 'book_fmt': None},
        })


def find_tests():
    import shutil
    import unittest
    from unittest.mock import patch

    import apsw

    from calibre.db.tests.base import BaseTest
    from calibre.gui2.viewer.integration import load_book_storage_from_library, save_book_storage_to_library

    class BookStorageTest(BaseTest):
        def setUp(self):
            super().setUp()
            self.storage_dir = self.mkdtemp()
            p = patch(f'{__name__}.book_storage_dir', lambda: self.storage_dir)
            p.start()
            self.addCleanup(p.stop)
            # Upgrade the library database so that it has the book_storage table
            self.init_cache().close()

        def bld(self, book_id=1, fmt='FMT1'):
            return {'dbpath': os.path.join(self.library_path, 'metadata.db'), 'book_id': book_id, 'fmt': fmt, 'library_id': 'test'}

        def req(self, entry, path_key='key', bld=None, sync_annots_user=''):
            return {
                'entry': entry,
                'path_key': path_key,
                'book_library_details': bld,
                'sync_annots_user': sync_annots_user,
                'calibre_data': {'library_id': None, 'book_id': None, 'book_fmt': None},
            }

        def test_book_storage_file(self):
            self.assertIsNone(load_book_storage_from_file('missing'))
            e = new_book_storage_entry({'a': 'b', 'ü': '\U0001f600'}, 3)
            save_book_storage_to_file('key', e)
            self.assertEqual(load_book_storage_from_file('key'), e)
            self.assertEqual(os.listdir(self.storage_dir), ['key.json'])
            with open(book_storage_path('bad'), 'w') as f:
                f.write('{"timestamp": 1, "data": {"a": 1}}')
            self.assertIsNone(load_book_storage_from_file('bad'))
            # No storage anywhere gives an empty entry with a zero timestamp
            self.assertEqual(load_book_storage('missing', None), new_book_storage_entry(timestamp=0))
            self.assertEqual(load_book_storage('key', None), e)

        def test_book_storage_library(self):
            bld = self.bld()
            # Libraries last opened with an older version of calibre are ignored
            old_library = self.bld()
            old_library['dbpath'] = os.path.join(self.mkdtemp(), 'metadata.db')
            shutil.copyfile(bld['dbpath'], old_library['dbpath'])
            conn = apsw.Connection(old_library['dbpath'])
            conn.execute('DROP TABLE book_storage; PRAGMA user_version=27')
            conn.close()
            save_book_storage_to_library(old_library, new_book_storage_entry({'a': 'b'}))
            self.assertIsNone(load_book_storage_from_library(old_library))
            self.assertIsNone(load_book_storage_from_library(bld))
            e1 = new_book_storage_entry({'a': '1'}, 10)
            save_book_storage(self.req(e1, bld=bld, sync_annots_user='webuser'))
            self.assertEqual(load_book_storage_from_file('key'), e1)
            self.assertEqual(load_book_storage_from_library(bld), e1)
            self.assertEqual(load_book_storage_from_library(bld, user_type='web', user='webuser'), e1)
            self.assertIsNone(load_book_storage_from_library(self.bld(fmt='FMT2')))
            # The newest of the local file and the library wins
            e2 = new_book_storage_entry({'a': '2'}, 20)
            save_book_storage_to_file('key', e2)
            self.assertEqual(load_book_storage('key', bld), e2)
            e3 = new_book_storage_entry({'a': '3'}, 30)
            save_book_storage_to_library(bld, e3, 'webuser')
            self.assertEqual(load_book_storage('key', bld), e3)
            # Storage saved by the sync user, for example in the content server, is used
            e4 = new_book_storage_entry({'a': '4'}, 40)
            save_book_storage_to_library(self.bld(), e4)
            cache = self.init_cache()
            cache.update_book_storage_for_book(1, 'FMT1', new_book_storage_entry({'a': '5'}, 50), user_type='web', user='webuser')
            cache.close()
            self.assertEqual(load_book_storage('key', bld)['data'], {'a': '4'})
            self.assertEqual(load_book_storage('key', bld, 'webuser')['data'], {'a': '5'})
            # When launched from calibre, the storage read by calibre is used instead of the library
            self.assertEqual(load_book_storage('key', bld, 'webuser', {'book_storage': None}), e2)
            self.assertEqual(load_book_storage('key', bld, 'webuser', {'book_storage': {'timestamp': 100, 'data': {'c': 'd'}}})['data'], {'c': 'd'})
            self.assertEqual(load_book_storage('key', bld, 'webuser', {'book_storage': {'timestamp': 100, 'data': []}}), e2)

        def data(self, entry: BookStorageEntry | None) -> dict[str, str]:
            self.assertIsNotNone(entry)
            assert entry is not None
            return entry['data']

        def test_book_storage_save_worker(self):
            w = BookStorageSaveWorker()
            w.start()
            for i in range(10):
                w.save(new_book_storage_entry({'i': str(i)}, i), 'one', self.bld())
            w.save(new_book_storage_entry({'x': 'y'}, 1), 'two', None)
            w.shutdown()
            self.assertEqual(self.data(load_book_storage_from_file('one')), {'i': '9'})
            self.assertEqual(self.data(load_book_storage_from_library(self.bld())), {'i': '9'})
            self.assertEqual(self.data(load_book_storage_from_file('two')), {'x': 'y'})

    return unittest.TestLoader().loadTestsFromTestCase(BookStorageTest)
