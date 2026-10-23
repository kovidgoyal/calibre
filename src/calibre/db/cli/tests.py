#!/usr/bin/env python
# License: GPLv3

"""
Test the CLI of the calibre database management tool
"""

import csv
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
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


class RestoreDatabaseTest(BaseTest):
    REPORT_NAME = 'calibre_db_restore_report.txt'

    def setUp(self):
        super().setUp()
        cache = self.init_cache()
        cache.dump_metadata()
        # Only books that have a folder on disk can be restored
        self.book_dirs = {}
        for book_id in cache.all_book_ids():
            book_dir = os.path.join(self.library_path, *cache.field_for('path', book_id).split('/'))
            if os.path.exists(os.path.join(book_dir, 'metadata.opf')):
                self.book_dirs[book_id] = book_dir
        self.assertGreater(len(self.book_dirs), 1)
        self.all_titles = {book_id: cache.field_for('title', book_id) for book_id in cache.all_book_ids()}
        self.titles = {book_id: self.all_titles[book_id] for book_id in self.book_dirs}
        cache.close()
        self.objects_to_close.remove(cache)
        # The report is written to the current directory
        self.cwd = self.mkdtemp()
        self.prev_cwd = os.getcwd()
        os.chdir(self.cwd)

    def tearDown(self):
        os.chdir(self.prev_cwd)
        super().tearDown()

    def corrupt_opf(self, book_id):
        with open(os.path.join(self.book_dirs[book_id], 'metadata.opf'), 'wb') as f:
            f.write(b'not an opf')

    def run_restore(self):
        from calibre.db.cli.cmd_restore_database import main, option_parser
        from calibre.db.cli.main import get_parser

        library_path = self.library_path

        class DBCtx:
            def __init__(self):
                self.library_path = library_path

        opts, args = option_parser(get_parser, []).parse_args(['--really-do-it'])
        with redirect_stdout(StringIO()) as out, redirect_stderr(StringIO()) as err:
            ret = main(opts, args, DBCtx())
        return ret, out.getvalue(), err.getvalue()

    def restored_titles(self):
        cache = self.init_cache()
        return {book_id: cache.field_for('title', book_id) for book_id in cache.all_book_ids()}

    def report_path(self):
        return os.path.join(self.cwd, self.REPORT_NAME)

    def test_restore_succeeded(self):
        ret, out, err = self.run_restore()
        self.assertEqual(ret, 0, err)
        self.assertIn('Restoring database succeeded', out)
        self.assertEqual(err, '')
        self.assertFalse(os.path.exists(self.report_path()))
        self.assertTrue(os.path.exists(os.path.join(self.library_path, 'metadata_pre_restore.db')))
        self.assertEqual(self.restored_titles(), self.titles)

    def test_restore_partially_failed(self):
        bad_id = min(self.titles)
        self.corrupt_opf(bad_id)
        ret, out, err = self.run_restore()
        self.assertEqual(ret, 2, err)
        self.assertIn('Restoring database succeeded', out)
        self.assertIn(self.REPORT_NAME, err)
        with open(self.report_path(), encoding='utf-8') as f:
            self.assertIn(self.book_dirs[bad_id], f.read())
        expected = dict(self.titles)
        del expected[bad_id]
        self.assertEqual(self.restored_titles(), expected)

    def test_restore_failed(self):
        for book_id in self.titles:
            self.corrupt_opf(book_id)
        ret, out, err = self.run_restore()
        self.assertEqual(ret, 1, out)
        self.assertNotIn('Restoring database succeeded', out)
        self.assertIn('Restoring database failed', err)
        # Each failed folder must be reported exactly once
        for book_dir in self.book_dirs.values():
            self.assertEqual(err.count(f'Failed to restore: {book_dir}\n'), 1, err)
        self.assertFalse(os.path.exists(self.report_path()))
        # The original database must be left untouched
        self.assertFalse(os.path.exists(os.path.join(self.library_path, 'metadata_pre_restore.db')))
        self.assertEqual(self.restored_titles(), self.all_titles)


def find_tests():
    loader = unittest.defaultTestLoader
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(PrintCheckLibraryResultsTest),
        loader.loadTestsFromTestCase(ListCategoriesTest),
        loader.loadTestsFromTestCase(SetCustomTest),
        loader.loadTestsFromTestCase(FTSSearchTest),
        loader.loadTestsFromTestCase(RestoreDatabaseTest),
    ))
