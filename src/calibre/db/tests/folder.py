#!/usr/bin/env python
# License: GPLv3

import os
from io import BytesIO

from calibre.db.tests.base import BaseTest
from calibre.db.tests.filesystem import FilesystemTest
from calibre.ebooks.metadata.book.base import Metadata


class FolderTest(BaseTest):
    def test_builtin_opf_and_old_library(self):
        from calibre.ebooks.metadata.opf2 import OPF, metadata_to_opf

        cache = self.init_cache()
        self.assertFalse(cache.field_metadata['library_path']['is_custom'])
        self.assertNotIn('#library_path', cache.field_metadata)
        before = cache.field_for('path', 1)
        self.assertNotIn(b'calibre:library_path', metadata_to_opf(cache.get_metadata(1)))
        cache.set_field('library_path', {1: 'electronics/books'})
        raw = metadata_to_opf(cache.get_metadata(1))
        self.assertIn(b'<meta name="calibre:library_path" content="electronics/books"', raw)
        self.assertNotIn(b'calibre:user_metadata:#library_path', raw)
        self.assertEqual(OPF(BytesIO(raw)).to_book_metadata().library_path, 'electronics/books')
        cache.set_field('library_path', {1: ''})
        self.assertEqual(cache.field_for('path', 1), before)
        self.assertNotIn(b'calibre:library_path', metadata_to_opf(cache.get_metadata(1)))
        cache.close()
        cache = self.init_cache()
        self.assertEqual(cache.field_for('path', 1), before)
        self.assertFalse(cache.field_for('library_path', 1))

    def test_migrate_custom_library_path(self):
        from calibre.ebooks.metadata.opf2 import metadata_to_opf

        cache = self.init_cache()
        cache.set_field('library_path', {1: 'electronics/books'})
        path, data = cache.field_for('path', 1), self.contents(cache)
        db = cache.backend
        num = db.create_custom_column('library_path', 'Путь размещения', 'text', False)
        db.execute(f'INSERT INTO custom_column_{num}(id,value) VALUES(1,?)', ('electronics/books',))
        db.execute(f'INSERT INTO books_custom_column_{num}_link(book,value) VALUES(1,1)')
        db.execute('DELETE FROM books_library_paths_link; DELETE FROM library_paths;')
        db.prefs['test_path_preference'] = {'#library_path': '{#library_path}'}
        cache.close()
        cache = self.init_cache()
        self.assertEqual(cache.field_for('library_path', 1), 'electronics/books')
        self.assertEqual(cache.field_for('path', 1), path)
        self.assertEqual(self.contents(cache), data)
        self.assertNotIn('#library_path', cache.field_metadata)
        self.assertEqual(cache.pref('test_path_preference'), {'library_path': '{library_path}'})
        self.assertIn(1, cache.dirtied_cache)
        self.assertNotIn(b'calibre:user_metadata:#library_path', metadata_to_opf(cache.get_metadata(1)))
        cache.close()
        cache = self.init_cache()
        self.assertEqual(cache.field_for('library_path', 1), 'electronics/books')

    def test_import_old_custom_opf(self):
        from calibre.ebooks.metadata.opf2 import OPF, metadata_to_opf

        mi = Metadata('Legacy', ['Author'])
        mi.set_user_metadata('#library_path', {
            'datatype': 'text', 'is_multiple': {}, 'name': 'Путь размещения',
            '#value#': 'electronics/books',
        })
        parsed = OPF(BytesIO(metadata_to_opf(mi))).to_book_metadata()
        self.assertEqual(parsed.library_path, 'electronics/books')
        self.assertNotIn('#library_path', parsed.get_all_user_metadata(False))
        cache = self.init_cache()
        ids, _ = cache.add_books([(parsed, {})])
        self.assertTrue(cache.field_for('path', ids[0]).startswith('electronics/books/'))

    def folder_cache(self):
        return self.init_cache()

    def contents(self, cache, bid=1):
        return FilesystemTest.get_filesystem_data(self, cache, bid)

    def test_folder_move_and_clear(self):
        cache = self.folder_cache()
        old = cache.field_for('path', 1)
        data = self.contents(cache)
        extra_dir = os.path.join(self.library_path, old, 'data')
        os.makedirs(extra_dir, exist_ok=True)
        with open(os.path.join(extra_dir, 'notes.txt'), 'wb') as stream:
            stream.write(b'additional file')
        for folder in ('Electronics', 'Электроника/Схемотехника', ''):
            cache.set_field('library_path', {1: folder})
            self.assertEqual(cache.field_for('path', 1), (folder + '/' if folder else '') + old)
            self.assertEqual(self.contents(cache), data)
            with open(os.path.join(self.library_path, cache.field_for('path', 1), 'data', 'notes.txt'), 'rb') as stream:
                self.assertEqual(stream.read(), b'additional file')
        self.assertFalse(os.path.exists(os.path.join(self.library_path, 'Электроника')))

    def test_folder_batch_search_and_rename(self):
        cache = self.folder_cache()
        data = {bid: self.contents(cache, bid) for bid in (1, 2)}
        cache.set_field('library_path', {1: 'Electronics', 2: 'Electronics'})
        self.assertEqual(cache.search('library_path:Electronics'), {1, 2})
        self.assertEqual(cache.search('#library_path:Electronics'), {1, 2})
        item = cache.get_item_id('library_path', 'Electronics')
        cache.rename_items('library_path', {item: 'Electronics/Archive'})
        for bid in (1, 2):
            self.assertTrue(cache.field_for('path', bid).startswith('Electronics/Archive/'))
            self.assertEqual(self.contents(cache, bid), data[bid])
        item = cache.get_item_id('library_path', 'Electronics/Archive')
        cache.remove_items('library_path', {item})
        for bid in (1, 2):
            self.assertFalse(cache.field_for('path', bid).startswith('Electronics/'))

    def test_folder_create_metadata_and_author(self):
        cache = self.folder_cache()
        mi = Metadata('Issue', ['Radio'])
        mi.set('library_path', 'Electronics')
        ids, _ = cache.add_books([(mi, {'FMT1': BytesIO(b'issue content')})])
        bid = ids[0]
        self.assertTrue(cache.field_for('path', bid).startswith('Electronics/Radio/'))
        cache.set_field('authors', {bid: ['New author']})
        cache.set_field('title', {bid: 'New title'})
        self.assertTrue(cache.field_for('path', bid).startswith('Electronics/New author/New title'))
        self.assertEqual(cache.search('author:"=New author" library_path:Electronics'), {bid})
        mi = cache.get_metadata(bid)
        mi.set('library_path', 'Archive')
        cache.set_metadata(bid, mi, set_title=False, set_authors=False)
        self.assertTrue(cache.field_for('path', bid).startswith('Archive/'))
        mi.set('library_path', '')
        cache.set_metadata(bid, mi, force_changes=True, set_title=False, set_authors=False)
        self.assertTrue(cache.field_for('path', bid).startswith('New author/'))
        self.assertEqual(cache.format(bid, 'FMT1'), b'issue content')

    def test_folder_invalid_batch(self):
        cache = self.folder_cache()
        old = cache.field_for('path', 1)
        for value in ('../outside', '/absolute', 'C:/outside', 'a//b', 'a/../b', '.caltrash', 'CON', 'a (12)', 'a' * 300):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cache.set_field('library_path', {1: 'Valid', 2: value})
            self.assertFalse(cache.field_for('library_path', 1))
            self.assertEqual(cache.field_for('path', 1), old)

    def test_folder_trash_restore(self):
        cache = self.folder_cache()
        data = self.contents(cache)
        cache.set_field('library_path', {1: 'Electronics/Archive'})
        path = cache.field_for('path', 1)
        cache.remove_books({1})
        self.assertFalse(os.path.exists(os.path.join(self.library_path, 'Electronics')))
        cache.move_book_from_trash(1)
        self.assertEqual(cache.field_for('path', 1), path)
        self.assertEqual(self.contents(cache), data)

    def test_folder_shared_prefix_and_delete(self):
        from calibre.library.check_library import CHECKS, CheckLibrary

        cache = self.folder_cache()
        cache.set_field('authors', {1: ['Electronics']})
        cache.set_field('library_path', {2: 'Electronics/Archive'})
        cache.dump_metadata()
        cache.close()
        legacy = self.init_legacy()
        checker = CheckLibrary(self.library_path, legacy)
        checker.scan_library([], [])
        for key, *_ in CHECKS:
            self.assertFalse(getattr(checker, key), (key, getattr(checker, key)))
        legacy.close()
        cache = self.init_cache()
        data = self.contents(cache)
        cache.remove_books({2}, permanent=True)
        self.assertEqual(self.contents(cache), data)
        self.assertTrue(os.path.isdir(os.path.join(self.library_path, 'Electronics')))

    def test_folder_integrity_and_restore(self):
        from calibre.db.restore import Restore
        from calibre.library.check_library import CHECKS, CheckLibrary

        cache = self.folder_cache()
        cache.set_field('library_path', {1: 'Electronics/Archive', 2: 'Technical'})
        cache.dump_metadata()
        data = self.contents(cache)
        paths = {bid: cache.field_for('path', bid) for bid in (1, 2)}
        cache.close()
        legacy = self.init_legacy()
        checker = CheckLibrary(self.library_path, legacy)
        checker.scan_library([], [])
        for key, *_ in CHECKS:
            self.assertFalse(getattr(checker, key), key)
        legacy.close()
        restore = Restore(self.library_path)
        restore.run()
        self.assertIsNone(restore.tb)
        self.assertFalse(restore.errors_occurred, restore.report)
        cache = self.init_cache()
        for bid, path in paths.items():
            self.assertEqual(cache.field_for('path', bid), path)
        self.assertEqual(self.contents(cache), data)
