#!/usr/bin/env python
# License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import builtins
import sys

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
        cd = fts.all_currently_dirty()
        self.ae(len(cd), 3)
        fts.dirty_existing()
        self.ae(len(cd), 3)


def find_tests():
    import unittest
    return unittest.defaultTestLoader.loadTestsFromTestCase(FTSAPITest)


def run_tests():
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
