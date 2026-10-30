#!/usr/bin/env python
# License: GPLv3

"""
Test the CLI of the calibre database management tool
"""

import csv
import json
import os
import shutil
import unittest
from contextlib import redirect_stderr, redirect_stdout
from functools import partial
from io import StringIO

from calibre.db.cli.cmd_check_library import _print_check_library_results
from calibre.db.cli.cmd_list_categories import do_list
from calibre.db.constants import NOTES_DB_NAME, NOTES_DIR_NAME
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


class NotesTest(BaseTest):
    def run_notes(self, db, *args, is_remote=False):
        from calibre.db.cli.cmd_notes import implementation, main, option_parser
        from calibre.db.cli.main import get_parser

        class DBCtx:
            option_parser = None

            def __init__(self, is_remote: bool):
                self.is_remote = is_remote

            def run(self, name, *args):
                return implementation(db, (lambda *a: None) if self.is_remote else None, *args)

        dbctx = DBCtx(is_remote)
        opts, args = option_parser(get_parser, []).parse_args(list(args))
        with redirect_stdout(StringIO()) as out:
            main(opts, args, dbctx)
        return out.getvalue()

    def test_notes(self):
        db = self.init_cache()
        self.addCleanup(db.close)
        self.assertEqual(self.run_notes(db, 'list'), '')
        path = os.path.join(self.library_path, 'note.html')
        with open(path, 'w') as f:
            f.write('<p>A <b>great</b> author</p>')
        for is_remote in (False, True):
            with self.subTest(is_remote=is_remote):
                self.run_notes(db, 'set', 'authors', 'author one', path, is_remote=is_remote)
                self.assertIn('<b>great</b>', db.notes_for('authors', db.get_item_id('authors', 'Author One')))
                self.assertEqual(self.run_notes(db, 'show', 'authors', 'Author One').strip(), 'A **great** author')
        html = self.run_notes(db, 'show', '--as-html', 'authors', 'Author One')
        self.assertIn('<b>great</b>', html)
        db.import_note('tags', db.get_item_id('tags', 'Tag One'), html.encode(), path_is_data=True)
        self.assertEqual(self.run_notes(db, 'list'), 'authors: Author One\ntags: Tag One\n')
        self.assertEqual(self.run_notes(db, 'list', 'tags'), 'tags: Tag One\n')
        self.run_notes(db, 'remove', 'tags', 'Tag One')
        self.assertEqual(self.run_notes(db, 'list'), 'authors: Author One\n')
        self.assertEqual(self.run_notes(db, 'show', 'tags', 'Tag One'), '')
        self.assertEqual(self.run_notes(db, 'show', '--as-html', 'tags', 'Tag One'), '')
        for args, msg in (
            (('show', 'authors', 'Nobody'), 'No item named Nobody'),
            (('show', 'title', 'Title One'), 'does not support notes'),
            (('list', 'rating'), 'does not support notes'),
            (('frob',), 'not recognized'),
            (('show', 'authors'), 'must specify a field'),
            (('set', 'authors', 'Author One'), 'must specify the file'),
            (('set', 'authors', 'Author One', os.path.join(self.library_path, 'missing.html')), 'Failed to read the note'),
            (('set', 'authors', 'Author One', path, 'extra'), 'Too many arguments'),
            (('show', 'authors', 'Author One', 'extra'), 'Too many arguments'),
            (('list', 'authors', 'tags'), 'at most one field'),
        ):
            with self.subTest(args=args), self.assertRaisesRegex(SystemExit, msg):
                self.run_notes(db, *args)

    def test_notes_search(self):
        db = self.init_cache()
        self.addCleanup(db.close)
        author_id = db.get_item_id('authors', 'Author One')
        tag_id = db.get_item_id('tags', 'Tag One')
        db.set_notes_for('authors', author_id, '<p>Historical fiction from Poland</p>', searchable_text='Historical fiction from Poland')
        db.set_notes_for('tags', tag_id, '<p>Historical fiction from France</p>', searchable_text='Historical fiction from France')
        db.set_field('#tags', {1: ('Research One',)})
        item_id = db.get_item_id('#tags', 'Research One')
        db.set_notes_for('#tags', item_id, '<p>Historical fiction from Japan</p>', searchable_text='Historical fiction from Japan')
        for is_remote in (False, True):
            with self.subTest(is_remote=is_remote):
                search = partial(self.run_notes, db, 'search', is_remote=is_remote)
                lines = {tuple(line.split('\t')) for line in search('historical').splitlines()}
                self.assertEqual(
                    lines,
                    {
                        ('authors', 'Author One', 'Author One Historical fiction from Poland'),
                        ('tags', 'Tag One', 'Tag One Historical fiction from France'),
                        ('#tags', 'Research One', 'Research One Historical fiction from Japan'),
                    },
                )
                self.assertEqual(search('--field', 'authors', 'historical'), 'authors\tAuthor One\tAuthor One Historical fiction from Poland\n')
                self.assertEqual(search('--field', '#tags', 'historical'), '#tags\tResearch One\tResearch One Historical fiction from Japan\n')
                self.assertEqual(search('historical AND Poland'), 'authors\tAuthor One\tAuthor One Historical fiction from Poland\n')
                self.assertEqual(set(search('"fiction from"').splitlines()), set(search('historical').splitlines()))
                self.assertEqual(search('unmatched'), '')
                self.assertEqual(search('--field', 'series', 'historical'), '')
                for args, msg in (
                    ((), 'one non-empty search expression'),
                    (('',), 'one non-empty search expression'),
                    ((' ',), 'one non-empty search expression'),
                    (('one', 'two'), 'one non-empty search expression'),
                    (('"',), 'Failed to parse search query'),
                    (('--field', 'title', 'historical'), 'does not support notes'),
                    (('--field', '#missing', 'historical'), 'does not support notes'),
                    (('--as-html', 'historical'), 'cannot be used with search'),
                ):
                    with self.subTest(args=args), self.assertRaisesRegex(SystemExit, msg):
                        search(*args)
        with self.assertRaisesRegex(SystemExit, 'only be used with search'):
            self.run_notes(db, 'list', '--field', 'authors')
        db.set_notes_for('authors', author_id, 'terminal', searchable_text='terminal\x1b[31m\x9b with\nnewlines\tand tabs')
        output = self.run_notes(db, 'search', 'terminal')
        self.assertEqual(output, 'authors\tAuthor One\tAuthor One terminal[31m with newlines and tabs\n')

    def test_notes_server_side_import(self):
        from calibre.db.cli.cmd_notes import implementation

        db = self.init_cache()
        self.addCleanup(db.close)
        img = os.path.join(self.library_path, 'image.png')
        with open(img, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n')
        path = os.path.join(self.library_path, 'note.html')
        with open(path, 'w') as f:
            f.write('<p>secret</p><img src="image.png">')
        author_id = db.get_item_id('authors', 'Author One')

        def notify_changes(*a):
            pass

        # Paths must never be read on the server
        ok, err = implementation(db, notify_changes, 'set', 'authors', 'Author One', path, True)
        self.assertFalse(ok)
        self.assertIn('Cannot import notes from files on the server', err)
        self.assertFalse(db.notes_for('authors', author_id))
        # Images referenced by file paths in HTML data must not be imported,
        # not even from the calibre temp directory of the server
        from calibre.ptempfile import base_dir

        tmp_img = os.path.join(base_dir(), 'notes-test-image.png')
        shutil.copyfile(img, tmp_img)
        self.addCleanup(os.remove, tmp_img)
        for src in (img, 'file://' + img.replace(os.sep, '/'), 'image.png', tmp_img, 'notes-test-image.png'):
            with self.subTest(src=src):
                ok, err = implementation(db, notify_changes, 'set', 'authors', 'Author One', f'<p>x</p><img src="{src}">'.encode(), False)
                self.assertTrue(ok)
                self.assertFalse(db.notes_data_for('authors', author_id)['resource_hashes'])
        # Locally, images relative to the HTML file are imported
        ok, err = implementation(db, None, 'set', 'authors', 'Author One', path, True)
        self.assertTrue(ok)
        self.assertEqual(len(db.notes_data_for('authors', author_id)['resource_hashes']), 1)


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

    def assert_restore_succeeded(self):
        ret, out, err = self.run_restore()
        self.assertEqual(ret, 0, err)
        self.assertIn('Restoring database succeeded', out)
        self.assertEqual(err, '')
        self.assertFalse(os.path.exists(self.report_path()))
        self.assertTrue(os.path.exists(os.path.join(self.library_path, 'metadata_pre_restore.db')))
        self.assertEqual(self.restored_titles(), self.titles)

    def test_restore_succeeded(self):
        self.assert_restore_succeeded()

    def restore_without_notes(self, with_preferences):
        if with_preferences:
            cache = self.init_cache()
            cache.saved_search_add('Restored search', 'title:test')
            cache.backend.prefs.write_serialized(self.library_path)
            cache.close()
            self.objects_to_close.remove(cache)
        else:
            self.assertFalse(os.path.exists(os.path.join(self.library_path, 'metadata_db_prefs_backup.json')))
        notes_path = os.path.join(self.library_path, NOTES_DIR_NAME)
        shutil.rmtree(notes_path)
        self.assert_restore_succeeded()
        self.assertTrue(os.path.isfile(os.path.join(notes_path, NOTES_DB_NAME)))
        if with_preferences:
            self.assertEqual(self.init_cache().saved_search_lookup('Restored search'), 'title:test')

    def test_restore_without_notes(self):
        self.restore_without_notes(with_preferences=False)

    def test_restore_without_notes_with_preferences(self):
        self.restore_without_notes(with_preferences=True)

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


class ItemsTest(BaseTest):
    def run_items(self, db, *args):
        from calibre.db.cli.cmd_items import implementation, main, option_parser
        from calibre.db.cli.main import get_parser

        class DBCtx:
            def run(self, name, *args):
                return implementation(db, None, *args)

        opts, args = option_parser(get_parser, []).parse_args(list(args))
        with redirect_stdout(StringIO()) as out:
            main(opts, args, DBCtx())
        return out.getvalue()

    def test_items(self):
        from calibre.db.cli.cmd_items import supported_fields

        db = self.init_cache()
        self.addCleanup(db.close)
        self.assertEqual(supported_fields(db), {'authors', 'tags', 'series', 'publisher', '#authors', '#tags', '#series'})

        # Rename, matching case insensitively
        self.assertEqual(self.run_items(db, 'rename', 'publisher', 'publisher one', 'Pub'), 'One book changed\n')
        self.assertEqual(db.field_for('publisher', 2), 'Pub')
        # Renaming to an existing item merges them
        self.assertEqual(self.run_items(db, 'rename', 'tags', 'Tag Two', 'Tag One'), 'One book changed\n')
        self.assertEqual(db.field_for('tags', 2), ('Tag One',))
        self.assertIsNone(db.get_item_id('tags', 'Tag Two'))
        # Renaming to several values for multiple value fields
        self.run_items(db, 'rename', '#tags', 'My Tag Two', 'A, B')
        self.assertEqual(db.field_for('#tags', 2), ('My Tag One', 'A', 'B'))
        self.run_items(db, 'rename', 'authors', 'Author One', 'Writer')
        self.assertEqual(db.field_for('authors', 1), ('Author Two', 'Writer'))
        self.assertEqual(db.field_for('author_sort', 2), 'Writer')
        # Restricting to the books matching a search
        self.assertEqual(self.run_items(db, 'rename', '--search', 'id:1', 'series', 'A Series One', 'Other'), 'One book changed\n')
        self.assertEqual((db.field_for('series', 1), db.field_for('series', 2)), ('Other', 'A Series One'))

        # Remove
        self.assertEqual(self.run_items(db, 'remove', '-s', 'id:1', 'tags', 'tag one'), 'One book changed\n')
        self.assertEqual((db.field_for('tags', 1), db.field_for('tags', 2)), (('News',), ('Tag One',)))
        self.assertEqual(self.run_items(db, 'remove', 'tags', 'News', 'Tag One'), '2 books changed\n')
        self.assertEqual(db.all_field_names('tags'), set())
        self.run_items(db, 'remove', '#series', 'My Series One')
        self.assertIsNone(db.field_for('#series', 2))

        for args, msg in (
            (('rename', 'tags', 'Nothing', 'X'), 'No item named Nothing'),
            (('remove', 'publisher', 'Pub', 'Nothing'), 'No item named Nothing'),
            (('rename', 'title', 'Title One', 'X'), 'not supported'),
            (('remove', 'formats', 'FMT1'), 'not supported'),
            (('remove', '#enum', 'One'), 'not supported'),
            (('remove', 'authors', 'Writer'), 'cannot be removed'),
            (('rename', 'publisher', 'Pub', ' '), 'must not be empty'),
            (('rename', 'publisher', 'Pub'), 'must specify a field'),
            (('rename', 'publisher', 'Pub', 'X', 'Y'), 'must specify a field'),
            (('remove', 'publisher'), 'must specify a field'),
            (('frob',), 'not recognized'),
            ((), 'must specify an action'),
        ):
            with self.subTest(args=args), self.assertRaisesRegex(SystemExit, msg):
                self.run_items(db, *args)
        # Nothing was changed by the failed commands
        self.assertEqual(db.field_for('publisher', 2), 'Pub')
        self.assertEqual(db.field_for('authors', 2), ('Writer',))

    def test_items_remote(self):
        from calibre.db.cli.cmd_items import implementation

        db = self.init_cache()
        self.addCleanup(db.close)
        changes = []
        # Templates in search expressions must not be evaluated for remote clients
        ok, msg = implementation(db, changes.append, 'rename', 'tags', ['Tag One'], 'X', 'template:"{title}#@#:t:Title Two"')
        self.assertFalse(ok)
        self.assertIn('Templates are not allowed', msg)
        self.assertEqual(db.field_for('tags', 1), ('News', 'Tag One'))
        self.assertFalse(changes)
        ok, msg = implementation(db, None, 'rename', 'tags', ['Tag One'], 'X', 'template:"{title}#@#:t:Title Two"')
        self.assertTrue(ok, msg)
        self.assertEqual(db.field_for('tags', 1), ('News', 'X'))
        ok, msg = implementation(db, changes.append, 'remove', 'tags', ['News'], '', 'title:"=Title Two" and (')
        self.assertFalse(ok)
        self.assertIn('Failed to parse search query', msg)
        self.assertEqual(db.field_for('tags', 1), ('News', 'X'))
        self.assertTrue(implementation(db, changes.append, 'remove', 'tags', ['News'], '', 'id:1')[0])
        self.assertEqual(db.field_for('tags', 1), ('X',))
        self.assertEqual(len(changes), 1)


class AnnotationsTest(BaseTest):
    def run_annotations(self, db, *args, is_remote=False, changes=None):
        import json

        from calibre.db.cli.cmd_annotations import implementation, main, option_parser
        from calibre.db.cli.main import get_parser

        notify_changes = (changes if changes is not None else []).append if is_remote else None

        class DBCtx:
            def run(self, name, *args):
                ans = implementation(db, notify_changes, *args)
                # Remote results are sent as JSON
                return json.loads(json.dumps(ans)) if is_remote else ans

        opts, args = option_parser(get_parser, []).parse_args(list(args))
        with redirect_stdout(StringIO()) as out:
            main(opts, args, DBCtx())
        return out.getvalue()

    def test_annotations(self):
        import json

        from calibre.utils.date import EPOCH, utcnow

        db = self.init_cache()
        self.addCleanup(db.close)

        def a(**kw):
            ts = utcnow()
            kw['timestamp'] = ts.isoformat()
            return kw, (ts - EPOCH).total_seconds()

        db.set_annotations_for_book(
            1,
            'EPUB',
            [
                a(type='highlight', highlighted_text='second', uuid='2', spine_index=2, start_cfi='/4/2/1:0', toc_family_titles=['Chapter 2'], notes='A note'),
                a(type='highlight', highlighted_text='first', uuid='1', spine_index=1, start_cfi='/4/8/1:0', toc_family_titles=['Chapter 1']),
                a(type='bookmark', title='A bookmark', pos_type='epubcfi', pos='epubcfi(/6/2!/4/2)'),
                a(type='bookmark', title='No position\x1b[31m', pos_type='epubcfi'),
                a(type='highlight', highlighted_text='removed', uuid='3', removed=True),
            ],
        )
        db.set_annotations_for_book(2, 'EPUB', [a(type='bookmark', title='Other book', pos_type='epubcfi', pos='epubcfi(/6/2!/4/2)')])
        ids = {x['annotation'].get('highlighted_text') or x['annotation']['title']: x['id'] for x in db.all_annotations(ignore_removed=True)}

        for is_remote in (False, True):
            with self.subTest(is_remote=is_remote):
                lines = self.run_annotations(db, 'list', is_remote=is_remote).splitlines()
                self.assertEqual(len(lines), 5)
                self.assertIn(f"{ids['first']}\tTitle Two\thighlight\tEPUB\tlocal:viewer\tfirst", lines)
                # Control characters are not sent to the terminal
                self.assertIn(f"{ids['No position\x1b[31m']}\tTitle Two\tbookmark\tEPUB\tlocal:viewer\tNo position[31m", lines)
                self.assertEqual(
                    self.run_annotations(db, 'list', '-s', 'id:2', is_remote=is_remote).splitlines(),
                    [f"{ids['Other book']}\tTitle One\tbookmark\tEPUB\tlocal:viewer\tOther book"],
                )
                self.assertEqual(len(self.run_annotations(db, 'list', '-t', 'bookmark', is_remote=is_remote).splitlines()), 3)

                # Highlights are in the order they appear in the book, under their chapters
                text = self.run_annotations(db, 'export', '-f', 'markdown', '-s', 'id:1', is_remote=is_remote)
                self.assertTrue(text.startswith('# Title Two\n\n## Chapter 1\n\nfirst\n*'), text)
                self.assertLess(text.index('first'), text.index('second'))
                self.assertLess(text.index('second'), text.index('A bookmark'))
                # Bookmarks have no chapter, so they must not appear under the chapter of the last highlight
                self.assertLess(text.index('## Unknown chapter'), text.index('A bookmark'))
                self.assertNotIn('\x1b', text)
                self.assertIn('A note', text)
                self.assertNotIn('removed', text)
                text = self.run_annotations(db, 'export', is_remote=is_remote)
                self.assertIn('# Title One', text)
                self.assertIn('───', text)
                data = json.loads(self.run_annotations(db, 'export', '-f', 'json', '-t', 'highlight', is_remote=is_remote))
                self.assertEqual(data['type'], 'calibre_annotation_collection')
                exported = {(x['book_id'], x['format'], x['highlighted_text']) for x in data['annotations']}
                self.assertEqual(exported, {(1, 'EPUB', 'first'), (1, 'EPUB', 'second')})

        changes = []
        self.assertEqual(
            self.run_annotations(db, 'remove', str(ids['first']), str(ids['Other book']), is_remote=True, changes=changes), '2 annotations removed\n'
        )
        self.assertEqual([c.book_ids for c in changes], [frozenset((1, 2))])
        self.assertEqual(len(self.run_annotations(db, 'list').splitlines()), 3)
        for args, msg in (
            (('remove', str(ids['first'])), 'No annotations with the ids'),
            (('remove', '-t', 'bookmark', str(ids['second'])), 'cannot be used with remove'),
            (('remove', 'x'), 'must be numbers'),
            (('remove',), 'must specify the ids'),
            (('list', '-s', 'title:"=Title One" and ('), 'Failed to parse search query'),
            (('list', 'extra'), 'Too many arguments'),
            (('frob',), 'not recognized'),
        ):
            with self.subTest(args=args), self.assertRaisesRegex(SystemExit, msg):
                self.run_annotations(db, *args)
        self.assertEqual(len(self.run_annotations(db, 'list').splitlines()), 3)

    def test_annotations_import(self):
        from io import BytesIO

        from calibre.utils.date import EPOCH
        from calibre.utils.iso8601 import parse_iso8601

        db = self.init_cache()
        for book_id in (1, 2, 3):
            db.add_format(book_id, 'FMT1', BytesIO(b'book'), run_hooks=False)

        def a(**kw):
            kw.setdefault('timestamp', '2026-01-01T00:00:00+00:00')
            return kw, (parse_iso8601(kw['timestamp']) - EPOCH).total_seconds()

        db.set_annotations_for_book(
            1,
            'FMT1',
            [
                a(type='highlight', uuid='shared', highlighted_text='Original', start_cfi='/4/2:0', spine_index=0, notes='A note'),
                a(type='bookmark', title='Bookmark', pos_type='epubcfi', pos='epubcfi(/6/2!/4/2)'),
            ],
        )
        exported = self.run_annotations(db, 'export', '-s', 'id:1', '-f', 'json')
        path = os.path.join(self.mkdtemp(), 'annotations.calibre_annotation_collection')
        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write(exported)
        for is_remote, book_id in ((False, 2), (True, 3)):
            with self.subTest(is_remote=is_remote):
                existing = [
                    a(type='highlight', uuid='shared', highlighted_text='Newer', timestamp='2026-02-01T00:00:00+00:00'),
                    a(type='highlight', uuid='unrelated', highlighted_text='Unrelated'),
                ]
                db.set_annotations_for_book(book_id, 'FMT1', existing)
                db.set_last_read_position(book_id, 'FMT1', cfi='epubcfi(/6/2!/4/4)', pos_frac=0.5)
                reading_position = db.get_last_read_positions(book_id, 'FMT1')
                db.set_annotations_for_book(book_id, 'FMT1', [a(type='bookmark', title='Web bookmark')], user_type='web', user='reader')
                changes = []
                for imported, unchanged in ((1, 1), (0, 2)):
                    self.assertEqual(
                        self.run_annotations(db, 'import', str(book_id), 'fmt1', path, is_remote=is_remote, changes=changes),
                        f'{imported} annotations imported\n{unchanged} annotations unchanged, as the library already has the same or newer versions\n',
                    )
                    amap = db.annotations_map_for_book(book_id, 'FMT1')
                    self.assertEqual({h['uuid']: h['highlighted_text'] for h in amap['highlight']}, {'shared': 'Newer', 'unrelated': 'Unrelated'})
                    self.assertEqual([b['title'] for b in amap['bookmark']], ['Bookmark'])
                    self.assertEqual(db.get_last_read_positions(book_id, 'FMT1'), reading_position)
                    self.assertEqual(db.annotations_map_for_book(book_id, 'FMT1', user_type='web', user='reader')['bookmark'][0]['title'], 'Web bookmark')
                    self.assertTrue(all('book_id' not in x and 'format' not in x for values in amap.values() for x in values))
                # Only imports that change something are notified
                self.assertEqual([c.book_ids for c in changes], [frozenset((book_id,))] * (1 if is_remote else 0))
                self.run_annotations(db, 'import', str(book_id), 'FMT1', path, '--user-type', 'web', '--annotation-user', 'reader', is_remote=is_remote)
                web = db.annotations_map_for_book(book_id, 'FMT1', user_type='web', user='reader')
                self.assertEqual({b['title'] for b in web['bookmark']}, {'Bookmark', 'Web bookmark'})
                self.assertEqual(web['highlight'][0]['notes'], 'A note')
                # A newer deletion in the destination must not be resurrected
                # by an older highlight in a backup.
                db.set_annotations_for_book(book_id, 'FMT1', [a(type='highlight', uuid='shared', removed=True, timestamp='2026-03-01T00:00:00+00:00')])
                self.run_annotations(db, 'import', str(book_id), 'FMT1', path, is_remote=is_remote)
                shared = next(x for x in db.annotations_map_for_book(book_id, 'FMT1')['highlight'] if x['uuid'] == 'shared')
                self.assertTrue(shared['removed'])
        self.assertEqual(db.annotations_map_for_book(1, 'FMT1')['highlight'][0]['highlighted_text'], 'Original')

    def test_annotations_import_invalid(self):
        from copy import deepcopy
        from io import BytesIO

        from calibre.db.cli.cmd_annotations import implementation

        db = self.init_cache()
        db.add_format(1, 'FMT1', BytesIO(b'book'), run_hooks=False)
        annot = {'type': 'highlight', 'uuid': 'new', 'highlighted_text': 'Text', 'timestamp': '2026-01-01T00:00:00+00:00', 'book_id': 20, 'format': 'FMT1'}
        collection = {'version': 1, 'type': 'calibre_annotation_collection', 'annotations': [annot]}
        invalid = [None, [], {}, dict(collection, version=2), dict(collection, version=True), dict(collection, annotations={})]
        for patch in (
            {'type': 'last-read'},
            {'uuid': None},
            {'uuid': ''},
            {'timestamp': None},
            {'timestamp': 'bad'},
            {'book_id': None},
            {'book_id': True},
            {'format': None},
            {'user_type': 'web'},
            {'user_type': 'other', 'user': 'x'},
            {'title': '', 'type': 'bookmark'},
            {'style': {'kind': ['color']}},
            {'removed': True},
            {'notes': []},
            {'spine_index': -1},
            {'spine_index': True},
            {'style': 'bad'},
            {'toc_family_titles': [2]},
        ):
            invalid.append(dict(collection, annotations=[annot, dict(annot, **patch)]))
        invalid.extend((
            dict(collection, annotations=[annot, dict(annot, book_id=21)]),
            dict(collection, annotations=[annot, None]),
            # Annotations of different users must not be merged into one
            dict(collection, annotations=[dict(annot, user_type='local', user='viewer'), dict(annot, user_type='web', user='reader')]),
        ))
        for data in invalid:
            with self.subTest(data=data):
                changes = []
                ok, err = implementation(db, changes.append, 'import', 1, 'FMT1', deepcopy(data), 'local', 'viewer')
                self.assertFalse(ok, err)
                self.assertFalse(changes)
                self.assertEqual(db.annotations_map_for_book(1, 'FMT1'), {})
        for book_id, fmt, user_type, user in (
            (999, 'FMT1', 'local', 'viewer'),
            (1, 'PDF', 'local', 'viewer'),
            (1, 'FMT1', 'other', 'viewer'),
            (1, 'FMT1', 'web', ''),
            (1, 'FMT1', 'local', 'other'),
        ):
            self.assertFalse(implementation(db, None, 'import', book_id, fmt, deepcopy(collection), user_type, user)[0])
        changes = []
        self.assertEqual(
            implementation(db, changes.append, 'import', 1, 'FMT1', dict(collection, annotations=[]), 'local', 'viewer'),
            (True, {'imported': 0, 'unchanged': 0, 'skipped': 0}),
        )
        self.assertFalse(changes)
        for args, msg in (
            (('import',), 'Specify a destination'),
            (('import', 'x', 'FMT1', 'file'), 'must be a number'),
            (('import', '1', 'FMT1', 'file', '--user-type', 'web'), 'Specify --annotation-user'),
            (('import', '1', 'FMT1', 'file', '-s', 'id:1'), 'cannot be used with import'),
            (('import', '1', 'FMT1', 'file', '--annotation-user', 'reader'), 'only be imported for the calibre E-book viewer'),
            (('remove', '1', '--annotation-user', 'reader'), 'cannot be used with remove'),
        ):
            with self.subTest(args=args), self.assertRaisesRegex(SystemExit, msg):
                self.run_annotations(db, *args)
        path = os.path.join(self.mkdtemp(), 'bad.json')
        with open(path, 'w') as f:
            f.write('not JSON')
        with self.assertRaisesRegex(SystemExit, 'Failed to read'):
            self.run_annotations(db, 'import', '1', 'FMT1', path)

    def test_annotations_import_normalization(self):
        from io import BytesIO

        from calibre.db.cli.cmd_annotations import implementation
        from calibre.utils.date import EPOCH
        from calibre.utils.iso8601 import parse_iso8601

        db = self.init_cache()
        db.add_format(1, 'FMT1', BytesIO(b'book'), run_hooks=False)
        newer = '2026-01-01T12:00:00.000Z'
        db.set_annotations_for_book(
            1, 'FMT1', [({'type': 'highlight', 'uuid': 'u', 'highlighted_text': 'Newer', 'timestamp': newer}, (parse_iso8601(newer) - EPOCH).total_seconds())]
        )

        def annot(**kw):
            return dict({'type': 'highlight', 'book_id': 7, 'format': 'FMT1', 'timestamp': '2026-01-01T00:00:00Z'}, **kw)

        collection = {
            'version': 1,
            'type': 'calibre_annotation_collection',
            'annotations': [
                # Older, even though it compares as newer as a string
                annot(uuid='u', highlighted_text='Older', timestamp='2026-01-01T20:00:00+10:00'),
                annot(uuid='naive', timestamp='2026-01-02T03:04:05.678912', unknown={'x': 1}, style={'kind': 'color', 'which': 'yellow'}),
                annot(uuid='other-format', format='PDF'),
            ],
        }
        self.assertEqual(implementation(db, None, 'import', 1, 'FMT1', collection, 'local', 'viewer'), (True, {'imported': 1, 'unchanged': 1, 'skipped': 1}))
        hmap = {h['uuid']: h for h in db.annotations_map_for_book(1, 'FMT1')['highlight']}
        self.assertEqual(set(hmap), {'u', 'naive'})
        self.assertEqual(hmap['u']['highlighted_text'], 'Newer')
        # Timestamps are stored in the UTC format used by the viewers and
        # unknown fields are dropped
        self.assertEqual(
            hmap['naive'], {'type': 'highlight', 'uuid': 'naive', 'timestamp': '2026-01-02T03:04:05.678Z', 'style': {'kind': 'color', 'which': 'yellow'}}
        )

    def test_annotations_import_users(self):
        from io import BytesIO

        from calibre.utils.date import EPOCH
        from calibre.utils.iso8601 import parse_iso8601

        db = self.init_cache()
        for book_id in (1, 2):
            db.add_format(book_id, 'FMT1', BytesIO(b'book'), run_hooks=False)
        db.add_format(1, 'FMT2', BytesIO(b'book'), run_hooks=False)
        ts = '2026-01-01T00:00:00.000Z'

        def bookmark(title):
            return {'type': 'bookmark', 'title': title, 'timestamp': ts}, (parse_iso8601(ts) - EPOCH).total_seconds()

        db.set_annotations_for_book(1, 'FMT1', [bookmark('local')])
        db.set_annotations_for_book(1, 'FMT2', [bookmark('other format')])
        db.set_annotations_for_book(1, 'FMT1', [bookmark('web')], user_type='web', user='reader')
        tdir = self.mkdtemp()

        def export(name, *args):
            path = os.path.join(tdir, name)
            with open(path, 'w') as f:
                f.write(self.run_annotations(db, 'export', '-s', 'id:1', '-f', 'json', *args))
            return path

        path = export('all.json')
        with self.assertRaisesRegex(SystemExit, 'more than one user'):
            self.run_annotations(db, 'import', '2', 'FMT1', path)
        self.assertEqual(db.annotations_map_for_book(2, 'FMT1'), {})
        self.assertEqual(len(self.run_annotations(db, 'list', '--user-type', 'web').splitlines()), 1)
        self.assertEqual(len(self.run_annotations(db, 'list', '--annotation-user', 'viewer').splitlines()), 2)
        # Annotations of another user can be transferred, those of other formats are skipped
        path = export('web.json', '--user-type', 'web', '--annotation-user', 'reader')
        self.assertEqual(self.run_annotations(db, 'import', '2', 'FMT1', path), '1 annotations imported\n')
        path = export('local.json', '--user-type', 'local')
        self.assertEqual(self.run_annotations(db, 'import', '2', 'FMT1', path), '1 annotations imported\n1 annotations of other formats skipped\n')
        self.assertEqual({b['title'] for b in db.annotations_map_for_book(2, 'FMT1')['bookmark']}, {'local', 'web'})
        self.assertEqual(db.annotations_map_for_book(2, 'FMT1', user_type='web', user='reader'), {})

    def test_annotations_import_stdin(self):
        from io import BytesIO, TextIOWrapper
        from unittest.mock import patch

        db = self.init_cache()
        data = json.dumps({
            'version': 1,
            'type': 'calibre_annotation_collection',
            'annotations': [
                {'type': 'bookmark', 'title': 'Imported', 'book_id': 22, 'format': 'FMT1', 'timestamp': '2026-01-01T00:00:00+00:00'},
            ],
        })
        with TextIOWrapper(BytesIO(data.encode('utf-8-sig'))) as stream, patch('sys.stdin', stream):
            self.assertEqual(self.run_annotations(db, 'import', '1', 'FMT1', '-'), '1 annotations imported\n')
        self.assertEqual(db.annotations_map_for_book(1, 'FMT1')['bookmark'][0]['title'], 'Imported')

    def test_annotations_search(self):
        from calibre.utils.date import EPOCH
        from calibre.utils.iso8601 import parse_iso8601
        from calibre.utils.localization import bcp47_locale_name
        from calibre_extensions.sqlite_extension import set_ui_language

        db = self.init_cache()
        # Stemming follows the UI language. These fixtures use English words,
        # regardless of the locale of the machine running the tests.
        self.addCleanup(set_ui_language, bcp47_locale_name())
        set_ui_language('en')
        timestamp = '2026-01-01T00:00:00+00:00'

        def a(**kw):
            kw['timestamp'] = timestamp
            return kw, (parse_iso8601(timestamp) - EPOCH).total_seconds()

        db.set_annotations_for_book(
            1,
            'EPUB',
            [
                a(type='highlight', uuid='phrase', highlighted_text='The climate change discussion'),
                a(type='highlight', uuid='notes', highlighted_text='A highlighted passage', notes='Private cobalt\x1b[31m note\x9b\ncontinued'),
                a(type='highlight', uuid='stem', highlighted_text='She was running'),
                a(type='highlight', uuid='snippet', highlighted_text=' '.join(['before'] * 80 + ['needle'] + ['after'] * 80)),
                a(type='highlight', uuid='removed', highlighted_text='climate change', removed=True),
                a(type='bookmark', title='Climate change bookmark', pos_type='epubcfi'),
            ],
        )
        db.set_annotations_for_book(2, 'EPUB', [a(type='highlight', uuid='other', highlighted_text='climate science')])
        changes = []
        for is_remote in (False, True):
            with self.subTest(is_remote=is_remote):

                def run(*args, is_remote=is_remote):
                    return self.run_annotations(db, 'search', *args, is_remote=is_remote, changes=changes)

                phrase = json.loads(run('"climate change"', '-f', 'json'))
                self.assertEqual({a['annotation']['type'] for a in phrase}, {'bookmark', 'highlight'})
                self.assertEqual({a['book_id'] for a in phrase}, {1})
                self.assertEqual({a['title'] for a in phrase}, {'Title Two'})
                self.assertTrue(all(a['id'] > 0 and a['format'] == 'EPUB' and a['user_type'] == 'local' and a['user'] == 'viewer' for a in phrase))
                self.assertEqual(len(json.loads(run('climate', '-f', 'json'))), 3)
                self.assertEqual(len(json.loads(run('climate', '-f', 'json', '-s', 'id:2'))), 1)
                self.assertEqual(json.loads(run('climate', '-f', 'json', '-s', 'id:999')), [])
                self.assertEqual(len(json.loads(run('climate', '-f', 'json', '-t', 'bookmark'))), 1)
                self.assertEqual(len(json.loads(run('run', '-f', 'json'))), 1)
                self.assertEqual(json.loads(run('run', '--no-stemming', '-f', 'json')), [])
                self.assertEqual(run('missingword'), '')
                snippet = json.loads(run('needle', '-f', 'json'))[0]
                self.assertIn('needle', snippet['text'])
                self.assertLess(len(snippet['text']), len(snippet['annotation']['highlighted_text']))
                notes = run('cobalt').splitlines()
                self.assertEqual(len(notes), 1)
                self.assertEqual(len(notes[0].split('\t')), 6)
                self.assertIn('cobalt', notes[0])
                self.assertNotIn('\x1b', notes[0])
                raw = run('cobalt', '-f', 'json')
                self.assertNotIn('\x9b', raw)
                notes = json.loads(raw)
                self.assertEqual(notes[0]['annotation']['uuid'], 'notes')
                self.assertIn('\x9b', notes[0]['annotation']['notes'])
                self.assertNotIn('\x1f', notes[0]['text'])
        self.assertFalse(changes)

    def test_annotations_search_invalid(self):
        db = self.init_cache()
        for args, msg in (
            (('search',), 'non-empty'),
            (('search', ''), 'non-empty'),
            (('search', ' '), 'non-empty'),
            (('search', 'one', 'two'), 'non-empty'),
            (('search', 'one', '-f', 'markdown'), 'text or json'),
            (('search', '"unterminated'), 'Failed'),
            (('search', 'word', '-s', '('), 'Failed to parse search query'),
            (('list', '--no-stemming'), 'only be used with search'),
        ):
            for is_remote in (False, True):
                with self.subTest(args=args, is_remote=is_remote), self.assertRaisesRegex(SystemExit, msg):
                    self.run_annotations(db, *args, is_remote=is_remote)


class SavedSearchesTest(BaseTest):
    def test_saved_searches_remote(self):
        from calibre.db.cli.cmd_saved_searches import implementation

        db = self.init_cache()
        self.addCleanup(db.close)
        changes = []
        tpl = 'template:"program: 1#@#:t:1"'
        # A Virtual library, created locally, that uses a saved search
        implementation(db, None, 'add', 'foo', 'id:1')
        db.set_pref('virtual_libraries', {'VL': 'search:foo'})
        implementation(db, None, 'add', 'local_tpl', tpl)
        # Remote clients must not be able to store templates, since the Virtual library is evaluated with templates allowed
        for val in (tpl, 'id:9999 and ' + tpl, 'search:local_tpl'):
            with self.subTest(val=val), self.assertRaisesRegex(ValueError, 'Templates are not allowed') as cm:
                implementation(db, changes.append, 'add', 'foo', val)
            self.assertTrue(getattr(cm.exception, 'suppress_traceback', False))
        with self.assertRaisesRegex(ValueError, 'Failed to parse search query'):
            implementation(db, changes.append, 'add', 'foo', '(id:1')
        self.assertEqual(db.saved_search_lookup('foo'), 'id:1')
        self.assertEqual(db.books_in_virtual_library('VL'), {1})
        self.assertFalse(changes)
        implementation(db, changes.append, 'add', 'foo', 'id:2')
        self.assertEqual(db.books_in_virtual_library('VL'), {2})
        self.assertEqual(len(changes), 1)
        # Local clients are trusted
        implementation(db, None, 'add', 'foo', tpl)
        self.assertEqual(db.books_in_virtual_library('VL'), {1, 2, 3})


class DataFilesTest(BaseTest):
    def run_data_files(self, db, *args, is_remote=False):
        from calibre.db.cli.cmd_data_files import main, option_parser
        from calibre.db.cli.main import get_parser
        from calibre.utils.serialize import msgpack_dumps, msgpack_loads

        class DBCtx:
            def __init__(self):
                self.is_remote = is_remote

            def path(self, path):
                if is_remote:
                    with open(path, 'rb') as f:
                        return path, f.read()
                return path

            def run(self, name, *args):
                from calibre.db.cli import module_for_cmd

                impl = module_for_cmd(name).implementation
                if is_remote:
                    return msgpack_loads(msgpack_dumps(impl(db, lambda changes: None, *msgpack_loads(msgpack_dumps(args)))))
                return impl(db, None, *args)

        ctx = DBCtx()
        opts, args = option_parser(get_parser, []).parse_args(list(args))
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(main(opts, args, ctx), 0)
        return out.getvalue()

    def test_data_files(self):
        db = self.init_cache()
        source, output = os.path.join(self.mkdtemp(), 'source.txt'), os.path.join(self.mkdtemp(), 'result.txt')
        original = db.format(1, 'FMT1')
        for is_remote in (False, True):
            with self.subTest(is_remote=is_remote):

                def run(*args, is_remote=is_remote):
                    return self.run_data_files(db, *args, is_remote=is_remote)

                self.assertEqual(json.loads(run('list', '1', '--for-machine')), [])
                with open(source, 'wb') as f:
                    f.write(b'\0supplement\xff')
                run('add', '1', source, '--name', '研究/source.txt')
                listing = json.loads(run('list', '1', '--for-machine'))
                self.assertEqual([(x['name'], x['size']) for x in listing], [('研究/source.txt', 12)])
                self.assertGreater(listing[0]['mtime'], 0)
                self.assertEqual(run('list', '1').split('\t')[:2], ['研究/source.txt', '12'])
                run('get', '1', '研究/source.txt', '--output', output)
                with open(output, 'rb') as f:
                    self.assertEqual(f.read(), b'\0supplement\xff')
                with self.assertRaisesRegex(SystemExit, 'already exists'):
                    run('get', '1', '研究/source.txt', '--output', output)
                with self.assertRaisesRegex(SystemExit, 'already exist'):
                    run('add', '1', source, '--name', '研究/source.txt')
                with open(source, 'wb') as f:
                    f.write(b'new')
                run('add', '1', source, '--name', '研究/source.txt', '--replace')
                run('add', '1', source)
                with self.assertRaisesRegex(SystemExit, 'already exist'):
                    run('rename', '1', '研究/source.txt', 'source.txt')
                run('rename', '1', '研究/source.txt', 'source.txt', '--replace')
                run('rename', '1', 'source.txt', 'source.txt')
                run('get', '1', 'source.txt', '--output', output, '--replace')
                with open(output, 'rb') as f:
                    self.assertEqual(f.read(), b'new')
                with self.assertRaisesRegex(SystemExit, 'No data file'):
                    run('get', '1', 'missing', '--output', output, '--replace')
                with open(output, 'rb') as f:
                    self.assertEqual(f.read(), b'new')
                run('rename', '1', 'source.txt', 'sub/deeper/moved.txt')
                run('rename', '1', 'sub/deeper/moved.txt', 'sub/other/moved.txt')
                run('remove', '1', 'sub/other/moved.txt', *(('--permanent',) if is_remote else ()))
                self.assertEqual(json.loads(run('list', '1', '--for-machine')), [])
                # Directories left empty are removed, but not data/ itself
                self.assertEqual(os.listdir(os.path.join(db.backend.library_path, db.field_for('path', 1), 'data')), [])
                os.remove(output)
        self.assertEqual(db.format(1, 'FMT1'), original)

    def test_data_files_invalid_names(self):
        from calibre.db.cli.cmd_data_files import implementation

        db = self.init_cache()
        source = os.path.join(self.mkdtemp(), 'source')
        with open(source, 'wb') as f:
            f.write(b'file')
        self.run_data_files(db, 'add', '1', source)
        for name in (
            '',
            '../cover.jpg',
            '/tmp/file',
            'C:\\file',
            'x/../../cover.jpg',
            'x\\..\\cover.jpg',
            'x:stream',
            'x\0y',
            'x//y',
            'x?y',
            'x|y',
            'x\ty',
            'x<y>',
            'CON',
            'nul.txt',
            'sub/Com1.txt',
            'trailing.',
            'trailing ',
            'dir./x',
        ):
            for action, args in (('add', (source, False)), ('get', (None,)), ('rename', ('new', False)), ('remove', (True,))):
                with self.subTest(name=name, action=action):
                    self.assertFalse(implementation(db, None, action, 1, name, *args)[0])
            self.assertFalse(implementation(db, None, 'rename', 1, 'source', name, True)[0])
        self.assertFalse(implementation(db, None, 'list', 999)[0])
        self.assertFalse(implementation(db, None, 'unknown', 1)[0])
        # Malformed remote requests are rejected with an error, not an exception
        remote = lambda changes: None  # ruff: ignore[lambda-assignment]
        for action, args in (
            ('list', ('extra',)),
            ('add', ('x', 'abc', False)),
            ('add', ('x', {'a': 1}, False)),
            ('add', ('x', ('a', 'b'), False)),
            ('add', ('x', ('a', b'b'), 'yes')),
            ('get', (5, None)),
            ('get', (None, None)),
            ('rename', ('source', ['a'], False)),
            ('remove', ('source',)),
            ('remove', ('source', None)),
        ):
            with self.subTest(action=action, args=args):
                self.assertEqual(implementation(db, remote, action, 1, *args), (False, f'Invalid arguments for: {action}'))
        self.assertFalse(implementation(db, remote, 'list', '1')[0])
        # Names that are valid on some platforms are accepted
        for name in ('a..b.txt', '.hidden', 'console.txt', 'COM10', 'x+y'):
            with self.subTest(name=name):
                self.assertTrue(implementation(db, remote, 'add', 1, name, (name, b'x'), False)[0])
                self.assertTrue(implementation(db, remote, 'remove', 1, name, True)[0])
        # Even a crafted remote request must not use a server pathname as
        # the uploaded data, or use its get destination to write on the server.
        dest = os.path.join(self.mkdtemp(), 'server-output')
        self.assertEqual(implementation(db, lambda changes: None, 'get', 1, 'source', dest), (True, b'file'))
        self.assertFalse(os.path.exists(dest))
        self.assertEqual([x['name'] for x in implementation(db, None, 'list', 1)[1]], ['source'])
        self.assertTrue(implementation(db, lambda changes: None, 'add', 1, 'uploaded', (source, b'client bytes'), False)[0])
        self.assertEqual(implementation(db, lambda changes: None, 'get', 1, 'uploaded', dest), (True, b'client bytes'))

    def test_data_files_symlinks(self):
        from calibre.db.cli.cmd_data_files import implementation

        db = self.init_cache()
        root = os.path.join(db.backend.library_path, db.field_for('path', 1), 'data')
        os.makedirs(root)
        link = os.path.join(root, 'outside')
        try:
            os.symlink(os.path.dirname(root), link, target_is_directory=True)
        except OSError, NotImplementedError:
            self.skipTest('Creating symlinks is unavailable')
        for action, args in (('add', (b'', True)), ('get', (None,)), ('remove', (True,))):
            self.assertFalse(implementation(db, None, action, 1, 'outside/cover.jpg', *args)[0])
        self.assertIsNotNone(db.cover(1))
        # Symlinks that resolve outside the data directory are omitted from
        # the listing rather than preventing listing other files
        os.symlink(os.path.join(os.path.dirname(root), 'cover.jpg'), os.path.join(root, 'cover-link'))
        with open(os.path.join(root, 'regular'), 'wb') as f:
            f.write(b'x')
        self.assertEqual([x['name'] for x in implementation(db, None, 'list', 1)[1]], ['regular'])
        self.assertFalse(implementation(db, None, 'get', 1, 'cover-link', None)[0])

    def test_data_files_existing_names(self):
        from calibre.db.cli.cmd_data_files import implementation

        db = self.init_cache()
        root = os.path.join(db.backend.library_path, db.field_for('path', 1), 'data')
        os.makedirs(root)
        # Names that are not accepted for new files can still be managed
        # if they exist, for example, created by other programs
        try:
            with open(os.path.join(root, 'Notes: one.txt'), 'wb') as f:
                f.write(b'colon')
        except OSError:
            self.skipTest('Colons in filenames are unsupported')
        if os.listdir(root) != ['Notes: one.txt']:
            # On NTFS, the colon creates an alternate data stream instead
            self.skipTest('Colons in filenames are unsupported')
        self.assertEqual([x['name'] for x in implementation(db, None, 'list', 1)[1]], ['Notes: one.txt'])
        self.assertEqual(implementation(db, lambda changes: None, 'get', 1, 'Notes: one.txt', None), (True, b'colon'))
        self.assertFalse(implementation(db, None, 'rename', 1, 'Notes: one.txt', 'Notes: two.txt', False)[0])
        self.assertTrue(implementation(db, None, 'rename', 1, 'Notes: one.txt', 'notes.txt', False)[0])
        self.assertFalse(implementation(db, None, 'rename', 1, 'notes.txt', 'Notes: one.txt', False)[0])
        with open(os.path.join(root, 'Notes: one.txt'), 'wb') as f:
            f.write(b'colon')
        self.assertTrue(implementation(db, None, 'remove', 1, 'Notes: one.txt', True)[0])
        self.assertEqual([x['name'] for x in implementation(db, None, 'list', 1)[1]], ['notes.txt'])
        # \ is a separator for the backend, so such names give a clear error
        if os.sep == '/':
            with open(os.path.join(root, 'a\\b.txt'), 'wb') as f:
                f.write(b'x')
            self.assertIn('a\\b.txt', [x['name'] for x in implementation(db, None, 'list', 1)[1]])
            for action, args in (('get', (None,)), ('rename', ('c.txt', False)), ('remove', (True,))):
                ok, msg = implementation(db, None, action, 1, 'a\\b.txt', *args)
                self.assertFalse(ok)
                self.assertIn('backslash', msg)
            self.assertTrue(os.path.exists(os.path.join(root, 'a\\b.txt')))
        # \ is accepted as a separator in names
        os.mkdir(os.path.join(root, 'sub'))
        with open(os.path.join(root, 'sub', 'x.txt'), 'wb') as f:
            f.write(b'sub')
        self.assertEqual(implementation(db, lambda changes: None, 'get', 1, 'sub\\x.txt', None), (True, b'sub'))
        # Names differing only in case match on case-insensitive filesystems
        orig_case_sensitive = db.backend.is_case_sensitive
        try:
            db.backend.is_case_sensitive = True
            self.assertFalse(implementation(db, lambda changes: None, 'get', 1, 'SUB/X.txt', None)[0])
            db.backend.is_case_sensitive = False
            self.assertEqual(implementation(db, lambda changes: None, 'get', 1, 'SUB/X.txt', None), (True, b'sub'))
        finally:
            db.backend.is_case_sensitive = orig_case_sensitive
        # Only regular files are listed, special files such as FIFOs could
        # block reads indefinitely
        if hasattr(os, 'mkfifo'):
            os.mkfifo(os.path.join(root, 'fifo'))
            self.assertNotIn('fifo', [x['name'] for x in implementation(db, None, 'list', 1)[1]])
            self.assertFalse(implementation(db, lambda changes: None, 'get', 1, 'fifo', None)[0])

    def test_data_files_output(self):
        import stat

        from calibre.constants import get_umask, iswindows

        db = self.init_cache()
        source = os.path.join(self.mkdtemp(), 'source')
        with open(source, 'wb') as f:
            f.write(b'file')
        self.run_data_files(db, 'add', '1', source)
        tdir = self.mkdtemp()
        output = os.path.join(tdir, 'output')
        for is_remote in (False, True):
            with self.subTest(is_remote=is_remote):
                self.run_data_files(db, 'get', '1', 'source', '--output', output, is_remote=is_remote)
                if not iswindows:
                    self.assertEqual(stat.S_IMODE(os.stat(output).st_mode), 0o666 & ~get_umask())
                    os.chmod(output, 0o640)
                    self.run_data_files(db, 'get', '1', 'source', '--output', output, '--replace', is_remote=is_remote)
                    self.assertEqual(stat.S_IMODE(os.stat(output).st_mode), 0o640)
                    # Replacing writes through symlinks rather than replacing them
                    link = os.path.join(tdir, 'link')
                    os.symlink(output, link)
                    with open(output, 'wb') as f:
                        f.write(b'old')
                    self.run_data_files(db, 'get', '1', 'source', '--output', link, '--replace', is_remote=is_remote)
                    self.assertTrue(os.path.islink(link))
                    with open(output, 'rb') as f:
                        self.assertEqual(f.read(), b'file')
                    os.remove(link)
                    # Read-only outputs are not replaced
                    os.chmod(output, 0o440)
                    if not os.access(output, os.W_OK):  # not running as root
                        with self.assertRaisesRegex(SystemExit, 'Failed to save'):
                            self.run_data_files(db, 'get', '1', 'source', '--output', output, '--replace', is_remote=is_remote)
                    os.chmod(output, 0o640)
                # A missing data file does not leave an empty output behind
                missing = os.path.join(tdir, 'missing')
                with self.assertRaisesRegex(SystemExit, 'No data file'):
                    self.run_data_files(db, 'get', '1', 'nonexistent', '--output', missing, is_remote=is_remote)
                self.assertFalse(os.path.exists(missing))
                for args in ((os.path.join(tdir, 'nodir', 'x'),), (tdir, '--replace'), (os.path.join(tdir, 'nodir', 'x'), '--replace')):
                    with self.assertRaises(SystemExit):
                        self.run_data_files(db, 'get', '1', 'source', '--output', *args, is_remote=is_remote)
                os.remove(output)
        self.assertEqual(sorted(os.listdir(tdir)), [])

    def test_data_files_options(self):
        db = self.init_cache()
        for args in (
            (),
            ('unknown',),
            ('list',),
            ('list', 'one'),
            ('list', '1', 'extra'),
            ('get', '1', 'file'),
            ('list', '1', '--replace'),
            ('list', '1', '--permanent'),
            ('list', '1', '--name', 'x'),
            ('list', '1', '--output', 'x'),
            ('remove', '1', 'x', '--for-machine'),
        ):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                self.run_data_files(db, *args)


class TrashTest(BaseTest):
    def run_trash(self, db, *args, is_remote=False):
        from calibre.db.cli.cmd_trash import implementation, main, option_parser
        from calibre.db.cli.main import get_parser
        from calibre.utils.serialize import msgpack_dumps, msgpack_loads

        changes = []

        class DBCtx:
            def run(self, name, *args):
                if is_remote:
                    # Results are sent over the network by the Content server
                    return msgpack_loads(msgpack_dumps(implementation(db, changes.append, *msgpack_loads(msgpack_dumps(args)))))
                return implementation(db, None, *args)

        opts, args = option_parser(get_parser, []).parse_args(list(args))
        self.changes = changes
        try:
            with redirect_stdout(StringIO()) as out:
                main(opts, args, DBCtx())
        finally:
            self.last_output = out.getvalue()
        return self.last_output

    def test_trash(self):
        db = self.init_cache()
        self.addCleanup(db.close)
        self.assertEqual(self.run_trash(db, 'list'), '')
        titles = {i: db.field_for('title', i) for i in db.all_book_ids()}
        fmts = db.formats(1)
        # The trash is listed using the metadata backups of the books, as in a real library
        db.mark_as_dirty(db.all_book_ids())
        db.dump_metadata()
        db.remove_books((2, 3))
        db.remove_formats({1: fmts})

        out = self.run_trash(db, 'list')
        self.assertIn('Books:\n', out)
        self.assertIn(f'2\t{titles[2]}\t', out)
        self.assertIn(f'1\t{titles[1]}\t', out.partition('Formats:')[2])
        self.assertIn(', '.join(sorted(fmts)), out.partition('Formats:')[2])
        for is_remote in (False, True):
            with self.subTest(is_remote=is_remote):
                listed = json.loads(self.run_trash(db, 'list', '--for-machine', is_remote=is_remote))
                self.assertEqual({x['id'] for x in listed['books']}, {2, 3})
                self.assertEqual([(x['id'], sorted(x['formats'])) for x in listed['formats']], [(1, sorted(fmts))])
                self.assertEqual(listed['books'][0]['title'], titles[listed['books'][0]['id']])

        # Restore books, through the server too
        self.assertEqual(self.run_trash(db, 'restore', '2', is_remote=True), 'One book restored\n')
        self.assertEqual([type(c).__name__ for c in self.changes], ['BooksAdded'])
        self.assertTrue(db.has_id(2))
        self.assertEqual(db.field_for('title', 2), titles[2])
        # Restore formats
        self.assertEqual(self.run_trash(db, '--formats', 'restore', '1', is_remote=True), 'The formats of one book restored\n')
        self.assertEqual(set(db.formats(1)), set(fmts))
        self.assertEqual(self.changes[0].formats_map, {1: sorted(fmts)})
        books, formats = db.list_trash_entries()
        self.assertEqual(({e.book_id for e in books}, formats), ({3}, []))

        for args, msg in (
            ((), 'must specify an action'),
            (('frob',), 'not recognized'),
            (('list', '1'), 'Too many arguments'),
            (('empty', '1'), 'Too many arguments'),
            (('restore',), 'ids of the books'),
            (('restore', 'x'), 'must be numbers'),
            (('restore', '3,1'), 'No entries in the .+ for the books: 1$'),
            (('delete', '--formats', '3'), 'No entries in the .+ for the books: 3$'),
        ):
            with self.subTest(args=args), self.assertRaisesRegex(SystemExit, msg):
                self.run_trash(db, *args)
        # Nothing is restored if any of the books are not in the trash
        self.assertFalse(db.has_id(3))

        self.assertEqual(self.run_trash(db, 'delete', '3'), 'One entry permanently deleted\n')
        self.assertEqual(db.list_trash_entries(), ([], []))
        db.remove_books((2,))
        self.assertIn('emptied', self.run_trash(db, 'empty'))
        self.assertEqual(db.list_trash_entries(), ([], []))

    def test_trash_failures(self):
        from unittest.mock import patch

        from calibre.db.cli.cmd_trash import implementation

        db = self.init_cache()
        self.addCleanup(db.close)
        db.mark_as_dirty(db.all_book_ids())
        db.dump_metadata()
        fmts = sorted(db.formats(1))
        self.assertGreater(len(fmts), 1)
        db.remove_formats({1: fmts, 2: db.formats(2)})
        db.remove_books((2,))

        self.assertEqual(implementation(db, None, 'frob'), (False, 'Unknown action: frob'))
        with self.assertRaisesRegex(SystemExit, 'cannot be used'):
            self.run_trash(db, 'list', '--formats')

        # The removed formats of a book that no longer exists cannot be restored
        out = self.run_trash(db, 'list')
        self.assertIn('(not restorable)', [line for line in out.splitlines() if line.startswith('2\t')][-1])
        self.assertNotIn('(not restorable)', [line for line in out.splitlines() if line.startswith('1\t')][-1])
        listed = json.loads(self.run_trash(db, 'list', '--for-machine'))
        self.assertEqual({x['id']: x['restorable'] for x in listed['formats']}, {1: True, 2: False})
        with self.assertRaisesRegex(SystemExit, '2: The book no longer exists'):
            self.run_trash(db, 'restore', '--formats', '2')
        self.assertIn('The formats of 0 books restored', self.last_output)

        # A book whose formats are only partly restored is not counted as restored, the restored formats are notified
        orig = db.move_format_from_trash

        def fail_second(book_id, fmt):
            if fmt == fmts[1]:
                raise ValueError('failed')
            return orig(book_id, fmt)

        with patch.object(db, 'move_format_from_trash', side_effect=fail_second):
            with self.assertRaisesRegex(SystemExit, 'Failed to restore:\n1: failed'):
                self.run_trash(db, 'restore', '--formats', '1', is_remote=True)
        self.assertIn('The formats of 0 books restored', self.last_output)
        self.assertEqual(self.changes[0].formats_map, {1: [fmts[0]]})
        self.assertEqual(db.formats(1), (fmts[0],))

        # Deleting continues past failures
        db.remove_books((3,))
        orig_delete = db.delete_trash_entry

        def fail_delete(book_id, category):
            if book_id == 2:
                raise OSError('failed')
            return orig_delete(book_id, category)

        with patch.object(db, 'delete_trash_entry', side_effect=fail_delete):
            with self.assertRaisesRegex(SystemExit, 'Failed to delete:\n2: failed'):
                self.run_trash(db, 'delete', '2,3')
        self.assertEqual(self.last_output, 'One entry permanently deleted\n')
        self.assertEqual([e.book_id for e in db.list_trash_entries()[0]], [2])
        self.assertEqual(self.run_trash(db, 'delete', '--formats', '1,2'), '2 entries permanently deleted\n')
        self.assertEqual(db.list_trash_entries()[1], [])


class VirtualLibrariesTest(BaseTest):
    def run_vls(self, db, *args, is_remote=False, changes=None):
        from calibre.db.cli.cmd_virtual_libraries import implementation, main, option_parser
        from calibre.db.cli.main import get_parser
        from calibre.utils.serialize import msgpack_dumps, msgpack_loads

        class DBCtx:
            def run(self, name, *args):
                if is_remote:
                    # Results are sent over the network by the Content server
                    notify_changes = (changes if changes is not None else []).append
                    return msgpack_loads(msgpack_dumps(implementation(db, notify_changes, *msgpack_loads(msgpack_dumps(args)))))
                return implementation(db, None, *args)

        opts, args = option_parser(get_parser, []).parse_args(list(args))
        with redirect_stdout(StringIO()) as out:
            main(opts, args, DBCtx())
        return out.getvalue()

    def test_virtual_libraries(self):
        db = self.init_cache()
        self.addCleanup(db.close)
        self.assertEqual(self.run_vls(db), '')
        self.assertEqual(self.run_vls(db, 'add', 'One', 'title:"=Title One"'), 'Virtual library One added, with one book\n')
        self.assertEqual(self.run_vls(db, 'add', 'Both', 'id:1 or id:2', is_remote=True), 'Virtual library Both added, with 2 books\n')
        self.assertEqual(db.pref('virtual_libraries'), {'One': 'title:"=Title One"', 'Both': 'id:1 or id:2'})
        self.assertEqual(db.search('vl:Both'), {1, 2})
        self.assertEqual(self.run_vls(db, 'list'), 'Both\tid:1 or id:2\t2\nOne\ttitle:"=Title One"\t1\n')
        for is_remote in (False, True):
            with self.subTest(is_remote=is_remote):
                listed = json.loads(self.run_vls(db, 'list', '--for-machine', is_remote=is_remote))
                self.assertEqual(listed, [{'name': 'Both', 'search': 'id:1 or id:2', 'count': 2}, {'name': 'One', 'search': 'title:"=Title One"', 'count': 1}])

        with self.assertRaisesRegex(SystemExit, 'already exists'):
            self.run_vls(db, 'add', 'One', 'id:3')
        self.run_vls(db, 'add', '--replace', 'One', 'id:3')
        self.assertEqual(db.search('vl:One'), {3})

        # Templates are not allowed for remote clients
        db.set_pref('virtual_libraries', dict(db.pref('virtual_libraries'), T='template:"program: 1"#@#:t:1'))
        self.assertIn('T\ttemplate:"program: 1"#@#:t:1\tinvalid search', self.run_vls(db, 'list', is_remote=True))
        with self.assertRaisesRegex(SystemExit, 'Templates are not allowed'):
            self.run_vls(db, 'add', 'T2', 'template:"program: 1"#@#:t:1', is_remote=True)

        self.run_vls(db, 'rename', 'Both', 'Two books')
        self.assertEqual(set(db.pref('virtual_libraries')), {'One', 'Two books', 'T'})
        self.assertEqual(db.search('vl:"Two books"'), {1, 2})
        self.assertEqual(self.run_vls(db, 'remove', 'One', 'T', is_remote=True), '2 Virtual libraries removed\n')
        self.assertEqual(db.pref('virtual_libraries'), {'Two books': 'id:1 or id:2'})

        for args, msg in (
            (('frob',), 'not recognized'),
            (('list', 'x'), 'Too many arguments'),
            (('add', 'x'), 'name and a search expression'),
            (('add', ' ', 'id:1'), 'must not be empty'),
            (('add', 'Bad', '(id:1'), 'Failed to parse search query'),
            (('add', 'Two books', 'id:1'), 'already exists'),
            (('rename', 'x'), 'its new name'),
            (('rename', 'Nothing', 'x'), 'No Virtual library named: Nothing'),
            (('rename', 'Two books', ' '), 'must not be empty'),
            (('remove',), 'names of the Virtual libraries'),
            (('remove', 'Two books', 'Nothing'), 'No Virtual libraries named: Nothing'),
            (('add', '*x', 'id:1'), 'cannot begin with'),
            (('rename', 'Two books', '*x'), 'cannot begin with'),
        ):
            with self.subTest(args=args), self.assertRaisesRegex(SystemExit, msg):
                self.run_vls(db, *args)
        # Nothing is removed if any of the names do not exist
        self.assertEqual(db.pref('virtual_libraries'), {'Two books': 'id:1 or id:2'})

    def test_virtual_libraries_edge_cases(self):
        from calibre.srv.changes import VirtualLibrariesChanged

        db = self.init_cache()
        self.addCleanup(db.close)
        changes = []
        tpl = 'template:"program: 1#@#:t:1"'
        self.run_vls(db, 'add', 'A', 'id:1')
        self.run_vls(db, 'add', 'B', 'id:2')

        # Templates are detected even where searching would not reach them, as they are evaluated later with templates allowed
        db.saved_search_add('local_tpl', tpl)
        for expr in ('id:9999 and ' + tpl, 'search:local_tpl'):
            with self.subTest(expr=expr), self.assertRaisesRegex(SystemExit, 'Templates are not allowed'):
                self.run_vls(db, 'add', 'T', expr, is_remote=True, changes=changes)
        self.assertNotIn('T', db.pref('virtual_libraries'))

        # A replaced search that uses the Virtual library itself is recursive
        with self.assertRaisesRegex(SystemExit, 'Failed to parse search query'):
            self.run_vls(db, 'add', '--replace', 'A', 'vl:A or id:3')
        self.assertEqual(db.pref('virtual_libraries'), {'A': 'id:1', 'B': 'id:2'})
        self.assertEqual(db.search('vl:A'), {1})
        self.assertFalse(changes)

        # Renaming to the same name does nothing, renaming updates the Virtual library used on startup
        self.run_vls(db, 'rename', 'A', 'A', is_remote=True, changes=changes)
        db.set_pref('virtual_lib_on_startup', 'A')
        self.run_vls(db, 'rename', 'A', 'C', is_remote=True, changes=changes)
        self.assertEqual(db.pref('virtual_libraries'), {'C': 'id:1', 'B': 'id:2'})
        self.assertEqual(db.pref('virtual_lib_on_startup'), 'C')

        # Repeated names are removed once
        self.assertEqual(self.run_vls(db, 'remove', 'C', 'C', is_remote=True, changes=changes), 'One Virtual library removed\n')
        self.assertEqual(db.pref('virtual_libraries'), {'B': 'id:2'})
        self.assertEqual(db.pref('virtual_lib_on_startup'), '')

        self.run_vls(db, 'add', '--replace', 'B', 'id:3', is_remote=True, changes=changes)
        self.assertTrue(all(isinstance(c, VirtualLibrariesChanged) for c in changes))
        self.assertEqual(
            [(set(c.added), set(c.removed), c.renamed) for c in changes],
            [(set(), set(), (('A', 'C'),)), (set(), {'C'}, ()), ({'B'}, set(), ())],
        )


def find_tests():
    loader = unittest.defaultTestLoader
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(PrintCheckLibraryResultsTest),
        loader.loadTestsFromTestCase(ListCategoriesTest),
        loader.loadTestsFromTestCase(SetCustomTest),
        loader.loadTestsFromTestCase(FTSSearchTest),
        loader.loadTestsFromTestCase(NotesTest),
        loader.loadTestsFromTestCase(RestoreDatabaseTest),
        loader.loadTestsFromTestCase(ItemsTest),
        loader.loadTestsFromTestCase(AnnotationsTest),
        loader.loadTestsFromTestCase(SavedSearchesTest),
        loader.loadTestsFromTestCase(TrashTest),
        loader.loadTestsFromTestCase(DataFilesTest),
        loader.loadTestsFromTestCase(VirtualLibrariesTest),
    ))
