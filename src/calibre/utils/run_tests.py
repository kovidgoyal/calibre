#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import unittest, functools, importlib
from calibre.utils.monotonic import monotonic


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
        super(TestResult, self).__init__(*args, **kwargs)
        self.start_time = {}
        for x in ('Success', 'Error', 'Failure', 'Skip', 'ExpectedFailure', 'UnexpectedSuccess'):
            x = 'add' + x
            setattr(self, x, no_endl(getattr(self, x)))
        self.times = {}

    def startTest(self, test):
        self.start_time[test] = monotonic()
        return super(TestResult, self).startTest(test)

    def stopTest(self, test):
        orig = self.stream.writeln
        self.stream.writeln = self.stream.write
        super(TestResult, self).stopTest(test)
        elapsed = monotonic()
        elapsed -= self.start_time.get(test, elapsed)
        self.times[test] = elapsed
        self.stream.writeln = orig
        self.stream.writeln(' [%.1f s]' % elapsed)

    def stopTestRun(self):
        super(TestResult, self).stopTestRun()
        if self.wasSuccessful():
            tests = sorted(self.times, key=self.times.get, reverse=True)
            slowest = ['%s [%.1f s]' % (t.id(), self.times[t]) for t in tests[:3]]
            if len(slowest) > 1:
                self.stream.writeln('\nSlowest tests: %s' % ' '.join(slowest))


def find_tests_in_package(package, excludes=('main.py',)):
    loader = importlib.import_module(package).__spec__.loader
    items = list(loader.contents())
    suits = []
    for x in items:
        if x.endswith('.py') and x not in excludes:
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
    from calibre.utils.config_base import reset_tweaks_to_default
    from calibre.ebooks.metadata.book.base import reset_field_metadata
    reset_tweaks_to_default()
    reset_field_metadata()


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
    parser.add_argument('name', nargs='?', default=None,
                        help='The name of the test to run, for e.g. writing.WritingTest.many_many_basic or .many_many_basic for a shortcut')
    args = parser.parse_args()
    tests = find_tests()
    if args.name:
        if args.name.startswith('.'):
            tests = filter_tests_by_name(tests, args.name[1:])
        else:
            tests = filter_tests_by_module(tests, args.name)
        if not tests._tests:
            raise SystemExit('No test named %s found' % args.name)
    run_cli(tests, verbosity)


def run_cli(suite, verbosity=4):
    r = unittest.TextTestRunner
    r.resultclass = unittest.TextTestResult if verbosity < 2 else TestResult
    init_env()
    result = r(verbosity=verbosity).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
