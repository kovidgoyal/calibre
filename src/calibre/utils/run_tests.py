#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import functools
import importlib
import importlib.resources
import os
import unittest

from calibre.utils.monotonic import monotonic

is_ci = os.environ.get('CI', '').lower() == 'true'


def no_endl(f):
    @functools.wraps(f)
    def func(*args, **kwargs):
        self = f.__self__
        orig = self.stream.writeln
        self.stream.writeln = self.stream.write
        try:
            return f(*args, **kwargs)
        finally:
            self.stream.writeln = orig
    return func


class TestResult(unittest.TextTestResult):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = {}
        for x in ('Success', 'Error', 'Failure', 'Skip', 'ExpectedFailure', 'UnexpectedSuccess'):
            x = 'add' + x
            setattr(self, x, no_endl(getattr(self, x)))
        self.times = {}

    def startTest(self, test):
        self.start_time[test] = monotonic()
        return super().startTest(test)

    def stopTest(self, test):
        orig = self.stream.writeln
        self.stream.writeln = self.stream.write
        super().stopTest(test)
        elapsed = monotonic()
        elapsed -= self.start_time.get(test, elapsed)
        self.times[test] = elapsed
        self.stream.writeln = orig
        self.stream.writeln(' [%.1f s]' % elapsed)

    def stopTestRun(self):
        super().stopTestRun()
        if self.wasSuccessful():
            tests = sorted(self.times, key=self.times.get, reverse=True)
            slowest = [f'{t.id()} [{self.times[t]:.1f} s]' for t in tests[:3]]
            if len(slowest) > 1:
                self.stream.writeln('\nSlowest tests: %s' % ' '.join(slowest))


def find_tests_in_package(package, excludes=('main.py',)):
    items = [path.name for path in importlib.resources.files(package).iterdir()]
    suits = []
    excludes = set(excludes) | {x + 'c' for x in excludes}
    seen = set()
    for x in items:
        if (x.endswith('.py') or x.endswith('.pyc')) and x not in excludes:
            q = x.rpartition('.')[0]
            if q in seen:
                continue
            seen.add(q)
            m = importlib.import_module(package + '.' + x.partition('.')[0])
            suits.append(unittest.defaultTestLoader.loadTestsFromModule(m))
    return unittest.TestSuite(suits)


def itertests(suite):
    stack = [suite]
    while stack:
        suite = stack.pop()
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                stack.append(test)
                continue
            if test.__class__.__name__ == 'ModuleImportFailure':
                raise Exception('Failed to import a test module: %s' % test)
            yield test


def init_env():
    from calibre.ebooks.metadata.book.base import reset_field_metadata
    from calibre.ebooks.oeb.polish.utils import setup_css_parser_serialization
    from calibre.utils.config_base import reset_tweaks_to_default
    reset_tweaks_to_default()
    reset_field_metadata()
    setup_css_parser_serialization()


def filter_tests(suite, test_ok):
    ans = unittest.TestSuite()
    added = set()
    for test in itertests(suite):
        if test_ok(test) and test not in added:
            ans.addTest(test)
            added.add(test)
    return ans


def filter_tests_by_name(suite, *names):
    names = {x if x.startswith('test_') else 'test_' + x for x in names}

    def q(test):
        return test._testMethodName in names
    return filter_tests(suite, q)


def remove_tests_by_name(suite, *names):
    names = {x if x.startswith('test_') else 'test_' + x for x in names}

    def q(test):
        return test._testMethodName not in names
    return filter_tests(suite, q)


def filter_tests_by_module(suite, *names):
    names = frozenset(names)

    def q(test):
        m = test.__class__.__module__.rpartition('.')[-1]
        return m in names
    return filter_tests(suite, q)


