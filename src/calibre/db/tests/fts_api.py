#!/usr/bin/env python
# License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import builtins
import sys
from io import BytesIO

from calibre.db.tests.base import BaseTest


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
        fts = cache.backend.enable_fts()
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


def find_tests():
    import unittest
    return unittest.defaultTestLoader.loadTestsFromTestCase(FTSAPITest)


def run_tests():
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
