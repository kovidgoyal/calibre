#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import builtins
import os
import sys

from calibre.utils.date import EPOCH, utcnow

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

    def initialize(self, conn):
        main_db_path = os.path.abspath(conn.db_filename('main'))
        dbpath = os.path.join(os.path.dirname(main_db_path), 'full-text-search.db')
        conn.execute(f'ATTACH DATABASE "{dbpath}" AS fts_db')
        SchemaUpgrade(conn)
        conn.fts_dbpath = dbpath

    def get_connection(self):
        db = self.dbref()
        if db is None:
            raise RuntimeError('db has been garbage collected')
        ans = db.backend.conn
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
            conn.execute('DELETE FROM fts_db.dirtied_formats WHERE book=? and format=?', (book_id, fmt))
