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
from StringIO import StringIO

from mock import Mock, patch

from calibre.library.check_library import CheckLibrary
from calibre.library.cli import _print_check_library_results


class PrintCheckLibraryResultsTest(unittest.TestCase):
    """
    Asserts the format of the output to the CLI to avoid regressions
    """
    check_machine_name = 'dummy_check'
    check_human_name = 'Dummy Check'
    check = (check_machine_name, check_human_name, True, False)

    @patch('sys.stdout', new_callable=StringIO)
    def test_prints_nothing_if_no_errors(self, mock_stdout):
        checker = Mock(name='checker', spec=CheckLibrary)
        setattr(checker, self.check_machine_name, None)
        opts = Mock()

        opts.csv = False
        _print_check_library_results(checker, self.check, opts)
        self.assertEqual(mock_stdout.getvalue(), '')

        opts.csv = True
        _print_check_library_results(checker, self.check, opts)
        self.assertEqual(mock_stdout.getvalue(), '')

    @patch('sys.stdout', new_callable=StringIO)
    def test_human_readable_output(self, mock_stdout):
        """
        Basic check of the human-readable output.

        Does not test: the full line format, truncation
        """
        checker = Mock(name='checker', speck=CheckLibrary)
        data = [['first', 'second']]
        opts = Mock()
        opts.csv = False
        setattr(checker, self.check_machine_name, data)
        _print_check_library_results(checker, self.check, opts)

        result = mock_stdout.getvalue().split('\n')
        self.assertEqual(len(result), len(data)+2)
        self.assertEqual(result[0], self.check_human_name)

        result_first = result[1].split('-')[0].strip()
        result_second = result[1].split('-')[1].strip()

        self.assertEqual(result_first, 'first')
        self.assertEqual(result_second, 'second')

        self.assertEqual(result[-1], '')

    @patch('sys.stdout', new_callable=StringIO)
    def test_basic_csv_output(self, mock_stdout):
        """
        Test simple csv output
        """
        checker = Mock(name='checker', speck=CheckLibrary)
        data = [['first', 'second']]
        opts = Mock()
        opts.csv = True
        setattr(checker, self.check_machine_name, data)
        _print_check_library_results(checker, self.check, opts)

        result = mock_stdout.getvalue().split('\n')
        parsed_result = [l for l in csv.reader(result) if l]
        self.assertEqual(parsed_result, [[self.check_human_name, data[0][0], data[0][1]]])

    @patch('sys.stdout', new_callable=StringIO)
    def test_escaped_csv_output(self, mock_stdout):
        """
        Test more complex csv output
        """
        checker = Mock(name='checker', speck=CheckLibrary)
        data = [['I, Caesar', 'second']]
        opts = Mock()
        opts.csv = True
        setattr(checker, self.check_machine_name, data)
        _print_check_library_results(checker, self.check, opts)

        result = mock_stdout.getvalue().split('\n')
        parsed_result = [l for l in csv.reader(result) if l]
        self.assertEqual(parsed_result, [[self.check_human_name, data[0][0], data[0][1]]])
