#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
from contextlib import closing, suppress
from threading import RLock

import apsw

from calibre.prints import debug_print
from calibre.ptempfile import PersistentTemporaryFile, TemporaryDirectory

# Any plugins not running in the device thread must acquire this lock before
# trying to access the Kobo database.
kobo_db_lock = RLock()
INJECT_9P_ERROR = False


def row_factory(cursor: apsw.Cursor, row):
    return {k[0]: row[i] for i, k in enumerate(cursor.getdescription())}


def wal_path(path: str) -> str:
    return path + '-wal'


def copy_db(conn: apsw.Connection, dest_path: str):
    with suppress(AttributeError):  # need a new enough version of apsw
        conn.cache_flush()
    # checkpoint all WAL transactions into the main db file and truncate WAL file to zero
    conn.wal_checkpoint(mode=apsw.SQLITE_CHECKPOINT_TRUNCATE)
    with TemporaryDirectory() as tdir:
        tempdb = os.path.join(tdir, 'temp.sqlite')
        with closing(apsw.Connection(tempdb)) as dest, dest.backup('main', conn, 'main') as b:
            while not b.done:
                with suppress(apsw.BusyError, apsw.LockedError):
                    b.step()
        shutil.move(tempdb, dest_path)
        twal, dwal = wal_path(tempdb), wal_path(dest_path)
        if os.path.exists(twal):  # this should never happen as sqlite is supposed to delete -wal file when last connection to db is closed
            shutil.move(twal, dwal)
        else:
            with suppress(FileNotFoundError):
                os.remove(dwal)


class Database:

    def __init__(self, path_on_device: str):
        self.path_on_device = self.dbpath = path_on_device
        self.dbversion = 0
        def connect(path: str = path_on_device) -> None:
            if INJECT_9P_ERROR:
                raise apsw.IOError('Fake I/O error to test 9p codepath')
            with closing(apsw.Connection(path)) as conn:
                conn.setrowtrace(row_factory)
                cursor = conn.cursor()
                cursor.execute('SELECT version FROM dbversion')
                with suppress(StopIteration):
                    result = next(cursor)
                    self.dbversion = result['version']
                debug_print('Kobo database version: ', self.dbversion)
                self.dbpath = path
        self.needs_copy = True
        self.use_row_factory = True
        with kobo_db_lock:
            try:
                connect()
                self.needs_copy = False
            except apsw.IOError:
                debug_print(f'Kobo: I/O error connecting to {self.path_on_device} copying it into temporary storage and connecting there')
                with open(self.path_on_device, 'rb') as src, PersistentTemporaryFile(suffix='-kobo-db.sqlite') as dest:
                    shutil.copyfileobj(src, dest)
                wal = wal_path(self.path_on_device)
                if os.path.exists(wal):
                    shutil.copy2(wal, wal_path(dest.name))
                try:
                    connect(dest.name)
                except Exception:
                    os.remove(dest.name)
                    raise

    def __enter__(self) -> apsw.Connection:
        kobo_db_lock.acquire()
        self.conn = apsw.Connection(self.dbpath)
        if self.use_row_factory:
            self.conn.setrowtrace(row_factory)
        return self.conn.__enter__()

    def __exit__(self, exc_type, exc_value, tb) -> bool | None:
        try:
            with closing(self.conn):
                suppress_exception = self.conn.__exit__(exc_type, exc_value, tb)
                if self.needs_copy and (suppress_exception or (exc_type is None and exc_value is None and tb is None)):
                    copy_db(self.conn, self.path_on_device)
        finally:
            kobo_db_lock.release()
        return suppress_exception
