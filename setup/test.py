#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os
import subprocess
import sys

from setup import Command

TEST_MODULES = frozenset('srv db polish opf css docx cfi matcher icu smartypants build misc dbcli ebooks'.split())


class Test(Command):

    description = 'Run the calibre test suite'

    def add_options(self, parser):
        parser.add_option('--test-verbosity', type=int, default=4, help='Test verbosity (0-4)')
        parser.add_option('--test-module', '--test-group', default=[], action='append', type='choice', choices=sorted(map(str, TEST_MODULES)),
                          help='The test module to run (can be specified more than once for multiple modules). Choices: %s' % ', '.join(sorted(TEST_MODULES)))
        parser.add_option('--test-name', '-n', default=[], action='append',
                          help='The name of an individual test to run. Can be specified more than once for multiple tests. The name of the'
                          ' test is the name of the test function without the leading test_. For example, the function test_something()'
                          ' can be run by specifying the name "something".')
        parser.add_option('--exclude-test-module', default=[], action='append', type='choice', choices=sorted(map(str, TEST_MODULES)),
                          help='A test module to be excluded from the test run (can be specified more than once for multiple modules).'
                          ' Choices: %s' % ', '.join(sorted(TEST_MODULES)))
        parser.add_option('--exclude-test-name', default=[], action='append',
                          help='The name of an individual test to be excluded from the test run. Can be specified more than once for multiple tests.')
        parser.add_option('--under-sanitize', default=False, action='store_true',
                          help='Run the test suite with the sanitizer preloaded')

    def run(self, opts):
        if opts.under_sanitize and 'CALIBRE_EXECED_UNDER_SANITIZE' not in os.environ:
            if 'libasan' not in os.environ.get('LD_PRELOAD', ''):
                os.environ['LD_PRELOAD'] = os.path.abspath(subprocess.check_output('gcc -print-file-name=libasan.so'.split()).decode('utf-8').strip())
            os.environ['CALIBRE_EXECED_UNDER_SANITIZE'] = '1'
            os.environ['ASAN_OPTIONS'] = 'detect_leaks=0'
            os.environ['PYCRYPTODOME_DISABLE_DEEPBIND'] = '1'  # https://github.com/Legrandin/pycryptodome/issues/558
            self.info(f'Re-execing with LD_PRELOAD={os.environ["LD_PRELOAD"]}')
            sys.stdout.flush()
            os.execl('setup.py', *sys.argv)
        from calibre.utils.run_tests import (
            filter_tests_by_name, remove_tests_by_name, run_cli, find_tests
        )
        tests = find_tests(which_tests=frozenset(opts.test_module), exclude_tests=frozenset(opts.exclude_test_module))
        if opts.test_name:
            tests = filter_tests_by_name(tests, *opts.test_name)
        if opts.exclude_test_name:
            tests = remove_tests_by_name(tests, *opts.exclude_test_name)
        run_cli(tests, verbosity=opts.test_verbosity, buffer=not opts.test_name)


class TestRS(Command):

    description = 'Run tests for RapydScript code'

    def run(self, opts):
        from calibre.utils.rapydscript import run_rapydscript_tests
        run_rapydscript_tests()
