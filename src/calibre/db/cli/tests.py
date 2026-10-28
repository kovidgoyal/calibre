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
                return implementation(db, None, *args)

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
            ((), 'must specify an action'),
        ):
            with self.subTest(args=args), self.assertRaisesRegex(SystemExit, msg):
                self.run_notes(db, *args)

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
            ((), 'must specify an action'),
        ):
            with self.subTest(args=args), self.assertRaisesRegex(SystemExit, msg):
                self.run_annotations(db, *args)
        self.assertEqual(len(self.run_annotations(db, 'list').splitlines()), 3)


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
        loader.loadTestsFromTestCase(TrashTest),
    ))
