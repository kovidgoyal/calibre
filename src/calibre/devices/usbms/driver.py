# License: GPLv3 Copyright: 2009, John Schember <john at nachtimwald.com>

"""
Generic USB Mass storage device driver. This is not a complete stand alone
driver. It is intended to be subclassed with the relevant parts implemented
for a particular device.
"""

import json
import os
import shutil
from contextlib import suppress
from functools import partial
from inspect import signature
from itertools import cycle
from typing import TYPE_CHECKING, ClassVar, Never, cast, overload

from calibre import fsync, prints
from calibre.constants import filesystem_encoding, ismacos, numeric_version
from calibre.devices.usbms.books import Book, BookList, file_datetime
from calibre.devices.usbms.cli import CLI
from calibre.devices.usbms.device import Device
from calibre.ebooks.metadata.book.json_codec import JsonCodec
from calibre.prints import debug_print
from calibre.utils.localization import _

if TYPE_CHECKING:
    import re
    from collections.abc import Callable, Iterator, Sequence

    from calibre.devices.interface import BookList as _BookList
    from calibre.devices.interface import DeviceInformation, DriveInfo
    from calibre.ebooks.metadata.book.base import Metadata


def safe_walk(
    top: str,
    topdown: bool = True,
    onerror: Callable[[OSError], object] | None = None,
    followlinks: bool = False,
    maxdepth: int = 128,
) -> Iterator[tuple[str, list[str], list[str]]]:
    "A replacement for os.walk that does not die when it encounters undecodeable filenames in a linux filesystem"
    if maxdepth < 0:
        return
    islink, join, isdir = os.path.islink, os.path.join, os.path.isdir

    # We may not have read permission for top, in which case we can't
    # get a list of the files the directory contains.  os.path.walk
    # always suppressed the exception then, rather than blow up for a
    # minor reason when (say) a thousand readable directories are still
    # left to visit.  That logic is copied here.
    try:
        names = os.listdir(top)
    except OSError as err:
        if onerror is not None:
            onerror(err)
        return

    dirs: list[str] = []
    nondirs: list[str] = []
    for name in names:
        if isinstance(name, bytes):
            try:
                name = name.decode(filesystem_encoding)
            except UnicodeDecodeError:
                debug_print(f'Skipping undecodeable file: {name!r}')
                continue
        if isdir(join(top, name)):
            dirs.append(name)
        else:
            nondirs.append(name)

    if topdown:
        yield top, dirs, nondirs
    for name in dirs:
        new_path = join(top, name)
        if followlinks or not islink(new_path):
            yield from safe_walk(new_path, topdown, onerror, followlinks, maxdepth - 1)
    if not topdown:
        yield top, dirs, nondirs


def _list_dir(
    top: str, skip_dir_suffixes: tuple[str, ...], prestat: Callable[[str], bool] | None = None, raise_errors: bool = False
) -> tuple[list[os.DirEntry[str]], list[str]]:
    """
    Return the entries for the non-directories in top and the paths of its sub
    folders. Symlinked folders and folders whose names end with one of
    skip_dir_suffixes are not returned. The stat result is fetched and cached in
    the entries of files whose names prestat() returns True for. Failure to list
    top is logged and ignored unless raise_errors is True.
    """
    files: list[os.DirEntry[str]] = []
    subdirs: list[str] = []
    try:
        with os.scandir(top) as it:
            entries = list(it)
    except OSError as err:
        if raise_errors:
            raise
        debug_print(f'USBMS: Failed to list the folder {top!r} with error: {err}')
        return files, subdirs
    for entry in entries:
        try:
            # is_dir() and is_symlink() use the file type from the directory
            # listing so they do not need a system call on most filesystems
            is_dir = entry.is_dir()
        except OSError as err:
            debug_print(f'USBMS: Failed to get the type of {entry.path!r} with error: {err}')
            is_dir = False  # treated as a file, like os.path.isdir() does
        if is_dir:
            if not entry.is_symlink() and not entry.name.endswith(skip_dir_suffixes):
                subdirs.append(entry.path)
            continue
        files.append(entry)
        if prestat is not None and prestat(entry.name):
            # entry.stat() caches its result, on failure it is retried, and the
            # error reported, by the caller
            with suppress(OSError):
                entry.stat()
    return files, subdirs


