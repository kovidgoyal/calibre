#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import unittest

from setup import Command

TEST_MODULES = frozenset('srv db polish opf css docx cfi matcher icu smartypants'.split())

def find_tests(which_tests=None):
    ans = []
    a = ans.append
    def ok(x):
        return not which_tests or x in which_tests

    if ok('srv'):
        from calibre.srv.tests.main import find_tests
        a(find_tests())
    if ok('db'):
        from calibre.db.tests.main import find_tests
        a(find_tests())
    if ok('polish'):
        from calibre.ebooks.oeb.polish.tests.main import find_tests
        a(find_tests())
    if ok('opf'):
        from calibre.ebooks.metadata.opf2 import suite
        a(suite())
        from calibre.ebooks.metadata.opf3_test import suite
        a(suite())
    if ok('css'):
        from tinycss.tests.main import find_tests
        a(find_tests())
        from calibre.ebooks.oeb.normalize_css import test_normalization
        a(test_normalization(return_tests=True))
        from calibre.ebooks.css_transform_rules import test
        a(test(return_tests=True))
        from css_selectors.tests import find_tests
        a(find_tests())
    if ok('docx'):
        from calibre.ebooks.docx.fields import test_parse_fields
        a(test_parse_fields(return_tests=True))
        from calibre.ebooks.docx.writer.utils import test_convert_color
        a(test_convert_color(return_tests=True))
    if ok('cfi'):
        from calibre.ebooks.epub.cfi.tests import find_tests
        a(find_tests())
    if ok('matcher'):
        from calibre.utils.matcher import test
        a(test(return_tests=True))
    if ok('icu'):
        from calibre.utils.icu_test import find_tests
        a(find_tests())
    if ok('smartypants'):
        from calibre.utils.smartypants import run_tests
        a(run_tests(return_tests=True))

    tests = unittest.TestSuite(ans)
    return tests

class Test(Command):

    def run(self, opts):
        from calibre.gui2 import ensure_app, load_builtin_fonts
        ensure_app(), load_builtin_fonts()
        r = unittest.TextTestRunner
        r(verbosity=2).run(find_tests())
