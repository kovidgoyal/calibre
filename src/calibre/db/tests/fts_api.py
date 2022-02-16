#!/usr/bin/env python
# License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import builtins
import sys
from io import BytesIO

from calibre.db.tests.base import BaseTest
from calibre.db.fts.text import html_to_text


def print(*args, **kwargs):
    kwargs['file'] = sys.__stdout__
    builtins.print(*args, **kwargs)


class FTSAPITest(BaseTest):
    ae = BaseTest.assertEqual

    def setUp(self):
        super().setUp()
        from calibre_extensions.sqlite_extension import set_ui_language
        set_ui_language('en')

    def tearDown(self):
        super().tearDown()
        from calibre_extensions.sqlite_extension import set_ui_language
        set_ui_language('en')

    def test_fts_triggers(self):
        cache = self.init_cache()
        fts = cache.enable_fts()
        self.ae(fts.all_currently_dirty(), [(1, 'FMT1'), (1, 'FMT2'), (2, 'FMT1')])
        fts.dirty_existing()
        self.ae(fts.all_currently_dirty(), [(1, 'FMT1'), (1, 'FMT2'), (2, 'FMT1')])
        cache.remove_formats({2: ['FMT1']})
        self.ae(fts.all_currently_dirty(), [(1, 'FMT1'), (1, 'FMT2')])
        cache.remove_books((1,))
        self.ae(fts.all_currently_dirty(), [])
        cache.add_format(2, 'ADDED', BytesIO(b'data'))
        self.ae(fts.all_currently_dirty(), [(2, 'ADDED')])
        fts.clear_all_dirty()
        self.ae(fts.all_currently_dirty(), [])
        cache.add_format(2, 'ADDED', BytesIO(b'data2'))
        self.ae(fts.all_currently_dirty(), [(2, 'ADDED')])
        fts.add_text(2, 'ADDED', 'data2')
        self.ae(fts.all_currently_dirty(), [])
        cache.add_format(2, 'ADDED', BytesIO(b'data2'))
        self.ae(fts.all_currently_dirty(), [(2, 'ADDED')])
        fts.add_text(2, 'ADDED', 'data2')
        self.ae(fts.all_currently_dirty(), [])
        fts.dirty_existing()
        j = fts.get_next_fts_job()
        self.ae(j, (2, 'ADDED'))
        self.ae(j, fts.get_next_fts_job())
        fts.remove_dirty(*j)
        self.assertNotEqual(j, fts.get_next_fts_job())

    def test_fts_to_text(self):
        from calibre.ebooks.oeb.polish.parsing import parse
        html = '''
<html><body>
<div>first_para</div><p>second_para</p>
<p>some <i>itali</i>c t<!- c -->ext</p>
<div>nested<p>blocks</p></div>
</body></html>
'''
        root = parse(html)
        self.ae(tuple(html_to_text(root)), ('first_para\n\nsecond_para\n\nsome italic text\n\nnested\n\nblocks',))


def find_tests():
    import unittest
    return unittest.defaultTestLoader.loadTestsFromTestCase(FTSAPITest)


def run_tests():
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
