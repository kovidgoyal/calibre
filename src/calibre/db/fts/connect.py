#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import builtins
import os
import sys

from calibre.utils.date import EPOCH, utcnow

from .schema_upgrade import SchemaUpgrade

# TODO: db dump+restore
# TODO: calibre export/import
# TODO: check library and vacuuming of fts db


def print(*args, **kwargs):
    kwargs['file'] = sys.__stdout__
    builtins.print(*args, **kwargs)


class FTS:

    def __init__(self, get_connection):
        self.get_connection = get_connection
        conn = self.get_connection()
        main_db_path = os.path.abspath(conn.db_filename('main'))
        self.dbpath = os.path.join(os.path.dirname(main_db_path), 'full-text-search.db')
        conn.execute(f'ATTACH DATABASE "{self.dbpath}" AS fts_db')
        SchemaUpgrade(conn)

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
