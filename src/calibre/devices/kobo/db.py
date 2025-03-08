#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
from contextlib import closing, suppress

import apsw

from calibre.prints import debug_print
from calibre.ptempfile import PersistentTemporaryFile


def row_factory(cursor, row):
    return {k[0]: row[i] for i, k in enumerate(cursor.getdescription())}


def copy_db(conn: apsw.Connection, dest_path: str):
    conn.cache_flush()
    with PersistentTemporaryFile() as f:
        needs_remove = True
    try:
        with closing(apsw.Connection(f.name)) as dest, conn.backup('main', dest, 'main') as b:
            while not b.done:
                b.step()
        shutil.move(f.name, dest_path)
        needs_remove = False
    finally:
        if needs_remove:
            with suppress(OSError):
                os.remove(f.name)


class Database:

    def __init__(self, path_on_device: str):
        self.path_on_device = self.dbpath = path_on_device
        self.dbversion = 0
        def connect(path: str = path_on_device) -> None:
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
