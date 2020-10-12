#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import unittest, argparse


def find_tests():
    from calibre.utils.run_tests import find_tests_in_package
    return find_tests_in_package('tinycss.tests')


def run_tests(find_tests=find_tests, for_build=False):
    if not for_build:
        parser = argparse.ArgumentParser()
        parser.add_argument('name', nargs='?', default=None,
                            help='The name of the test to run')
        args = parser.parse_args()
    if not for_build and args.name and args.name.startswith('.'):
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
            print('No test named %s found' % args.name)
            raise SystemExit(1)
        tests = ans
    else:
        tests = unittest.defaultTestLoader.loadTestsFromName(args.name) if not for_build and args.name else find_tests()
    r = unittest.TextTestRunner
    if for_build:
        r = r(verbosity=0, buffer=True, failfast=True)
    else:
        r = r(verbosity=4)
    result = r.run(tests)
    if for_build and result.errors or result.failures:
        raise SystemExit(1)


if __name__ == '__main__':
    run_tests()
