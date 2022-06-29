#!/usr/bin/env python
# License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import builtins
import os
import sys
import tempfile
from apsw import Connection

from calibre.constants import plugins
from calibre.db.annotations import unicode_normalize
from calibre.db.tests.base import BaseTest


def print(*args, **kwargs):
    kwargs['file'] = sys.__stdout__
    builtins.print(*args, **kwargs)


class TestConn(Connection):

    def __init__(self, remove_diacritics=True, language='en', stem_words=False):
        from calibre_extensions.sqlite_extension import set_ui_language
        set_ui_language(language)
        super().__init__(':memory:')
        plugins.load_apsw_extension(self, 'sqlite_extension')
        options = []
        options.append('remove_diacritics'), options.append('2' if remove_diacritics else '0')
        options = ' '.join(options)
        tok = 'porter ' if stem_words else ''
        self.execute(f'''
CREATE VIRTUAL TABLE fts_table USING fts5(t, tokenize = '{tok}unicode61 {options}');
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
    from calibre_extensions.sqlite_extension import FTS5_TOKENIZE_DOCUMENT, tokenize
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
        from calibre_extensions.sqlite_extension import set_ui_language

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
        tt('你叫abc', '你', '叫', 'abc')
        tt('a你b叫什么名字', 'a', '你', 'b', '叫', '什么', '名字')

        for lang in 'de fr es sv it en'.split():
            set_ui_language(lang)
            tt("don't 'its' wörds", "don't", 'its', 'wörds', 'words')
            tt("l'hospital", "l'hospital")
            tt("x'bug'", "x'bug")
        set_ui_language('en')
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
        self.ae(conn.search("叫"), [("你don't>叫<mess",)])
    # }}}

    def test_fts_stemming(self):  # {{{
        from calibre_extensions.sqlite_extension import stem

        self.ae(stem('run'), 'run')
        self.ae(stem('connection'), 'connect')
        self.ae(stem('maintenaient'), 'maintenai')
        self.ae(stem('maintenaient', 'fr'), 'mainten')
        self.ae(stem('continué', 'fr'), 'continu')
        self.ae(stem('maître', 'FRA'), 'maîtr')

        conn = TestConn(stem_words=True)
        conn.insert_text('a simplistic connection')
        self.ae(conn.term_row_counts(), {'a': 1, 'connect': 1, 'simplist': 1})
        self.ae(conn.search("connection"), [('a simplistic >connection<',),])
        self.ae(conn.search("connect"), [('a simplistic >connection<',),])
        self.ae(conn.search("simplistic connect"), [('a >simplistic< >connection<',),])
        self.ae(conn.search("simplist"), [('a >simplistic< connection',),])

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

    def test_pdftotext(self):
        pdf_data = '''\
%PDF-1.1
%¥±ë

1 0 obj
  << /Type /Catalog
     /Pages 2 0 R
  >>
endobj

2 0 obj
  << /Type /Pages
     /Kids [3 0 R]
     /Count 1
     /MediaBox [0 0 300 144]
  >>
endobj

3 0 obj
  <<  /Type /Page
      /Parent 2 0 R
      /Resources
       << /Font
           << /F1
               << /Type /Font
                  /Subtype /Type1
                  /BaseFont /Times-Roman
               >>
           >>
       >>
      /Contents 4 0 R
  >>
endobj

4 0 obj
  << /Length 55 >>
stream
  BT
    /F1 18 Tf
    0 0 Td
    (Hello World) Tj
  ET
endstream
endobj

xref
0 5
0000000000 65535 f
0000000018 00000 n
0000000077 00000 n
0000000178 00000 n
0000000457 00000 n
trailer
  <<  /Root 1 0 R
      /Size 5
  >>
startxref
565
%%EOF'''
        with tempfile.TemporaryDirectory() as tdir:
            pdf = os.path.join(tdir, 'test.pdf')
            with open(pdf, 'w') as f:
                f.write(pdf_data)
            from calibre.db.fts.text import pdftotext
            self.assertEqual(pdftotext(pdf).strip(), 'Hello World')


def find_tests():
    import unittest
    return unittest.defaultTestLoader.loadTestsFromTestCase(FTSTest)


def run_tests():
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
