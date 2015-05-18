#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import unittest, os, argparse, time, functools

try:
    import init_calibre
    del init_calibre
except ImportError:
    pass

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
        self.start_time[test] = time.time()
        return super(TestResult, self).startTest(test)

    def stopTest(self, test):
        orig = self.stream.writeln
        self.stream.writeln = self.stream.write
        super(TestResult, self).stopTest(test)
        elapsed = time.time()
        elapsed -= self.start_time.get(test, elapsed)
        self.times[test] = elapsed
        self.stream.writeln = orig
        self.stream.writeln(' [%.1g s]' % elapsed)

    def stopTestRun(self):
        super(TestResult, self).stopTestRun()
        if self.wasSuccessful():
            tests = sorted(self.times, key=self.times.get, reverse=True)
            slowest = ['%s [%g s]' % (t.id(), self.times[t]) for t in tests[:3]]
            if len(slowest) > 1:
                self.stream.writeln('\nSlowest tests: %s' % ' '.join(slowest))

def find_tests():
    return unittest.defaultTestLoader.discover(os.path.dirname(os.path.abspath(__file__)), pattern='*.py')

def run_tests(find_tests=find_tests):
    parser = argparse.ArgumentParser()
    parser.add_argument('name', nargs='?', default=None,
                        help='The name of the test to run, for e.g. writing.WritingTest.many_many_basic or .many_many_basic for a shortcut')
    args = parser.parse_args()
    if args.name and args.name.startswith('.'):
        tests = find_tests()
        q = args.name[1:]
        if not q.startswith('test_'):
            q = 'test_' + q
        ans = None
        try:
            for suite in tests:
                for test in suite._tests:
                    if test.__class__.__name__ == 'ModuleImportFailure':
                        raise Exception('Failed to import a test module: %s' % test)
                    for s in test:
                        if s._testMethodName == q:
                            ans = s
                            raise StopIteration()
        except StopIteration:
            pass
        if ans is None:
            print ('No test named %s found' % args.name)
            raise SystemExit(1)
        tests = ans
    else:
        tests = unittest.defaultTestLoader.loadTestsFromName(args.name) if args.name else find_tests()
    r = unittest.TextTestRunner
    r.resultclass = TestResult
    r(verbosity=4).run(tests)

if __name__ == '__main__':
    from calibre.utils.config_base import reset_tweaks_to_default
    from calibre.ebooks.metadata.book.base import reset_field_metadata
    reset_tweaks_to_default()
    reset_field_metadata()
    run_tests()