def scan_files(
    top: str,
    recursive: bool = True,
    skip_dir_suffixes: tuple[str, ...] = (),
    threads: int = 1,
    maxdepth: int = 128,
    prestat: Callable[[str], bool] | None = None,
    raise_errors: bool = False,
) -> Iterator[tuple[str, os.DirEntry[str]]]:
    """
    Yield (folder, directory entry) for every non-directory in top and, if
    recursive, its sub folders. Uses os.scandir() so that telling files and
    folders apart needs no stat() call per file, and the stat result of an entry,
    if needed, is cached in the entry (and comes free with the directory listing
    on Windows). Symlinked folders are not followed and folders whose names end
    with one of skip_dir_suffixes are not entered. Folders that cannot be listed
    are skipped, except for top if raise_errors is True.

    If threads is greater than one, several folders are listed at the same time,
    so that on high latency filesystems, such as network drives, the requests
    overlap. The stat results of the files whose names prestat() returns True for
    are then also fetched in the worker threads, as on Unix every
    os.DirEntry.stat() call is a request to the filesystem. The results are
    sorted by folder and name, otherwise they are in the same order as a top
    down os.walk().
    """
    if threads <= 1 or not recursive:
        files, subdirs = _list_dir(top, skip_dir_suffixes, raise_errors=raise_errors)
        for entry in files:
            yield top, entry
        if recursive and maxdepth > 0:
            for d in subdirs:
                yield from scan_files(d, True, skip_dir_suffixes, 1, maxdepth - 1)
        return

    from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

    found: list[tuple[str, os.DirEntry[str]]] = []
    with ThreadPoolExecutor(max_workers=threads, thread_name_prefix='USBMSScan') as executor:
        pending: dict[Future[tuple[list[os.DirEntry[str]], list[str]]], tuple[str, int]] = {
            executor.submit(_list_dir, top, skip_dir_suffixes, prestat, raise_errors): (top, maxdepth)
        }
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                d, depth = pending.pop(future)
                files, subdirs = future.result()  # only raises for top, if raise_errors is True
                found.extend((d, entry) for entry in files)
                if depth > 0:
                    for sd in subdirs:
                        pending[executor.submit(_list_dir, sd, skip_dir_suffixes, prestat)] = sd, depth - 1
    found.sort(key=lambda x: (x[0], x[1].name))
    yield from found


def accepts_keyword(func: Callable[..., object], name: str) -> bool:
    """True if func can be called with the keyword argument name"""
    try:
        params = signature(func).parameters
    except TypeError, ValueError:  # no signature available
        return False
    p = params.get(name)
    return p is not None and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)


