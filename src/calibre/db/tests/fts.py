#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import builtins
import sys
from apsw import Connection

from calibre.constants import plugins
from calibre.db.tests.base import BaseTest


def print(*args, **kwargs):
    kwargs['file'] = sys.__stdout__
    builtins.print(*args, **kwargs)


class TestConn(Connection):

    def __init__(self, remove_diacritics=True):
        super().__init__(':memory:')
        plugins.load_apsw_extension(self, 'sqlite_extension')
        options = []
        options.append('remove_diacritics'), options.append('2' if remove_diacritics else '0')
        options = ' '.join(options)
        self.execute(f'''
CREATE VIRTUAL TABLE fts_table USING fts5(t, tokenize = 'unicode61 {options}');
CREATE VIRTUAL TABLE fts_row USING fts5vocab(fts_table, row);
''')

    def execute(self, *a):
        return self.cursor().execute(*a)

    def insert_text(self, text):
        self.execute('INSERT INTO fts_table(t) VALUES (?)', (text,))

    def term_row_counts(self):
        return dict(self.execute('SELECT term,doc FROM fts_row'))

    def search(self, query, highlight_start='>', highlight_end='<', snippet_size=4):
        snippet_size=max(1, min(snippet_size, 64))
        stmt = (
            f'SELECT snippet(fts_table, 0, "{highlight_start}", "{highlight_end}", "…", {snippet_size})'
            ' FROM fts_table WHERE fts_table MATCH ? ORDER BY RANK'
        )
        return list(self.execute(stmt, (query,)))


class FTSTest(BaseTest):
    ae = BaseTest.assertEqual

    def test_basic_fts(self):  # {{{
        conn = TestConn()
        conn.insert_text('two words, and a period. With another.')
        conn.insert_text('and another re-init')
        self.ae(conn.search("another"), [('and >another< re-init',), ('…With >another<.',)])
        self.ae(conn.search("period"), [('…a >period<. With another.',)])
        self.ae(conn.term_row_counts(), {'a': 1, 're': 1, 'init': 1, 'and': 2, 'another': 2, 'period': 1, 'two': 1, 'with': 1, 'words': 1})
        conn = TestConn()
        conn.insert_text('coộl')
        self.ae(conn.term_row_counts(), {'cool': 1, 'coộl': 1})
        conn = TestConn(remove_diacritics=False)
        conn.insert_text('coộl')
        self.ae(conn.term_row_counts(), {'coộl': 1})
    # }}}
