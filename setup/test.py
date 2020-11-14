#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os
import unittest

from setup import Command, islinux, ismacos, iswindows, SRC

TEST_MODULES = frozenset('srv db polish opf css docx cfi matcher icu smartypants build misc dbcli ebooks'.split())


class TestImports(unittest.TestCase):

    def base_check(self, base, exclude_packages, exclude_modules):
        import importlib
        import_base = os.path.dirname(base)
        count = 0
        for root, dirs, files in os.walk(base):
            for d in tuple(dirs):
                if not os.path.isfile(os.path.join(root, d, '__init__.py')):
                    dirs.remove(d)
            for fname in files:
                module_name, ext = os.path.splitext(fname)
                if ext != '.py':
                    continue
                path = os.path.join(root, module_name)
                relpath = os.path.relpath(path, import_base).replace(os.sep, '/')
                full_module_name = '.'.join(relpath.split('/'))
                if full_module_name.endswith('.__init__'):
                    full_module_name = full_module_name.rpartition('.')[0]
                if full_module_name in exclude_modules or ('.' in full_module_name and full_module_name.rpartition('.')[0] in exclude_packages):
                    continue
                importlib.import_module(full_module_name)
                count += 1
        return count

    def test_import_of_all_python_modules(self):
        exclude_modules = {'calibre.gui2.dbus_export.demo', 'calibre.gui2.dbus_export.gtk'}
        exclude_packages = {'calibre.devices.mtp.unix.upstream'}
        if not iswindows:
            exclude_modules |= {'calibre.utils.iphlpapi', 'calibre.utils.open_with.windows', 'calibre.devices.winusb'}
            exclude_packages |= {'calibre.utils.winreg', 'calibre.utils.windows'}
        if not ismacos:
            exclude_modules.add('calibre.utils.open_with.osx')
        if not islinux:
            exclude_modules |= {
                    'calibre.utils.dbus_service', 'calibre.linux',
                    'calibre.utils.linux_trash', 'calibre.utils.open_with.linux',
                    'calibre.gui2.linux_file_dialogs'
            }
            exclude_packages.add('calibre.gui2.dbus_export')
        self.assertGreater(self.base_check(os.path.join(SRC, 'odf'), exclude_packages, exclude_modules), 10)
        base = os.path.join(SRC, 'calibre')
        self.assertGreater(self.base_check(base, exclude_packages, exclude_modules), 1000)

        import calibre.web.feeds.feedparser as f
        del f
        from calibre.ebooks.markdown import Markdown
        del Markdown


def find_tests(which_tests=None, exclude_tests=None):
    ans = []
    a = ans.append

    def ok(x):
        return (not which_tests or x in which_tests) and (not exclude_tests or x not in exclude_tests)

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
    if ok('ebooks'):
        from calibre.ebooks.metadata.rtf import find_tests
        a(find_tests())
        from calibre.ebooks.metadata.html import find_tests
        a(find_tests())
        from calibre.ebooks.pdf.test_html_writer import find_tests
        a(find_tests())
        from calibre.utils.xml_parse import find_tests
        a(find_tests())
        from calibre.gui2.viewer.annotations import find_tests
        a(find_tests())
    if ok('misc'):
        from calibre.ebooks.metadata.tag_mapper import find_tests
        a(find_tests())
        from calibre.ebooks.metadata.author_mapper import find_tests
        a(find_tests())
        from calibre.utils.shared_file import find_tests
        a(find_tests())
        from calibre.utils.test_lock import find_tests
        a(find_tests())
        from calibre.utils.search_query_parser_test import find_tests
        a(find_tests())
        from calibre.utils.html2text import find_tests
        a(find_tests())
        from calibre.library.comments import find_tests
        a(find_tests())
        from calibre.ebooks.compression.palmdoc import find_tests
        a(find_tests())
        from calibre.gui2.viewer.convert_book import find_tests
        a(find_tests())
        from calibre.utils.hyphenation.test_hyphenation import find_tests
        a(find_tests())
        if iswindows:
            from calibre.utils.windows.wintest import find_tests
            a(find_tests())
            from calibre.utils.windows.winsapi import find_tests
            a(find_tests())
        a(unittest.defaultTestLoader.loadTestsFromTestCase(TestImports))
    if ok('dbcli'):
        from calibre.db.cli.tests import find_tests
        a(find_tests())

    tests = unittest.TestSuite(ans)
    return tests


class Test(Command):

    description = 'Run the calibre test suite'

    def add_options(self, parser):
        parser.add_option('--test-verbosity', type=int, default=4, help='Test verbosity (0-4)')
        parser.add_option('--test-module', '--test-group', default=[], action='append', type='choice', choices=sorted(map(str, TEST_MODULES)),
                          help='The test module to run (can be specified more than once for multiple modules). Choices: %s' % ', '.join(sorted(TEST_MODULES)))
        parser.add_option('--test-name', default=[], action='append',
                          help='The name of an individual test to run. Can be specified more than once for multiple tests. The name of the'
                          ' test is the name of the test function without the leading test_. For example, the function test_something()'
                          ' can be run by specifying the name "something".')
        parser.add_option('--exclude-test-module', default=[], action='append', type='choice', choices=sorted(map(str, TEST_MODULES)),
                          help='A test module to be excluded from the test run (can be specified more than once for multiple modules).'
                          ' Choices: %s' % ', '.join(sorted(TEST_MODULES)))
        parser.add_option('--exclude-test-name', default=[], action='append',
                          help='The name of an individual test to be excluded from the test run. Can be specified more than once for multiple tests.')

    def run(self, opts):
        from calibre.utils.run_tests import run_cli, filter_tests_by_name, remove_tests_by_name
        tests = find_tests(which_tests=frozenset(opts.test_module), exclude_tests=frozenset(opts.exclude_test_module))
        if opts.test_name:
            tests = filter_tests_by_name(tests, *opts.test_name)
        if opts.exclude_test_name:
            tests = remove_tests_by_name(tests, *opts.exclude_test_name)
        run_cli(tests, verbosity=opts.test_verbosity)


class TestRS(Command):

    description = 'Run tests for RapydScript code'

    def run(self, opts):
        from calibre.utils.rapydscript import run_rapydscript_tests
        run_rapydscript_tests()
