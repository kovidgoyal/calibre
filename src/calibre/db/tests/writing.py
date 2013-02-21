#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest
from collections import namedtuple
from functools import partial

from calibre.utils.date import UNDEFINED_DATE
from calibre.db.tests.base import BaseTest

class WritingTest(BaseTest):

    @property
    def cloned_library(self):
        return self.clone_library(self.library_path)

    def create_getter(self, name, getter=None):
        if getter is None:
            ans = lambda db:partial(db.get_custom, label=name[1:],
                                       index_is_id=True)
        else:
            ans = lambda db:partial(getattr(db, getter), index_is_id=True)
        return ans

    def create_setter(self, name, setter=None):
        if setter is None:
            ans = lambda db:partial(db.set_custom, label=name[1:], commit=True)
        else:
            ans = lambda db:partial(getattr(db, setter), commit=True)
        return ans

    def create_test(self, name, vals, getter=None, setter=None ):
        T = namedtuple('Test', 'name vals getter setter')
        return T(name, vals, self.create_getter(name, getter),
                 self.create_setter(name, setter))

    def run_tests(self, tests):
        cl = self.cloned_library
        results = {}
        for test in tests:
            results[test] = []
            for val in test.vals:
                cache = self.init_cache(cl)
                cache.set_field(test.name, {1: val})
                cached_res = cache.field_for(test.name, 1)
                del cache
                db = self.init_old(cl)
                getter = test.getter(db)
                sqlite_res = getter(1)
                test.setter(db)(1, val)
                old_cached_res = getter(1)
                self.assertEqual(old_cached_res, cached_res,
                                 'Failed setting for %s with value %r, cached value not the same. Old: %r != New: %r'%(
                        test.name, val, old_cached_res, cached_res))
                db.refresh()
                old_sqlite_res = getter(1)
                self.assertEqual(old_sqlite_res, sqlite_res,
                    'Failed setting for %s, sqlite value not the same: %r != %r'%(
                        test.name, old_sqlite_res, sqlite_res))
                del db



    def test_one_one(self):
        'Test setting of values in one-one fields'
        tests = []
        for name, getter, setter in (
            ('pubdate', 'pubdate', 'set_pubdate'),
            ('timestamp', 'timestamp', 'set_timestamp'),
            ('#date', None, None)
        ):
            tests.append(self.create_test(
                name, ('2011-1-12', UNDEFINED_DATE, None), getter, setter))

        self.run_tests(tests)

def tests():
    return unittest.TestLoader().loadTestsFromTestCase(WritingTest)

def run():
    unittest.TextTestRunner(verbosity=2).run(tests())

if __name__ == '__main__':
    run()


