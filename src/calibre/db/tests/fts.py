#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import builtins
import sys
from apsw import Connection

from calibre.constants import plugins
from calibre.db.tests.base import BaseTest
from calibre.db.annotations import unicode_normalize


def print(*args, **kwargs):
    kwargs['file'] = sys.__stdout__
    builtins.print(*args, **kwargs)


class TestConn(Connection):

    def __init__(self, remove_diacritics=True, language='en'):
        from calibre_extensions.sqlite_extension import set_ui_language
        set_ui_language(language)
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
        self.execute('INSERT INTO fts_table(t) VALUES (?)', (unicode_normalize(text),))

    def term_row_counts(self):
        return dict(self.execute('SELECT term,doc FROM fts_row'))

    def search(self, query, highlight_start='>', highlight_end='<', snippet_size=4):
        snippet_size=max(1, min(snippet_size, 64))
        stmt = (
            f'SELECT snippet(fts_table, 0, "{highlight_start}", "{highlight_end}", "…", {snippet_size})'
            ' FROM fts_table WHERE fts_table MATCH ? ORDER BY RANK'
        )
        return list(self.execute(stmt, (unicode_normalize(query),)))


def tokenize(text, flags=None, remove_diacritics=True):
    from calibre_extensions.sqlite_extension import tokenize, FTS5_TOKENIZE_DOCUMENT
    if flags is None:
        flags = FTS5_TOKENIZE_DOCUMENT
    return tokenize(unicode_normalize(text), remove_diacritics, flags)


class FTSTest(BaseTest):
    ae = BaseTest.assertEqual

    def setUp(self):
        from calibre_extensions.sqlite_extension import set_ui_language
        set_ui_language('en')

    def tearDown(self):
        from calibre_extensions.sqlite_extension import set_ui_language
        set_ui_language('en')

    def test_fts_tokenize(self):  # {{{
        def t(x, s, e, f=0):
            return {'text': x, 'start': s, 'end': e, 'flags': f}

        def tt(text, *expected_tokens):
            q = tuple(x['text'] for x in tokenize(text))
            self.ae(q, expected_tokens)

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

        tt('你叫什么名字', '你', '叫', '什么', '名字')
        tt('a你b叫什么名字', 'a', '你', 'b', '叫', '什么', '名字')
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

        conn = TestConn()
        conn.insert_text("你don't叫mess")
        self.ae(conn.search("mess"), [("你don't叫>mess<",)])
        self.ae(conn.search('''"don't"'''), [("你>don't<叫mess",)])
        self.ae(conn.search("你"), [(">你<don't叫mess",)])
    # }}}

    def test_fts_query_syntax(self):  # {{{
        conn = TestConn()
        conn.insert_text('one two three')
        for q in ('"one two three"', 'one + two + three', '"one two" + three'):
            self.ae(conn.search(q), [('>one two three<',)])
        self.ae(conn.search('two'), [('one >two< three',)])
        for q in ('"one two thr" *', 'one + two + thr*'):
            self.ae(conn.search(q), [('>one two three<',)])
        self.ae(conn.search('^one'), [('>one< two three',)])
        self.ae(conn.search('^"one"'), [('>one< two three',)])
        self.ae(conn.search('^two'), [])
        conn = TestConn()
        conn.insert_text('one two three four five six seven')
        self.ae(conn.search('NEAR(one four)'), [('>one< two three >four<…',)])
        self.ae(conn.search('NEAR("one two" "three four")'), [('>one two< >three four<…',)])
        self.ae(conn.search('NEAR(one six, 2)'), [])

        conn.insert_text('moose cat')
        self.ae(conn.search('moose OR one'), [('>moose< cat',), ('>one< two three four…',)])
        self.ae(conn.search('(moose OR one) NOT cat'), [('>one< two three four…',)])
        self.ae(conn.search('moose AND one'), [])

    # }}}


def find_tests():
    import unittest
    return unittest.defaultTestLoader.loadTestsFromTestCase(FTSTest)


def run_tests():
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
