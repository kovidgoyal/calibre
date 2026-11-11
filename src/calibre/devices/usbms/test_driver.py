#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Tests for listing the books on USB mass storage devices and folders connected
as devices.
"""

import os
import shutil
import tempfile
import time
import unittest
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

from calibre.devices.folder_device.driver import FOLDER_DEVICE
from calibre.devices.kindle.driver import KINDLE2
from calibre.devices.usbms.books import Book, BookList, file_datetime
from calibre.devices.usbms.driver import USBMS, scan_files
from calibre.ebooks.metadata.book.base import Metadata

if TYPE_CHECKING:
    from collections.abc import Iterator

OLD_TIME = 1_000_000_000.0


class TempDirTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tdir = tempfile.mkdtemp(prefix='usbms-test-')
        self.addCleanup(shutil.rmtree, self.tdir, True)

    def path(self, rel: str) -> str:
        return os.path.join(self.tdir, *rel.split('/'))

    def write(self, rel: str, data: bytes = b'x') -> str:
        path = self.path(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
        return path


class TestScanFiles(TempDirTest):
    def make_tree(self) -> None:
        for rel in ('a.epub', 'dir1/b.mobi', 'dir1/dir2/c.azw3', 'dir3/d.epub', 'x.sdr/e.epub', 'dir1/y.sdr/z/f.epub'):
            self.write(rel)

    def names(self, **kw: object) -> list[str]:
        return [os.path.relpath(os.path.join(d, e.name), self.tdir).replace(os.sep, '/') for d, e in scan_files(self.tdir, **kw)]

    def test_recursive(self) -> None:
        self.make_tree()
        all_files = {'a.epub', 'dir1/b.mobi', 'dir1/dir2/c.azw3', 'dir3/d.epub', 'x.sdr/e.epub', 'dir1/y.sdr/z/f.epub'}
        for threads in (1, 4):
            self.assertEqual(set(self.names(threads=threads)), all_files, f'{threads=}')
            self.assertEqual(
                set(self.names(threads=threads, skip_dir_suffixes=('.sdr',))), {'a.epub', 'dir1/b.mobi', 'dir1/dir2/c.azw3', 'dir3/d.epub'}, f'{threads=}'
            )
            self.assertEqual(set(self.names(threads=threads, maxdepth=1)), {'a.epub', 'dir1/b.mobi', 'dir3/d.epub', 'x.sdr/e.epub'}, f'{threads=}')

    def test_non_recursive(self) -> None:
        self.make_tree()
        for threads in (1, 4):
            self.assertEqual(self.names(recursive=False, threads=threads), ['a.epub'])

    def test_order(self) -> None:
        self.make_tree()
        for i in range(20):
            self.write(f'many/dir{i}/f{i}.epub')
        # sequential scanning is top down, files before sub folders
        seq = self.names()
        self.assertEqual(seq[0], 'a.epub')
        self.assertEqual(sorted(seq), sorted(self.names(threads=8)))
        for _ in range(3):
            self.assertEqual(self.names(threads=8), self.names(threads=8))

    def test_prestat(self) -> None:
        self.make_tree()
        for threads in (1, 4):
            asked: list[str] = []
            names = {e.name for _, e in scan_files(self.tdir, threads=threads, prestat=lambda name, asked=asked: asked.append(name) is None)}
            # only used to overlap the stat() calls when using threads
            self.assertEqual(set(asked), names if threads > 1 else set(), f'{threads=}')

    def test_missing_folder(self) -> None:
        for threads in (1, 4):
            self.assertEqual(list(scan_files(self.path('nope'), threads=threads)), [])

    def test_symlinks(self) -> None:
        self.make_tree()
        try:
            os.symlink(self.path('dir1'), self.path('link'), target_is_directory=True)
            os.symlink(self.path('a.epub'), self.path('filelink.epub'))
        except OSError, NotImplementedError:
            self.skipTest('symlinks are not available')
        for threads in (1, 4):
            names = self.names(threads=threads)
            self.assertNotIn('link/b.mobi', names)
            self.assertNotIn('link', names)
            self.assertIn('filelink.epub', names)


class TestBookDate(TempDirTest):
    def test_date_from_file(self) -> None:
        path = self.write('documents/a.epub')
        os.utime(path, (OLD_TIME, OLD_TIME))
        book = Book(self.tdir, 'documents/a.epub')
        self.assertEqual(book.datetime, file_datetime(os.stat(path)))

    def test_ctime_of_zero_falls_back_to_mtime(self) -> None:
        st = SimpleNamespace(st_ctime=0, st_birthtime=0, st_mtime=OLD_TIME)
        self.assertEqual(file_datetime(st), time.gmtime(OLD_TIME))  # ty: ignore[invalid-argument-type] duck typed stat result

    def test_missing_file(self) -> None:
        before = time.gmtime(time.time() - 1)
        self.assertGreater(Book(self.tdir, 'nope.epub').datetime, before)

    def test_defer_datetime_does_not_touch_the_file(self) -> None:
        self.write('documents/a.epub')
        with patch('os.stat', side_effect=AssertionError('stat called')):
            Book(self.tdir, 'documents/a.epub', defer_datetime=True)


class BookWithoutDeferredDate(Book):
    def __init__(self, prefix: str, lpath: str, size: int | None = None, other: Metadata | None = None) -> None:
        super().__init__(prefix, lpath, size, other)


class DeviceForTest(USBMS):
    name = 'Device for test'
    FORMATS = ['epub', 'mobi']
    SUPPORTS_SUB_DIRS = True
    EBOOK_DIR_MAIN = 'documents'

    @classmethod
    def settings(cls) -> SimpleNamespace:
        return SimpleNamespace(read_metadata=False, format_map=list(cls.FORMATS), save_template='{title} - {authors}', use_subdirs=True)

    @classmethod
    def save_template(cls) -> str:
        return '{title} - {authors}'

    @classmethod
    def metadata_from_path(cls, path: str) -> Metadata:
        # the test books are not real books
        with open(path, 'rb') as f:
            return Metadata(f.read().decode())


class FlatDeviceForTest(DeviceForTest):
    SUPPORTS_SUB_DIRS = False


class DeviceWithOldUpdateMetadataItem(DeviceForTest):
    @classmethod
    def update_metadata_item(cls, book: Book) -> bool:  # ty: ignore[invalid-method-override] the signature third party drivers may have
        return super().update_metadata_item(book)


class DeviceWithOldBookClass(DeviceForTest):
    book_class = BookWithoutDeferredDate


class DeviceWithOldParseMetadataCache(DeviceForTest):
    @classmethod
    def parse_metadata_cache(cls, bl: BookList, prefix: str, name: str) -> bool:  # ty: ignore[invalid-method-override] the signature third party drivers may have
        return super().parse_metadata_cache(bl, prefix, name)


class FolderDeviceForTest(FOLDER_DEVICE):
    settings = DeviceForTest.settings
    save_template = DeviceForTest.save_template
    metadata_from_path = DeviceForTest.metadata_from_path


class TestBooks(TempDirTest):
    BOOKS = ('Auth One/Book A - Auth One.epub', 'Auth One/Book B - Auth One.mobi', 'Book C - Auth Two.epub')

    def setUp(self) -> None:
        super().setUp()
        for rel in self.BOOKS:
            self.set_book(rel, rel)
        self.write('documents/notes.dat', b'not a book')
        self.write('documents/dir.epub/inside.dat')  # a folder with a book extension

    def set_book(self, rel: str, title: str) -> None:
        path = self.write('documents/' + rel, title.encode())
        os.utime(path, (OLD_TIME, OLD_TIME))

    def device(self, cls: type[USBMS] = DeviceForTest) -> USBMS:
        if issubclass(cls, FOLDER_DEVICE):
            dev = cls(self.tdir)
            dev.EBOOK_DIR_MAIN = 'documents'
        else:
            dev = object.__new__(cls)
            dev._main_prefix = self.tdir + os.sep
            dev._card_a_prefix = dev._card_b_prefix = None
            dev.booklist_class = BookList
        dev.report_progress = lambda *a: None
        return dev

    def listing(self, cls: type[USBMS] = DeviceForTest) -> dict[str, tuple[str, int | None, time.struct_time]]:
        return {b.lpath: (b.title, b.size, b.datetime) for b in self.device(cls).books()}

    def check(self, cls: type[USBMS], books: tuple[str, ...] = BOOKS) -> None:
        def mtime_date(st: os.stat_result) -> time.struct_time:
            return time.gmtime(st.st_mtime)

        # Use the modification time as the date, as on Linux the ctime cannot be
        # set and is the current time, which is also the default date of a book
        with patch('calibre.devices.usbms.books.file_datetime', mtime_date), patch('calibre.devices.usbms.driver.file_datetime', mtime_date):
            for i in range(2):  # the second time the metadata cache is used
                self.check_listing(cls, books, i)

    def check_listing(self, cls: type[USBMS], books: tuple[str, ...], i: int) -> None:
        listing = self.listing(cls)
        self.assertEqual(set(listing), {'documents/' + rel for rel in books}, f'{cls.__name__} {i=}')
        for lpath, (title, size, dt) in listing.items():
            self.assertEqual(dt, time.gmtime(OLD_TIME), f'{cls.__name__} {i=} {lpath}')
            self.assertEqual(size, os.path.getsize(self.path(lpath)), f'{cls.__name__} {i=} {lpath}')

    def test_books_have_dates_and_sizes(self) -> None:
        for cls in (DeviceForTest, DeviceWithOldUpdateMetadataItem, DeviceWithOldBookClass, DeviceWithOldParseMetadataCache, FolderDeviceForTest):
            with self.subTest(cls=cls.__name__):
                self.check(cls)
                os.remove(self.path(cls.METADATA_CACHE))

    def test_flat_device(self) -> None:
        self.check(FlatDeviceForTest, ('Book C - Auth Two.epub',))

    def test_no_stat_of_cached_books(self) -> None:
        self.listing()
        real_stat = os.stat
        book_paths = {os.path.normcase(self.path('documents/' + rel)) for rel in self.BOOKS}

        stat_calls: list[str] = []

        def checked_stat(path: str | os.PathLike[str], *a: object, **kw: object) -> os.stat_result:
            # books() catches exceptions, so record the calls rather than raising
            if os.path.normcase(os.fspath(path)) in book_paths:
                stat_calls.append(os.fspath(path))
            return real_stat(path, *a, **kw)  # ty: ignore[invalid-argument-type] passing through the arguments

        with patch('os.stat', checked_stat):
            self.assertEqual(len(self.listing()), len(self.BOOKS))
        self.assertEqual(stat_calls, [])

    def test_changes_are_noticed(self) -> None:
        self.listing()
        self.set_book('Book C - Auth Two.epub', 'A longer new title')
        os.remove(self.path('documents/Auth One/Book B - Auth One.mobi'))
        self.set_book('Auth Three/Book D - Auth Three.epub', 'D')
        listing = self.listing()
        self.assertEqual(
            set(listing), {'documents/Auth One/Book A - Auth One.epub', 'documents/Book C - Auth Two.epub', 'documents/Auth Three/Book D - Auth Three.epub'}
        )
        self.assertEqual(listing['documents/Book C - Auth Two.epub'][:2], ('A longer new title', len(b'A longer new title')))

    def test_folder_device_uses_threads(self) -> None:
        self.assertGreater(self.device(FolderDeviceForTest).scan_threads(), 1)
        dev = self.device()
        self.assertEqual(dev.scan_threads(), 1)
        dev.connected_folder_path = self.tdir
        self.assertGreater(dev.scan_threads(), 1)
        threads_used: list[int] = []

        def recording_scan_files(*a: object, **kw: object) -> Iterator[tuple[str, os.DirEntry[str]]]:
            threads_used.append(cast('int', a[3]))
            return scan_files(*a, **kw)  # ty: ignore[invalid-argument-type] passing through the arguments

        with patch('calibre.devices.usbms.driver.scan_files', recording_scan_files):
            self.assertEqual(len(dev.books()), len(self.BOOKS))
        self.assertEqual(threads_used, [dev.FOLDER_SCAN_THREADS])

    def test_unreadable_folder_of_flat_device_is_an_error(self) -> None:
        with patch('os.scandir', side_effect=PermissionError('denied')):
            self.assertRaises(PermissionError, self.device(FlatDeviceForTest).books)
            self.assertEqual(len(self.device().books()), 0)  # the recursive scan ignores unreadable folders, as before

    def test_broken_symlink(self) -> None:
        try:
            os.symlink(self.path('nope.epub'), self.path('documents/Auth One/broken.epub'))
        except OSError, NotImplementedError:
            self.skipTest('symlinks are not available')
        self.assertEqual(len(self.listing()), len(self.BOOKS))
        self.assertEqual(len(self.listing()), len(self.BOOKS))


class TestKindle(TempDirTest):
    def test_sdr_folders_are_not_scanned(self) -> None:
        self.write('documents/a.azw3')
        self.write('documents/a.sdr/assets/metadata.kfx')
        self.write('documents/a.sdr/a.azw3')
        dev = object.__new__(KINDLE2)
        dev._main_prefix = self.tdir + os.sep
        names = [e.name for _, e in scan_files(self.path('documents'), skip_dir_suffixes=dev.SCAN_SKIP_DIR_SUFFIXES)]
        self.assertEqual(names, ['a.azw3'])

    def test_cover_thumbnail_sync(self) -> None:
        dev = object.__new__(KINDLE2)
        dev._main_prefix = self.tdir + os.sep
        src = {'same.jpg': b'1234', 'different.jpg': b'12345678', 'missing.jpg': b'abc'}
        for name, data in src.items():
            self.write('amazon-cover-bug/' + name, data)
        self.write('system/thumbnails/same.jpg', b'abcd')  # same size so not replaced
        self.write('system/thumbnails/different.jpg', b'x')
        self.write('system/thumbnails/other.jpg', b'unrelated')
        dev.sync_cover_thumbnails()

        def read(name: str) -> bytes:
            with open(self.path('system/thumbnails/' + name), 'rb') as f:
                return f.read()

        self.assertEqual(read('same.jpg'), b'abcd')
        self.assertEqual(read('different.jpg'), src['different.jpg'])
        self.assertEqual(read('missing.jpg'), src['missing.jpg'])
        self.assertEqual(read('other.jpg'), b'unrelated')


def find_tests() -> unittest.TestSuite:
    ans = unittest.TestSuite()
    for tc in (TestScanFiles, TestBookDate, TestBooks, TestKindle):
        ans.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(tc))
    return ans


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
