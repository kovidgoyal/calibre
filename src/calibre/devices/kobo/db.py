#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
from contextlib import closing, suppress

import apsw

from calibre.prints import debug_print
from calibre.ptempfile import PersistentTemporaryFile, TemporaryDirectory


def row_factory(cursor: apsw.Cursor, row):
    return {k[0]: row[i] for i, k in enumerate(cursor.getdescription())}


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
        dest_wal = dest_path + '-wal'
        if os.path.exists(dest_wal):  # truncate WAL file to zero
            open(dest_wal, 'w').close()


class Database:

    def __init__(self, path_on_device: str):
        self.path_on_device = self.dbpath = path_on_device
        self.dbversion = 0
        def connect(path: str = path_on_device) -> None:
            if path == path_on_device:
                raise apsw.IOError('xxx')
            with closing(apsw.Connection(path)) as conn:
                conn.setrowtrace(row_factory)
                cursor = conn.cursor()
                cursor.execute('SELECT version FROM dbversion')
                with suppress(StopIteration):
                    result = next(cursor)
                    self.dbversion = result['version']
                    debug_print('Database Version: ', self.dbversion)
                self.dbpath = path
        self.needs_copy = True
        self.use_row_factory = True
        try:
            connect()
            self.needs_copy = False
        except apsw.IOError:
            debug_print(f'Kobo: I/O error connecting to {self.path_on_device} copying it into temporary storage and connecting there')
            with open(self.path_on_device, 'rb') as src, PersistentTemporaryFile(suffix='-kobo-db.sqlite') as dest:
                shutil.copyfileobj(src, dest)
            wal = self.path_on_device + '-wal'
            if os.path.exists(wal):
                shutil.copy2(wal, dest.name + '-wal')
            try:
                connect(dest.name)
            except Exception:
                os.remove(dest.name)
                raise

    def __enter__(self) -> apsw.Connection:
        self.conn = apsw.Connection(self.dbpath)
        if self.use_row_factory:
            self.conn.setrowtrace(row_factory)
        return self.conn.__enter__()

    def __exit__(self, exc_type, exc_value, tb) -> bool | None:
        with closing(self.conn):
            suppress_exception = self.conn.__exit__(exc_type, exc_value, tb)
            if self.needs_copy and (suppress_exception or (exc_type is None and exc_value is None and tb is None)):
                copy_db(self.conn, self.path_on_device)
        return suppress_exception
