#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.db.tests.base import BaseTest
from apsw import Connection
from calibre.constants import plugins


class TestConn(Connection):

    def __init__(self):
        super().__init__(':memory:')
        plugins.load_apsw_extension(self, 'sqlite_extension')
        self.cursor().execute("CREATE VIRTUAL TABLE fts_table USING fts5(t, tokenize = 'unicode61 remove_diacritics 2')")

    def insert_text(self, text):
        self.cursor().execute('INSERT INTO fts_table(t) VALUES (?)', (text,))


class FTSTest(BaseTest):

    def test_basic_fts(self):  # {{{
        conn = TestConn()
        conn.insert_text('two words, and a period. With another.')
    # }}}
