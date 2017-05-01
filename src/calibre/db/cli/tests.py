#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__docformat__ = 'restructuredtext en'

'''
Test the CLI of the calibre database management tool
'''
import csv
import unittest
from cStringIO import StringIO


from calibre.db.cli.cmd_check_library import _print_check_library_results


class Checker(object):

    def __init__(self, kw):
        for k, v in kw.iteritems():
            setattr(self, k, v)


class PrintCheckLibraryResultsTest(unittest.TestCase):
    """
    Asserts the format of the output to the CLI to avoid regressions
    """

    check = ('dummy_check', 'Dummy Check')

    def test_prints_nothing_if_no_errors(self):
        stdout = StringIO()
        checker = Checker(dict.fromkeys(self.check))
        _print_check_library_results(checker, self.check, as_csv=False, out=stdout)
        self.assertEqual(stdout.getvalue(), '')
        _print_check_library_results(checker, self.check, as_csv=True, out=stdout)
        self.assertEqual(stdout.getvalue(), '')

    def test_human_readable_output(self):
        """
        Basic check of the human-readable output.

        Does not test: the full line format, truncation
        """
        data = [['first', 'second']]
        checker = Checker(dict.fromkeys(self.check))
        setattr(checker, self.check[0], data)
        stdout = StringIO()
        _print_check_library_results(checker, self.check, out=stdout, as_csv=False)

        result = stdout.getvalue().split('\n')
        self.assertEqual(len(result), len(data)+2)
        self.assertEqual(result[0], self.check[1])

        result_first = result[1].split('-')[0].strip()
        result_second = result[1].split('-')[1].strip()

        self.assertEqual(result_first, 'first')
        self.assertEqual(result_second, 'second')

        self.assertEqual(result[-1], '')

    def test_basic_csv_output(self):
        """
        Test simple csv output
        """
        data = [['first', 'second']]
        checker = Checker(dict.fromkeys(self.check))
        setattr(checker, self.check[0], data)
        stdout = StringIO()
        _print_check_library_results(checker, self.check, as_csv=True, out=stdout)

        result = stdout.getvalue().split('\n')
        parsed_result = [l for l in csv.reader(result) if l]
        self.assertEqual(parsed_result, [[self.check[1], data[0][0], data[0][1]]])

    def test_escaped_csv_output(self):
        """
        Test more complex csv output
        """
        data = [['I, Caesar', 'second']]
        checker = Checker(dict.fromkeys(self.check))
        setattr(checker, self.check[0], data)
        stdout = StringIO()
        _print_check_library_results(checker, self.check, as_csv=True, out=stdout)

        result = stdout.getvalue().split('\n')
        parsed_result = [l for l in csv.reader(result) if l]
        self.assertEqual(parsed_result, [[self.check[1], data[0][0], data[0][1]]])


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(PrintCheckLibraryResultsTest)
