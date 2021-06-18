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


def tokenize(text, flags=None, remove_diacritics=True):
    from calibre_extensions.sqlite_extension import tokenize, FTS5_TOKENIZE_DOCUMENT
    if flags is None:
        flags = FTS5_TOKENIZE_DOCUMENT
    return tokenize(text, remove_diacritics, flags)


class FTSTest(BaseTest):
    ae = BaseTest.assertEqual

    def test_fts_tokenize(self):  # {{{
        def t(x, s, e, f=0):
            return {'text': x, 'start': s, 'end': e, 'flags': f}

        self.ae(
            tokenize("Some wörds"),
            [t('some', 0, 4), t('wörds', 5, 11), t('words', 5, 11, 1)]
        )
        self.ae(
            tokenize("don't 'bug'"),
            [t("don't", 0, 5), t('bug', 7, 10)]
        )
        self.ae(
            tokenize("a,b. c"),
            [t("a", 0, 1), t('b', 2, 3), t('c', 5, 6)]
        )
        self.ae(
            tokenize("a*b+c"),
            [t("a", 0, 1), t('b', 2, 3), t('c', 4, 5)]
        )
        self.ae(
            tokenize("a(b[{^c"),
            [t("a", 0, 1), t('b', 2, 3), t('c', 6, 7)]
        )
        self.ae(
            tokenize("a😀smile"),
            [t("a", 0, 1), t('😀', 1, 5), t('smile', 5, 10)]
        )
    # }}}

    def test_fts_basic(self):  # {{{
        conn = TestConn()
        conn.insert_text('two words, and a period. With another.')
        conn.insert_text('and another re-init')
        self.ae(conn.search("another"), [('and >another< re-init',), ('…With >another<.',)])
        self.ae(conn.search("period"), [('…a >period<. With another.',)])
        self.ae(conn.term_row_counts(), {'a': 1, 're': 1, 'init': 1, 'and': 2, 'another': 2, 'period': 1, 'two': 1, 'with': 1, 'words': 1})
        conn = TestConn()
        conn.insert_text('coộl')
        self.ae(conn.term_row_counts(), {'cool': 1, 'coộl': 1})
        self.ae(conn.search("cool"), [('>coộl<',)])
        self.ae(conn.search("coộl"), [('>coộl<',)])
        conn = TestConn(remove_diacritics=False)
        conn.insert_text('coộl')
        self.ae(conn.term_row_counts(), {'coộl': 1})
    # }}}