def run_tests(find_tests, verbosity=4):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'name', nargs='?', default=None,
        help='The name of the test to run, for example: writing.WritingTest.many_many_basic or .many_many_basic for a shortcut')
    args = parser.parse_args()
    tests = find_tests()
    if args.name:
        if args.name.startswith('.'):
            tests = filter_tests_by_name(tests, args.name[1:])
        else:
            tests = filter_tests_by_module(tests, args.name)
        if not tests._tests:
            raise SystemExit('No test named %s found' % args.name)
    run_cli(tests, verbosity, buffer=not args.name)


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
        from calibre.constants import isbsd, islinux, ismacos, iswindows
        exclude_packages = {'calibre.devices.mtp.unix.upstream'}
        exclude_modules = set()
        if not iswindows:
            exclude_modules |= {'calibre.utils.iphlpapi', 'calibre.utils.open_with.windows', 'calibre.devices.winusb'}
            exclude_packages |= {'calibre.utils.winreg', 'calibre.utils.windows'}
        if not ismacos:
            exclude_modules.add('calibre.utils.open_with.osx')
        if not islinux:
            exclude_modules |= {
                'calibre.linux', 'calibre.gui2.tts.speechd',
                'calibre.utils.linux_trash', 'calibre.utils.open_with.linux',
                'calibre.gui2.linux_file_dialogs',
            }
        if 'SKIP_SPEECH_TESTS' in os.environ:
            exclude_packages.add('calibre.gui2.tts')
        if not isbsd:
            exclude_modules.add('calibre.devices.usbms.hal')
        d = os.path.dirname
        SRC = d(d(d(os.path.abspath(__file__))))
        self.assertGreater(self.base_check(os.path.join(SRC, 'odf'), exclude_packages, exclude_modules), 10)
        base = os.path.join(SRC, 'calibre')
        self.assertGreater(self.base_check(base, exclude_packages, exclude_modules), 1000)

        import calibre.web.feeds.feedparser as f
        del f
        from calibre.ebooks.markdown import Markdown
        del Markdown


def find_tests(which_tests=None, exclude_tests=None):
    from calibre.constants import iswindows
    ans = []
    a = ans.append

    def ok(x):
        return (not which_tests or x in which_tests) and (not exclude_tests or x not in exclude_tests)

    if ok('build'):
        from calibre.test_build import find_tests
        a(find_tests(only_build=True))
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
        from calibre.ebooks.html_transform_rules import test
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
    if ok('scraper'):
        from calibre.scraper.test_fetch_backend import find_tests
        a(find_tests())
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
        from calibre.utils.xml_parse import find_tests
        a(find_tests())
        from calibre.gui2.viewer.annotations import find_tests
        a(find_tests())
        from calibre.ebooks.html_entities import find_tests
        a(find_tests())
        from calibre.spell.dictionary import find_tests
        a(find_tests())
    if ok('misc'):
        from calibre.ebooks.html.input import find_tests
        a(find_tests())
        from calibre.ebooks.metadata.test_author_sort import find_tests
        a(find_tests())
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
        from calibre.utils.shm import find_tests
        a(find_tests())
        from calibre.library.comments import find_tests
        a(find_tests())
        from calibre.ebooks.compression.palmdoc import find_tests
        a(find_tests())
        from calibre.gui2.viewer.convert_book import find_tests
        a(find_tests())
        from calibre.utils.hyphenation.test_hyphenation import find_tests
        a(find_tests())
        from calibre.live import find_tests
        a(find_tests())
        from calibre.utils.copy_files_test import find_tests
        a(find_tests())
        if iswindows:
            from calibre.utils.windows.wintest import find_tests
            a(find_tests())
        a(unittest.defaultTestLoader.loadTestsFromTestCase(TestImports))
    if ok('dbcli'):
        from calibre.db.cli.tests import find_tests
        a(find_tests())

    tests = unittest.TestSuite(ans)
    return tests


def run_test(test_name, verbosity=4, buffer=False):
    # calibre-debug -t test_name
    which_tests = None
    if test_name.startswith('@'):
        which_tests = test_name[1:],
    tests = find_tests(which_tests)
    if test_name != 'all':
        if test_name.startswith('.'):
            tests = filter_tests_by_module(tests, test_name[1:])
        elif test_name.startswith('@'):
            pass
        else:
            tests = filter_tests_by_name(tests, test_name)
    if not tests._tests:
        raise SystemExit(f'No test named {test_name} found')
    run_cli(tests, verbosity, buffer=buffer)


def run_cli(suite, verbosity=4, buffer=True):
    r = unittest.TextTestRunner
    r.resultclass = unittest.TextTestResult if verbosity < 2 else TestResult
    init_env()
    result = r(verbosity=verbosity, buffer=buffer and not is_ci).run(suite)
    rc = 0 if result.wasSuccessful() else 1
    if is_ci:
        # for some reason interpreter shutdown hangs probably some non-daemonic
        # thread
        os._exit(rc)
    else:
        raise SystemExit(rc)
