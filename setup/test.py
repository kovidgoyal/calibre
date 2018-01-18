#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import unittest

from setup import Command

TEST_MODULES = frozenset('srv db polish opf css docx cfi matcher icu smartypants build misc dbcli'.split())


def find_tests(which_tests=None):
    ans = []
    a = ans.append

    def ok(x):
        return not which_tests or x in which_tests

    if ok('build'):
        from calibre.test_build import find_tests
        a(find_tests())
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
    if ok('misc'):
        from calibre.ebooks.metadata.tag_mapper import find_tests
        a(find_tests())
        from calibre.utils.shared_file import find_tests
        a(find_tests())
        from calibre.utils.test_lock import find_tests
        a(find_tests())
        from calibre.utils.search_query_parser_test import find_tests
        a(find_tests())
    if ok('dbcli'):
        from calibre.db.cli.tests import find_tests
        a(find_tests())

    tests = unittest.TestSuite(ans)
    return tests


class Test(Command):

    description = 'Run the calibre test suite'

    def add_options(self, parser):
        parser.add_option('--test-module', '--test-group', default=[], action='append', type='choice', choices=sorted(map(str, TEST_MODULES)),
                          help='The test module to run (can be specified more than once for multiple modules). Choices: %s' % ', '.join(sorted(TEST_MODULES)))
        parser.add_option('--test-verbosity', type=int, default=4, help='Test verbosity (0-4)')
        parser.add_option('--test-name', default=[], action='append',
                          help='The name of an individual test to run. Can be specified more than once for multiple tests. The name of the'
                          ' test is the name of the test function without the leading test_. For example, the function test_something()'
                          ' can be run by specifying the name "something".')

    def run(self, opts):
        from calibre.utils.run_tests import run_cli, filter_tests_by_name
        tests = find_tests(which_tests=frozenset(opts.test_module))
        if opts.test_name:
            tests = filter_tests_by_name(tests, *opts.test_name)
        run_cli(tests, verbosity=opts.test_verbosity)
