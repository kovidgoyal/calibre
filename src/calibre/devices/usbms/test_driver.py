#!/usr/bin/env python
# License: GPLv3

"""
Tests for the parts of the USBMS driver that are used for slow devices, such as
a Kindle mounted over sshfs: listing files without a stat() call for each one,
and the local copy of the device metadata cache.
"""

import os
import shutil
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from calibre.devices.kindle.driver import KINDLE2
from calibre.devices.usbms.books import Book, BookList
from calibre.devices.usbms.driver import USBMS, scan_files
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.json_codec import JsonCodec


class TempDirTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tdir = tempfile.mkdtemp(prefix='usbms-test-')
        self.addCleanup(shutil.rmtree, self.tdir, True)

    def write(self, rel: str, data: bytes = b'x') -> str:
        path = os.path.join(self.tdir, *rel.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
        return path


class TestScanFiles(TempDirTest):
    def make_tree(self) -> set[tuple[str, str]]:
        files = {'a.epub': b'1', 'dir1/b.mobi': b'22', 'dir1/dir2/c.azw3': b'333', 'dir3/d.epub': b'4444'}
        for rel, data in files.items():
            self.write(rel, data)
        return {(os.path.dirname(os.path.join(self.tdir, *rel.split('/'))), os.path.basename(rel)) for rel in files}

    def found(self, threads: int = 1, skip_dir_suffixes: tuple[str, ...] = ()) -> list[tuple[str, str, os.stat_result | None]]:
        return list(scan_files(self.tdir, skip_dir_suffixes, threads))

    def test_finds_all_files_with_sizes(self) -> None:
        expected = self.make_tree()
        for threads in (1, 4):
            found = self.found(threads=threads)
            self.assertEqual({(d, n) for d, n, _ in found}, expected, f'threads={threads}')
            for d, n, st in found:
                self.assertEqual(st.st_size, os.path.getsize(os.path.join(d, n)))

    def test_threads_give_the_same_result_in_a_fixed_order(self) -> None:
        self.make_tree()
        for i in range(30):
            self.write(f'many/dir{i}/f{i}.epub')
        sequential = sorted((d, n) for d, n, _ in self.found(threads=1))
        for _ in range(3):
            threaded = [(d, n) for d, n, _ in self.found(threads=8)]
            self.assertEqual(threaded, sequential)

    def test_skip_dir_suffixes(self) -> None:
        self.make_tree()
        self.write('book.sdr/book.apnx')
        self.write('dir1/other.sdr/deeper/x.epub')
        for threads in (1, 4):
            names = {n for _, n, _ in self.found(threads=threads, skip_dir_suffixes=('.sdr',))}
            self.assertNotIn('book.apnx', names)
            self.assertNotIn('x.epub', names)
            self.assertIn('b.mobi', names)
            names = {n for _, n, _ in self.found(threads=threads)}
            self.assertIn('book.apnx', names)
            self.assertIn('x.epub', names)

    def test_missing_folder(self) -> None:
        for threads in (1, 4):
            self.assertEqual(list(scan_files(os.path.join(self.tdir, 'nope'), threads=threads)), [])

    def test_symlinked_folders_are_not_followed(self) -> None:
        self.make_tree()
        try:
            os.symlink(os.path.join(self.tdir, 'dir1'), os.path.join(self.tdir, 'link'), target_is_directory=True)
        except OSError, NotImplementedError:
            self.skipTest('symlinks are not available')
        for threads in (1, 4):
            files = [(d, n) for d, n, _ in self.found(threads=threads)]
            self.assertEqual(len(files), len(set(files)))
            self.assertFalse([1 for d, _n in files if os.path.basename(d) == 'link' or os.sep + 'link' + os.sep in d])


class TestLocalMetadataCache(TempDirTest):
    def setUp(self) -> None:
        super().setUp()
        self.device = self.write('device/x').rpartition(os.sep)[0] + os.sep
        self.cache = os.path.join(self.tdir, 'cache')
        patcher = patch('calibre.devices.usbms.driver.cache_dir', lambda: self.cache)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_cache(self, titles: list[str]) -> None:
        bl = BookList(None, self.device, None)
        for t in titles:
            book = Book(self.device, f'documents/{t}.epub', size=1, defer_datetime=True)
            book.title = t
            bl.append(book)
        with open(os.path.join(self.device, 'metadata.calibre'), 'wb') as f:
            JsonCodec().encode_to_file(f, bl)

    def titles(self, use_local_copy: bool) -> list[str]:
        bl = BookList(None, self.device, None)
        USBMS.parse_metadata_cache(bl, self.device, 'metadata.calibre', use_local_copy=use_local_copy)
        return sorted(b.title for b in bl)

    def local_copy_path(self) -> str:
        return USBMS._local_metadata_cache_paths(self.device, 'metadata.calibre')[0]

    def test_local_copy_is_used_until_the_device_file_changes(self) -> None:
        self.write_cache(['one', 'two'])
        self.assertEqual(self.titles(True), ['one', 'two'])
        local = self.local_copy_path()
        self.assertTrue(os.path.exists(local))
        # Prove the local copy is what gets read: change it without changing its size
        with open(local, 'rb') as f:
            data = f.read()
        self.assertIn(b'"one"', data)
        with open(local, 'wb') as f:
            f.write(data.replace(b'"one"', b'"uno"'))
        self.assertEqual(self.titles(True), ['two', 'uno'])
        # Without the option the device file is read
        self.assertEqual(self.titles(False), ['one', 'two'])
        # A different size device file is read again and the local copy replaced
        self.write_cache(['one', 'two', 'three'])
        self.assertEqual(self.titles(True), ['one', 'three', 'two'])
        self.assertEqual(self.titles(True), ['one', 'three', 'two'])

    def test_corrupt_or_wrong_size_local_copy_is_ignored(self) -> None:
        self.write_cache(['one', 'two'])
        self.assertEqual(self.titles(True), ['one', 'two'])
        with open(self.local_copy_path(), 'wb') as f:
            f.write(b'[]')
        self.assertEqual(self.titles(True), ['one', 'two'])

    def test_missing_cache_file_needs_a_sync(self) -> None:
        bl = BookList(None, self.device, None)
        self.assertTrue(USBMS.parse_metadata_cache(bl, self.device, 'metadata.calibre', use_local_copy=True))
        self.assertEqual(len(bl), 0)

    def test_failure_to_save_the_local_copy_is_not_fatal(self) -> None:
        self.write_cache(['one'])
        with open(self.cache, 'w') as f:  # a file where the folder should be
            f.write('x')
        with patch('traceback.print_exc'):
            self.assertEqual(self.titles(True), ['one'])

    def test_books_have_their_date_set_after_loading_from_the_cache(self) -> None:
        self.write_cache(['one'])
        bl = BookList(None, self.device, None)
        USBMS.parse_metadata_cache(bl, self.device, 'metadata.calibre', use_local_copy=True)
        self.assertTrue(bl[0].datetime_deferred)
        bl = BookList(None, self.device, None)
        USBMS.parse_metadata_cache(bl, self.device, 'metadata.calibre')
        self.assertFalse(getattr(bl[0], 'datetime_deferred', False))


class TestBookDate(TempDirTest):
    def test_defer_datetime_does_not_touch_the_file(self) -> None:
        with patch('os.path.getctime', side_effect=AssertionError('getctime called')):
            Book(self.tdir, 'documents/a.epub', defer_datetime=True)

    def test_creation_time_of_zero_falls_back_to_the_modification_time(self) -> None:
        path = self.write('documents/a.epub')
        mtime = os.path.getmtime(path)
        with patch('os.path.getctime', return_value=0):
            book = Book(self.tdir, 'documents/a.epub')
        self.assertEqual(book.datetime, time.gmtime(mtime))


class DeviceForTest(USBMS):
    """A USBMS device that is a folder, with the settings the driver needs"""

    name = 'Device for test'
    FORMATS = ['epub', 'mobi']
    SUPPORTS_SUB_DIRS = True
    EBOOK_DIR_MAIN = 'documents'
    SCAN_SKIP_DIR_SUFFIXES = ('.sdr',)

    @classmethod
    def settings(cls) -> SimpleNamespace:
        return SimpleNamespace(read_metadata=False, format_map=list(cls.FORMATS), save_template='{title} - {authors}', use_subdirs=True)

    @classmethod
    def save_template(cls) -> str:
        return '{title} - {authors}'

    @classmethod
    def metadata_from_path(cls, path: str) -> Metadata:
        # the test books are not real books
        return Metadata(os.path.splitext(os.path.basename(path))[0])


class TestBooksOnSlowDevice(TempDirTest):
    def setUp(self) -> None:
        super().setUp()
        self.device_dir = os.path.join(self.tdir, 'device')
        self.cache = os.path.join(self.tdir, 'cache')
        patcher = patch('calibre.devices.usbms.driver.cache_dir', lambda: self.cache)
        patcher.start()
        self.addCleanup(patcher.stop)
        for rel in ('Auth One/Book A - Auth One.epub', 'Auth One/Book B - Auth One.mobi', 'Auth Two/Book C - Auth Two.epub'):
            self.write('device/documents/' + rel, rel.encode())
        self.write('device/documents/Auth One/Book A - Auth One.sdr/Book A - Auth One.apnx', b'sidecar')
        self.write('device/documents/notes.txt', b'not a book')

    def device(self, slow: bool) -> DeviceForTest:
        dev = object.__new__(DeviceForTest)
        dev._main_prefix = self.device_dir + os.sep
        dev._card_a_prefix = dev._card_b_prefix = None
        dev.slow_connection = slow
        dev.report_progress = lambda *a: None
        dev.booklist_class = BookList
        return dev

    def listing(self, slow: bool) -> dict[str, tuple[int | None, time.struct_time]]:
        bl = self.device(slow).books()
        return {b.lpath: (b.size, b.datetime) for b in bl}

    def test_slow_and_normal_modes_find_the_same_books(self) -> None:
        normal = self.listing(False)
        self.assertEqual(
            set(normal), {'documents/Auth One/Book A - Auth One.epub', 'documents/Auth One/Book B - Auth One.mobi', 'documents/Auth Two/Book C - Auth Two.epub'}
        )
        for _ in range(2):  # the second time the local copy of the metadata cache is used
            self.assertEqual(self.listing(True), normal)

    def test_changed_book_is_noticed_in_slow_mode(self) -> None:
        self.listing(True)
        self.write('device/documents/Auth Two/Book C - Auth Two.epub', b'now it is longer')
        sizes = {lpath: size for lpath, (size, _) in self.listing(True).items()}
        self.assertEqual(sizes['documents/Auth Two/Book C - Auth Two.epub'], len(b'now it is longer'))

    def test_new_and_removed_books_in_slow_mode(self) -> None:
        self.assertEqual(len(self.listing(True)), 3)
        os.remove(os.path.join(self.device_dir, 'documents', 'Auth Two', 'Book C - Auth Two.epub'))
        self.write('device/documents/Auth Three/Book D - Auth Three.epub')
        found = set(self.listing(True))
        self.assertNotIn('documents/Auth Two/Book C - Auth Two.epub', found)
        self.assertIn('documents/Auth Three/Book D - Auth Three.epub', found)
        self.assertEqual(found, set(self.listing(False)))


class TestKindleCoverSync(TempDirTest):
    def test_only_missing_or_different_size_thumbnails_are_restored(self) -> None:
        dev = object.__new__(KINDLE2)
        dev._main_prefix = self.tdir + os.sep
        src = {'same.jpg': b'1234', 'different.jpg': b'12345678', 'missing.jpg': b'abc'}
        for name, data in src.items():
            self.write('amazon-cover-bug/' + name, data)
        self.write('system/thumbnails/same.jpg', b'abcd')  # same size is not touched
        self.write('system/thumbnails/different.jpg', b'x')
        self.write('system/thumbnails/other.jpg', b'unrelated')
        dev.sync_cover_thumbnails()
        dest = os.path.join(self.tdir, 'system', 'thumbnails')

        def read(name: str) -> bytes:
            with open(os.path.join(dest, name), 'rb') as f:
                return f.read()

        self.assertEqual(read('same.jpg'), b'abcd')
        self.assertEqual(read('different.jpg'), src['different.jpg'])
        self.assertEqual(read('missing.jpg'), src['missing.jpg'])
        self.assertEqual(read('other.jpg'), b'unrelated')

    def test_no_thumbnails_folder(self) -> None:
        dev = object.__new__(KINDLE2)
        dev._main_prefix = self.tdir + os.sep
        self.write('amazon-cover-bug/a.jpg')
        dev.sync_cover_thumbnails()  # nothing to do and no error
        self.assertFalse(os.path.exists(os.path.join(self.tdir, 'system')))


def find_tests() -> unittest.TestSuite:
    ans = unittest.TestSuite()
    for tc in (TestScanFiles, TestLocalMetadataCache, TestBookDate, TestBooksOnSlowDevice, TestKindleCoverSync):
        ans.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(tc))
    return ans


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
