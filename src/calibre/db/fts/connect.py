#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import builtins
import hashlib
import os
import sys
from contextlib import suppress

from calibre.utils.date import EPOCH, utcnow

from .pool import Pool
from .schema_upgrade import SchemaUpgrade

# TODO: check that closing of db connection works
# TODO: db dump+restore
# TODO: calibre export/import
# TODO: check library and vacuuming of fts db


def print(*args, **kwargs):
    kwargs['file'] = sys.__stdout__
    builtins.print(*args, **kwargs)


class FTS:

    def __init__(self, dbref):
        self.dbref = dbref
        self.pool = Pool(dbref)

    def initialize(self, conn):
        main_db_path = os.path.abspath(conn.db_filename('main'))
        dbpath = os.path.join(os.path.dirname(main_db_path), 'full-text-search.db')
        conn.execute(f'ATTACH DATABASE "{dbpath}" AS fts_db')
        SchemaUpgrade(conn)
        conn.fts_dbpath = dbpath
        conn.execute('UPDATE fts_db.dirtied_formats SET in_progress=FALSE WHERE in_progress=TRUE')

    def get_connection(self):
        db = self.dbref()
        if db is None:
            raise RuntimeError('db has been garbage collected')
        ans = db.backend.get_connection()
        if ans.fts_dbpath is None:
            self.initialize(ans)
        return ans

    def dirty_existing(self):
        conn = self.get_connection()
        conn.execute('''
            INSERT OR IGNORE INTO fts_db.dirtied_formats(book, format)
            SELECT book, format FROM main.data;
        ''')

    def all_currently_dirty(self):
        conn = self.get_connection()
        return conn.get('''SELECT book, format from fts_db.dirtied_formats''', all=True)

    def clear_all_dirty(self):
        conn = self.get_connection()
        conn.execute('DELETE FROM fts_db.dirtied_formats')

    def remove_dirty(self, book_id, fmt):
        conn = self.get_connection()
        conn.execute('DELETE FROM fts_db.dirtied_formats WHERE book=? AND format=?', (book_id, fmt.upper()))

    def add_text(self, book_id, fmt, text, text_hash='', fmt_size=0, fmt_hash=''):
        conn = self.get_connection()
        ts = (utcnow() - EPOCH).total_seconds()
        fmt = fmt.upper()
        if text:
            conn.execute(
                'INSERT OR REPLACE INTO fts_db.books_text '
                '(book, timestamp, format, format_size, format_hash, searchable_text, text_size, text_hash) VALUES '
                '(?, ?, ?, ?, ?, ?, ?, ?)', (
                    book_id, ts, fmt, fmt_size, fmt_hash, text, len(text), text_hash))
        else:
            conn.execute('DELETE FROM fts_db.dirtied_formats WHERE book=? AND format=?', (book_id, fmt))

    def get_next_fts_job(self):
        conn = self.get_connection()
        for book_id, fmt in conn.get('SELECT book,format FROM fts_db.dirtied_formats WHERE in_progress=FALSE ORDER BY id'):
            return book_id, fmt
        return None, None

    def commit_result(self, book_id, fmt, fmt_size, fmt_hash, text, err_msg=''):
        conn = self.get_connection()
        text_hash = ''
        if text:
            text_hash = hashlib.sha1(text.encode('utf-8')).hexdigest()
            for x in conn.get('SELECT id FROM fts_db.books_text WHERE book=? AND format=? AND text_hash=?', (book_id, fmt, text_hash)):
                text = ''
                break
        self.add_text(book_id, fmt, text, text_hash, fmt_size, fmt_hash)

    def queue_job(self, book_id, fmt, path, fmt_size, fmt_hash):
        conn = self.get_connection()
        fmt = fmt.upper()
        for x in conn.get('SELECT id FROM fts_db.books_text WHERE book=? AND format=? AND format_size=? AND format_hash=?', (
                book_id, fmt, fmt_size, fmt_hash)):
            break
        else:
            self.pool.add_job(book_id, fmt, path, fmt_size, fmt_hash)
            conn.execute('UPDATE fts_db.dirtied_formats SET in_progress=TRUE WHERE book=? AND format=?', (book_id, fmt))
            return True
        self.remove_dirty(book_id, fmt)
        with suppress(OSError):
            os.remove(path)
        return False

    def shutdown(self):
        self.pool.shutdown()
