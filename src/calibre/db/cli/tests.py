#!/usr/bin/env python
# License: GPLv3

"""
Test the CLI of the calibre database management tool
"""

import csv
import unittest
from contextlib import redirect_stdout
from io import StringIO

from calibre.db.cli.cmd_check_library import _print_check_library_results
from calibre.db.cli.cmd_list_categories import do_list
from calibre.db.tests.base import BaseTest
from polyglot.io import PolyglotBytesIO


class Checker:
    def __init__(self, kw):
        for k, v in kw.items():
            setattr(self, k, v)


class PrintCheckLibraryResultsTest(unittest.TestCase):
    """
    Asserts the format of the output to the CLI to avoid regressions
    """

    check = ('dummy_check', 'Dummy Check')

    def test_prints_nothing_if_no_errors(self):
        stdout = PolyglotBytesIO()
        checker = Checker(dict.fromkeys(self.check))
        _print_check_library_results(checker, self.check, as_csv=False, out=stdout)
        self.assertEqual(stdout.getvalue(), b'')
        _print_check_library_results(checker, self.check, as_csv=True, out=stdout)
        self.assertEqual(stdout.getvalue(), b'')

    def test_human_readable_output(self):
        """
        Basic check of the human-readable output.

        Does not test: the full line format, truncation
        """
        data = [['first', 'second']]
        checker = Checker(dict.fromkeys(self.check))
        setattr(checker, self.check[0], data)
        stdout = PolyglotBytesIO()
        _print_check_library_results(checker, self.check, out=stdout, as_csv=False)

        result = stdout.getvalue().decode('utf-8', 'replace').split('\n')
        self.assertEqual(len(result), len(data) + 2)
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
        stdout = PolyglotBytesIO()
        _print_check_library_results(checker, self.check, as_csv=True, out=stdout)

        result = stdout.getvalue().decode('utf-8', 'replace').split('\n')
        parsed_result = [l for l in csv.reader(result) if l]
        self.assertEqual(parsed_result, [[self.check[1], data[0][0], data[0][1]]])

    def test_escaped_csv_output(self):
        """
        Test more complex csv output
        """
        data = [['I, Caesar', 'second']]
        checker = Checker(dict.fromkeys(self.check))
        setattr(checker, self.check[0], data)
        stdout = PolyglotBytesIO()
        _print_check_library_results(checker, self.check, as_csv=True, out=stdout)

        result = stdout.getvalue().decode('utf-8', 'replace').split('\n')
        parsed_result = [l for l in csv.reader(result) if l]
        self.assertEqual(parsed_result, [[self.check[1], data[0][0], data[0][1]]])


class ListCategoriesTest(unittest.TestCase):
    def test_list_output_is_text(self):
        data = [{'category': 'Authors', 'tag_count': 3, 'divided': 10}]
        out = StringIO()
        with redirect_stdout(out):
            do_list(['category', 'tag_count', 'divided'], data, None)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[1].split(), ['Authors', '3', '10'])


class SetCustomTest(BaseTest):
    def test_set_custom_append_multiple_values(self):
        from calibre.db.cli.cmd_set_custom import implementation

        db = self.init_cache()
        for column, separator, first, second in (
            ('tags', ',', 'Alpha', 'Beta'),
            ('authors', '&', 'Doe, Jane', 'Smith, John'),
        ):
            field = '#' + column
            for append, value, expected in (
                (True, f'{first}{separator}{second}', ('Existing', first, second)),
                (True, f' Existing {separator} {first}{separator}{first}{separator} ', ('Existing', first)),
                (True, first, ('Existing', first)),
                (True, '', ('Existing',)),
                (False, f'{first}{separator}{second}', (first, second)),
            ):
                with self.subTest(column=column, append=append, value=value):
                    db.set_field(field, {1: ('Existing',)})
                    ok, msg = implementation(db, None, column, 1, value, append)
                    self.assertTrue(ok, msg)
                    self.assertEqual(db.field_for(field, 1), expected)


class FTSSearchTest(BaseTest):
    def run_fts_search(self, db, *args):
        from calibre.db.cli.cmd_fts_search import implementation, main, option_parser
        from calibre.db.cli.main import get_parser

        class DBCtx:
            option_parser = None

            def run(self, name, *args):
                return implementation(db, None, *args)

        opts, args = option_parser(get_parser, []).parse_args(list(args))
        with redirect_stdout(StringIO()) as out:
            main(opts, args, DBCtx())
        return out.getvalue()

    def test_fts_search_indexing_threshold(self):
        db = self.init_cache()
        self.addCleanup(db.close)
        # the cache fts jobs will index formats, changing the numbers, so disable it
        db.queue_next_fts_job = lambda *a: None
        db.enable_fts(start_pool=False)
        with self.assertRaisesRegex(SystemExit, '3 files out of 3'):
            self.run_fts_search(db, 'test')
        self.assertEqual(self.run_fts_search(db, '--indexing-threshold=0', 'test'), '')
        db.remove_formats({2: ['FMT1']})
        with self.assertRaisesRegex(SystemExit, '2 files out of 2'):
            self.run_fts_search(db, 'test')
        # a library with no files has nothing left to index
        db.remove_books((1,))
        self.assertEqual(db.fts_indexing_progress()[:2], (0, 0))
        self.assertEqual(self.run_fts_search(db, 'test'), '')


def find_tests():
    loader = unittest.defaultTestLoader
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(PrintCheckLibraryResultsTest),
        loader.loadTestsFromTestCase(ListCategoriesTest),
        loader.loadTestsFromTestCase(SetCustomTest),
        loader.loadTestsFromTestCase(FTSSearchTest),
    ))