# CLI must come before Device as it implements the CLI functions that
# are inherited from the device interface in Device.
class USBMS(CLI, Device):
    """
    The base class for all USBMS devices. Implements the logic for
    sending/getting/updating metadata/caching metadata/etc.
    """

    description = _('Communicate with an e-book reader.')
    author = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Store type instances of BookList and Book. We must do this because
    # a) we need to override these classes in some device drivers, and
    # b) the classmethods seem only to see real attributes declared in the
    #    class, not attributes stored in the class
    booklist_class = BookList
    book_class = Book

    FORMATS: ClassVar[list[str]] = []
    CAN_SET_METADATA = []
    METADATA_CACHE = 'metadata.calibre'
    DRIVEINFO = 'driveinfo.calibre'

    SCAN_FROM_ROOT = False
    #: Folders whose names end with one of these are not searched for books
    SCAN_SKIP_DIR_SUFFIXES: ClassVar[tuple[str, ...]] = ()
    #: Number of folders to list at the same time when the device is a folder,
    #: which may be on a slow network drive, see :meth:`scan_threads`
    FOLDER_SCAN_THREADS: ClassVar[int] = 8

    def scan_threads(self) -> int:
        """
        The number of threads to use to list the folders on the device. Only
        folders connected as devices use more than one, as they may be on a high
        latency network drive, whereas real devices gain nothing from it.
        """
        return self.FOLDER_SCAN_THREADS if self.connected_folder_path else 1

    def _update_driveinfo_record(self, dinfo: object, prefix: str, location_code: str, name: str | None = None) -> dict[str, object]:
        import uuid

        from calibre.utils.date import isoformat, now

        if not isinstance(dinfo, dict):
            dinfo = {}
        if dinfo.get('device_store_uuid', None) is None:
            dinfo['device_store_uuid'] = str(uuid.uuid4())
        if dinfo.get('device_name', None) is None:
            dinfo['device_name'] = self.get_gui_name()
        if name is not None:
            dinfo['device_name'] = name
        dinfo['location_code'] = location_code
        dinfo['last_library_uuid'] = getattr(self, 'current_library_uuid', None)
        dinfo['calibre_version'] = '.'.join([str(i) for i in numeric_version])
        dinfo['date_last_connected'] = isoformat(now())
        dinfo['prefix'] = prefix.replace('\\', '/')
        return dinfo

    def _update_driveinfo_file(self, prefix: str, location_code: str, name: str | None = None) -> dict[str, object]:
        from calibre.utils.config import from_json, to_json

        if os.path.exists(os.path.join(prefix, self.DRIVEINFO)):
            with open(os.path.join(prefix, self.DRIVEINFO), 'rb') as f:
                try:
                    driveinfo = json.loads(f.read(), object_hook=from_json)
                except Exception:
                    driveinfo = None
                driveinfo = self._update_driveinfo_record(driveinfo, prefix, location_code, name)
            data = json.dumps(driveinfo, default=to_json)
            if not isinstance(data, bytes):
                data = data.encode('utf-8')
            with open(os.path.join(prefix, self.DRIVEINFO), 'wb') as f:
                f.write(data)
                fsync(f)
        else:
            driveinfo = self._update_driveinfo_record({}, prefix, location_code, name)
            data = json.dumps(driveinfo, default=to_json)
            if not isinstance(data, bytes):
                data = data.encode('utf-8')
            with open(os.path.join(prefix, self.DRIVEINFO), 'wb') as f:
                f.write(data)
                fsync(f)
        return driveinfo

    def get_device_information(self, end_session: bool = True) -> DeviceInformation:
        self.report_progress(1.0, _('Get device information...'))
        self.driveinfo: DriveInfo = {}

        def raise_os_error(e: OSError) -> Never:
            raise OSError(
                _(
                    'Failed to access files in the main memory of'
                    ' your device. You should contact the device'
                    ' manufacturer for support. Common fixes are:'
                    ' try a different USB cable/USB port on your computer.'
                    ' If you device has a "Reset to factory defaults" type'
                    ' of setting somewhere, use it. Underlying error: %s'
                )
                % e
            ) from e

        if self._main_prefix is not None:
            try:
                self.driveinfo['main'] = self._update_driveinfo_file(self._main_prefix, 'main')
            except PermissionError as e:
                if ismacos:
                    raise PermissionError(
                        _(
                            'Permission was denied by macOS trying to access files in the main memory of'
                            ' your device. You will need to grant permission explicitly by looking under'
                            ' System Preferences > Security and Privacy > Privacy > Files and Folders.'
                            ' Underlying error: %s'
                        )
                        % e
                    ) from e
                raise_os_error(e)
            except OSError as e:
                raise_os_error(e)
        try:
            if self._card_a_prefix is not None:
                self.driveinfo['A'] = self._update_driveinfo_file(self._card_a_prefix, 'A')
            if self._card_b_prefix is not None:
                self.driveinfo['B'] = self._update_driveinfo_file(self._card_b_prefix, 'B')
        except OSError as e:
            raise OSError(
                _(
                    'Failed to access files on the SD card in your'
                    ' device. This can happen for many reasons. The SD card may be'
                    ' corrupted, it may be too large for your device, it may be'
                    ' write-protected, etc. Try a different SD card, or reformat'
                    ' your SD card using the FAT32 filesystem. Also make sure'
                    ' there are not too many files in the root of your SD card.'
                    ' Underlying error: %s'
                )
                % e
            )
        return (self.get_gui_name(), '', '', '', self.driveinfo)

    def set_driveinfo_name(self, location_code: str, name: str) -> None:
        prefix = {'main': self._main_prefix, 'A': self._card_a_prefix, 'B': self._card_b_prefix}.get(location_code)
        if prefix is not None:
            self._update_driveinfo_file(prefix, location_code, name)

    def formats_to_scan_for(self) -> set[str]:
        return set(self.settings().format_map) | set(self.FORMATS)

    def is_allowed_book_file(self, filename: str, path: str, prefix: str) -> bool:
        return True

    def books(self, oncard: str | None = None, end_session: bool = True) -> BookList:
        from calibre.ebooks.metadata.meta import path_to_ext

        debug_print('USBMS: Fetching list of books from device. Device=', self.__class__.__name__, 'oncard=', oncard)

        dummy_bl = self.booklist_class(None, None, None)

        if oncard == 'carda' and not self._card_a_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl
        elif oncard == 'cardb' and not self._card_b_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl
        elif oncard and oncard not in {'carda', 'cardb'}:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl

        prefix = self._card_a_prefix if oncard == 'carda' else self._card_b_prefix if oncard == 'cardb' else self._main_prefix
        assert prefix is not None

        ebook_dirs = self.get_carda_ebook_dir() if oncard == 'carda' else self.EBOOK_DIR_CARD_B if oncard == 'cardb' else self.get_main_ebook_dir()

        debug_print('USBMS: dirs are:', prefix, ebook_dirs)

        # get the metadata cache
        bl = self.booklist_class(oncard, prefix, self.settings)
        # Avoid a stat() call per book when loading the cache, the date of the
        # books is set below from the directory listing instead. The checks are
        # needed as these may be overridden with the old signatures by third
        # party drivers.
        set_datetime = self.supports_deferred_datetime() and accepts_keyword(self.parse_metadata_cache, 'defer_datetime')
        if set_datetime:
            need_sync = self.parse_metadata_cache(bl, prefix, self.METADATA_CACHE, defer_datetime=True)
        else:
            need_sync = self.parse_metadata_cache(bl, prefix, self.METADATA_CACHE)
        # Avoid a stat() call per book by passing the size from the listing
        pass_size = accepts_keyword(self.update_metadata_item, 'size')

        # make a dict cache of paths so the lookup in the loop below is faster.
        bl_cache: dict[str, int | None] = {}
        for idx, b in enumerate(bl):
            bl_cache[b.lpath] = idx

        all_formats = self.formats_to_scan_for()

        def update_booklist(filename: str, path: str, prefix: str, entry: os.DirEntry[str]) -> bool:
            changed = False
            # Ignore AppleDouble files
            if filename.startswith('._'):
                return False
            if path_to_ext(filename) in all_formats and self.is_allowed_book_file(filename, path, prefix):
                try:
                    lpath = os.path.join(path, filename).partition(self.normalize_path(prefix))[2]
                    lpath = lpath.removeprefix(os.sep)
                    lpath = lpath.replace('\\', '/')
                    idx = bl_cache.get(lpath, None)
                    if idx is not None:
                        bl_cache[lpath] = None
                        book = bl[idx]
                        try:
                            st = entry.stat()  # follows symlinks like os.stat()
                        except OSError as err:
                            debug_print(f'USBMS: Failed to stat {entry.path!r} with error: {err}')
                            st = None
                        if st is not None and set_datetime:
                            book.datetime = file_datetime(st)
                        if st is not None and pass_size:
                            changed = self.update_metadata_item(book, size=st.st_size)
                        else:
                            changed = self.update_metadata_item(book)
                    elif bl.add_book(self.book_from_path(prefix, lpath), replace_metadata=False):
                        changed = True
                except Exception:  # Probably a filename encoding error
                    import traceback

                    traceback.print_exc()
            return changed

        if isinstance(ebook_dirs, (str, bytes)):
            ebook_dirs = [ebook_dirs]
        for ebook_dir in ebook_dirs:
            ebook_dir = self.path_to_unicode(ebook_dir)
            if self.SCAN_FROM_ROOT:
                ebook_dir = self.normalize_path(prefix)
            else:
                ebook_dir = self.normalize_path(os.path.join(prefix, *(ebook_dir.split('/'))) if ebook_dir else prefix)
            debug_print('USBMS: scan from root', self.SCAN_FROM_ROOT, ebook_dir)
            if not os.path.exists(ebook_dir):
                continue
            # Get all books in the ebook_dir directory. Build a list of files to
            # check first, so we can accurately report progress.
            recursive = bool(self.SUPPORTS_SUB_DIRS or self.SUPPORTS_SUB_DIRS_FOR_SCAN)
            # A flat device whose book folder cannot be listed is an error, rather
            # than having no books, as it used to be
            found = scan_files(
                ebook_dir,
                recursive,
                self.SCAN_SKIP_DIR_SUFFIXES,
                self.scan_threads(),
                prestat=lambda name: path_to_ext(name) in all_formats,
                raise_errors=not recursive,
            )
            flist = [(self.path_to_unicode(entry.name), self.path_to_unicode(path), entry) for path, entry in found if entry.name != self.METADATA_CACHE]
            for i, (filename, path, entry) in enumerate(flist):
                self.report_progress((i + 1) / float(len(flist)), _('Getting list of books on device...'))
                if update_booklist(filename, path, prefix, entry):
                    need_sync = True

        # Remove books that are no longer in the filesystem. Cache contains
        # indices into the booklist if book not in filesystem, None otherwise
        # Do the operation in reverse order so indices remain valid
        for idx in sorted(bl_cache.values(), reverse=True, key=lambda x: -1 if x is None else x):
            if idx is not None:
                need_sync = True
                del bl[idx]

        debug_print(f'USBMS: count found in cache: {len(bl_cache)}, count of files in metadata: {len(bl)}, need_sync: {need_sync}')
        if need_sync:  # self.count_found_in_bl != len(bl) or need_sync:
            if oncard == 'cardb':
                self.sync_booklists((None, None, bl))
            elif oncard == 'carda':
                self.sync_booklists((None, bl, None))
            else:
                self.sync_booklists((bl, None, None))

        self.report_progress(1.0, _('Getting list of books on device...'))
        debug_print('USBMS: Finished fetching list of books from device. oncard=', oncard)
        return bl

    def upload_books(
        self,
        files: Sequence[str],
        names: Sequence[str],
        on_card: str | None = None,
        end_session: bool = True,
        metadata: Sequence[Metadata] | None = None,
    ) -> list[tuple[str, str | None]]:
        debug_print(f'USBMS: uploading {len(files)} books')

        path = self._sanity_check(on_card, files)

        assert metadata is not None
        paths = []
        inames = iter(names)
        imetadata = iter(metadata)

        for i, infile in enumerate(files):
            mdata, fname = next(imetadata), next(inames)
            filepath = self.normalize_path(self.create_upload_path(path, mdata, fname))
            if not hasattr(infile, 'read'):
                infile = self.normalize_path(infile)
            filepath = self.put_file(infile, filepath, replace_file=True)
            paths.append(filepath)
            try:
                self.upload_cover(os.path.dirname(filepath), os.path.splitext(os.path.basename(filepath))[0], mdata, filepath)
            except Exception:  # Failure to upload cover is not catastrophic
                import traceback

                traceback.print_exc()

            self.report_progress((i + 1) / float(len(files)), _('Transferring books to device...'))

        self.report_progress(1.0, _('Transferring books to device...'))
        debug_print(f'USBMS: finished uploading {len(files)} books')
        return list(zip(paths, cycle([on_card])))

    def upload_cover(self, path: str, filename: str, metadata: Metadata, filepath: str) -> None:
        """
        Upload book cover to the device. Default implementation does nothing.

        :param path: The full path to the folder where the associated book is located.
        :param filename: The name of the book file without the extension.
        :param metadata: metadata belonging to the book. Use metadata.thumbnail
                         for cover
        :param filepath: The full path to the e-book file

        """
        pass

    def add_books_to_metadata(self, locations: Sequence[tuple[object, ...]], metadata: Sequence[Metadata], booklists: Sequence[_BookList]) -> None:
        debug_print(f'USBMS: adding metadata for {len(metadata)} books')

        imetadata = iter(metadata)
        locations = tuple(locations)
        for i, location in enumerate(locations):
            self.report_progress((i + 1) / float(len(locations)), _('Adding books to device metadata listing...'))
            info = next(imetadata)
            blist = 2 if location[1] == 'cardb' else 1 if location[1] == 'carda' else 0

            # Extract the correct prefix from the pathname. To do this correctly,
            # we must ensure that both the prefix and the path are normalized
            # so that the comparison will work. Book's __init__ will fix up
            # lpath, so we don't need to worry about that here.
            # locations are as returned by upload_books()
            path = self.normalize_path(cast('str', location[0]))
            prefix = None
            if self._main_prefix:
                prefix = self._main_prefix if path.startswith(self.normalize_path(self._main_prefix)) else None
            if not prefix and self._card_a_prefix:
                prefix = self._card_a_prefix if path.startswith(self.normalize_path(self._card_a_prefix)) else None
            if not prefix and self._card_b_prefix:
                prefix = self._card_b_prefix if path.startswith(self.normalize_path(self._card_b_prefix)) else None
            if prefix is None:
                prints('in add_books_to_metadata. Prefix is None!', path, self._main_prefix)
                continue
            lpath = path.partition(prefix)[2]
            if lpath.startswith(('/', '\\')):
                lpath = lpath[1:]
            book = self.book_class(prefix, lpath, other=info)
            if book.size is None:
                book.size = os.stat(self.normalize_path(path)).st_size
            b = booklists[blist].add_book(book, replace_metadata=True)
            if b:
                b._new_book = True
        self.report_progress(1.0, _('Adding books to device metadata listing...'))
        debug_print('USBMS: finished adding metadata')

    def delete_single_book(self, path: str) -> None:
        os.unlink(path)

    def delete_extra_book_files(self, path: str) -> None:
        filepath = os.path.splitext(path)[0]
        for ext in self.DELETE_EXTS:
            for x in (filepath, path):
                x += ext
                if os.path.exists(x):
                    if os.path.isdir(x):
                        shutil.rmtree(x, ignore_errors=True)
                    else:
                        os.unlink(x)

        if self.SUPPORTS_SUB_DIRS:
            try:
                os.removedirs(os.path.dirname(path))
            except Exception:
                pass

    def delete_books(self, paths: Sequence[str], end_session: bool = True) -> None:
        debug_print(f'USBMS: deleting {len(paths)} books')
        for i, path in enumerate(paths):
            self.report_progress((i + 1) / float(len(paths)), _('Removing books from device...'))
            path = self.normalize_path(path)
            if os.path.exists(path):
                # Delete the ebook
                self.delete_single_book(path)
                self.delete_extra_book_files(path)

        self.report_progress(1.0, _('Removing books from device...'))
        debug_print(f'USBMS: finished deleting {len(paths)} books')

    def remove_books_from_metadata(self, paths: Sequence[str], booklists: Sequence[_BookList]) -> None:
        debug_print(f'USBMS: removing metadata for {len(paths)} books')

        for i, path in enumerate(paths):
            self.report_progress((i + 1) / float(len(paths)), _('Removing books from device metadata listing...'))
            for bl in booklists:
                for book in bl:
                    if path.endswith(book.path):
                        bl.remove_book(book)
        self.report_progress(1.0, _('Removing books from device metadata listing...'))
        debug_print(f'USBMS: finished removing metadata for {len(paths)} books')

    # If you override this method and you use book._new_book, then you must
    # complete the processing before you call this method. The flag is cleared
    # at the end just before the return
    def sync_booklists(self, booklists: Sequence[_BookList | None], end_session: bool = True) -> None:
        debug_print('USBMS: starting sync_booklists')
        json_codec = JsonCodec()

        main_prefix = self._main_prefix
        if main_prefix is None:
            raise ValueError('Cannot sync booklists as the device main memory prefix is not set')
        if not os.path.exists(self.normalize_path(main_prefix)):
            os.makedirs(self.normalize_path(main_prefix))

        def write_prefix(prefix: str | None, listid: int) -> None:
            if prefix is not None and len(booklists) > listid and isinstance(booklists[listid], self.booklist_class):
                if not os.path.exists(prefix):
                    os.makedirs(self.normalize_path(prefix))
                with open(self.normalize_path(os.path.join(prefix, self.METADATA_CACHE)), 'wb') as f:
                    json_codec.encode_to_file(f, booklists[listid])  # ty: ignore[invalid-argument-type] not None, see isinstance() check above
                    fsync(f)

        write_prefix(self._main_prefix, 0)
        write_prefix(self._card_a_prefix, 1)
        write_prefix(self._card_b_prefix, 2)

        # Clear the _new_book indication, as we are supposed to be done with
        # adding books at this point
        for blist in booklists:
            if blist is not None:
                for book in blist:
                    book._new_book = False

        self.report_progress(1.0, _('Sending metadata to device...'))
        debug_print('USBMS: finished sync_booklists')

    @classmethod
    def build_template_regexp(cls) -> re.Pattern[str]:
        from calibre.devices.utils import build_template_regexp

        return build_template_regexp(cls.save_template())

    @classmethod
    def path_to_unicode(cls, path: str | bytes) -> str:
        if isinstance(path, bytes):
            path = path.decode(filesystem_encoding)
        return path

    @overload
    @classmethod
    def normalize_path(cls, path: str) -> str: ...
    @overload
    @classmethod
    def normalize_path(cls, path: None) -> None: ...
    @classmethod
    def normalize_path(cls, path: str | None) -> str | None:
        "Return path with platform native path separators"
        if path is None:
            return None
        if os.sep == '\\':
            path = path.replace('/', '\\')
        else:
            path = path.replace('\\', '/')
        return cls.path_to_unicode(path)

    @classmethod
    def supports_deferred_datetime(cls) -> bool:
        """
        True if :attr:`book_class` can be created without looking up the date of
        the book file, see the defer_datetime argument of :class:`Book`. Book
        classes that override __init__() without that argument are created normally.
        """
        return accepts_keyword(cls.book_class, 'defer_datetime')

    @classmethod
    def parse_metadata_cache(cls, bl: BookList, prefix: str, name: str, defer_datetime: bool = False) -> bool:
        """
        :param defer_datetime: Do not look up the date of every book, which is
            slow on network drives, the caller must set it. Only use when
            :meth:`supports_deferred_datetime` returns True.
        """
        json_codec = JsonCodec()
        need_sync = False
        cache_file = cls.normalize_path(os.path.join(prefix, name))
        book_class = partial(cls.book_class, defer_datetime=True) if defer_datetime else cls.book_class
        if os.access(cache_file, os.R_OK):
            try:
                with open(cache_file, 'rb') as f:
                    json_codec.decode_from_file(f, bl, book_class, prefix)
            except Exception:
                import traceback

                traceback.print_exc()
                need_sync = True
        else:
            need_sync = True
        return need_sync

    @classmethod
    def update_metadata_item(cls, book: Book, size: int | None = None) -> bool:
        """
        Re-read the metadata of book if the size of its file changed.

        :param size: The size of the file, if already known, to avoid a stat() call.
        """
        changed = False
        if size is None:
            size = os.stat(cls.normalize_path(book.path)).st_size
        if size != book.size:
            changed = True
            mi = cls.metadata_from_path(book.path)
            book.smart_update(mi)
            book.size = size
        return changed

    @classmethod
    def metadata_from_path(cls, path: str) -> Metadata:
        return cls.metadata_from_formats([path])

    @classmethod
    def metadata_from_formats(cls, fmts: list[str]) -> Metadata:
        from calibre.customize.ui import quick_metadata
        from calibre.ebooks.metadata.meta import metadata_from_formats

        with quick_metadata:
            return metadata_from_formats(fmts, force_read_metadata=True, pattern=cls.build_template_regexp())

    @classmethod
    def book_from_path(cls, prefix: str, lpath: str) -> Book:
        from calibre.ebooks.metadata.book.base import Metadata

        if cls.settings().read_metadata or cls.MUST_READ_METADATA:
            mi = cls.metadata_from_path(cls.normalize_path(os.path.join(prefix, lpath)))
        else:
            from calibre.ebooks.metadata.meta import metadata_from_filename

            mi = metadata_from_filename(cls.normalize_path(os.path.basename(lpath)), cls.build_template_regexp())
        if mi is None:
            mi = Metadata(os.path.splitext(os.path.basename(lpath))[0], [_('Unknown')])
        size = os.stat(cls.normalize_path(os.path.join(prefix, lpath))).st_size
        book = cls.book_class(prefix, lpath, other=mi, size=size)
        return book
