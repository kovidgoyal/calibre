#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
import stat
import tempfile
import time
from threading import Event, Thread
from typing import NamedTuple

from qt.core import QApplication, QCursor, QFileSystemWatcher, QObject, Qt, QTimer, pyqtSignal

from calibre import prints
from calibre.db.adding import compile_rule, filter_filename
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import gprefs
from calibre.gui2.dialogs.duplicates import DuplicatesQuestion
from calibre.utils.filenames import make_long_path_useable
from calibre.utils.localization import _
from calibre.utils.tdir_in_cache import tdir_in_cache

AUTO_ADDED = frozenset(BOOK_EXTENSIONS) - {'pdr', 'mbp', 'tan'}
# Extensions used by browsers, download managers, torrent clients and file
# transfer tools for files that are still being downloaded
PARTIAL_DOWNLOAD_EXTENSIONS = frozenset((
    'part',
    'partial',
    'crdownload',
    'download',
    'opdownload',
    'filepart',
    'tmp',
    'temp',
    '!qb',
    '!ut',
    'aria2',
    'bc!',
    'dlpart',
))
# Formats that are ZIP files and so can be checked for completeness by
# looking for the End of Central Directory record at the end of the file
ZIP_FORMATS = frozenset((
    'epub',
    'kepub',
    'zip',
    'cbz',
    'htmlz',
    'txtz',
    'pmlz',
    'oebzip',
    'fbz',
    'odt',
    'docx',
    'docm',
    'xps',
    'oxps',
    'ibook',
    'ibooks',
    'iba',
))
# A file must be unchanged for at least this many seconds before it is added
SETTLE_TIME = 2.0
# Files that look truncated are not added until they have been unchanged
# for this many seconds, after which they are assumed to be simply corrupt
INCOMPLETE_GRACE_TIME = 300.0


def is_partial_download(name: str, names_in_dir: set[str] | frozenset[str]) -> bool:
    """Return True if name is a temporary file used while downloading or
    copying, or if it is the target of a download that is still in progress,
    as indicated by the presence of a sibling file such as name.part (Firefox
    placeholders) or name.aria2 (aria2 control files)"""
    if name.startswith(('.', '~$')):
        # Hidden files: temporary files created by rsync, gvfs, etc. and
        # macOS AppleDouble ._ files
        return True
    ext = name.rpartition('.')[-1].lower() if '.' in name else ''
    if ext in PARTIAL_DOWNLOAD_EXTENSIONS:
        return True
    return any(f'{name}.{x}' in names_in_dir for x in ('part', 'aria2', 'crdownload', 'download', '!qB', '!ut'))


def looks_complete(path: str, fmt: str) -> bool:
    """Check the end of the file for the trailer that formats such as ZIP and PDF
    are required to have. Missing trailers usually mean the file is still being
    written. Raises OSError if the file cannot be read."""
    if fmt in ZIP_FORMATS:
        from calibre.utils.zipfile import _EndRecData

        with open(path, 'rb') as f:
            return _EndRecData(f) is not None
    if fmt == 'pdf':
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 4096))
            return b'%%EOF' in f.read()
    with open(path, 'rb'):
        # Only check that the file is readable, on Windows this fails if the
        # file is open for writing by another process
        pass
    return True


class Observation(NamedTuple):
    signature: tuple[int, int]  # (size, mtime_ns)
    unchanged_since: float  # time.monotonic() value
    complete: bool | None = None  # None means not yet checked


class AllAllowed:
    def __init__(self) -> None:
        self.disallowed = frozenset(gprefs['blocked_auto_formats'])

    def __contains__(self, x) -> bool:
        return x not in self.disallowed


def allowed_formats():
    "Return an object that can be used to test if a format (lowercase) is allowed for auto-adding"
    if gprefs['auto_add_everything']:
        allowed = AllAllowed()
    else:
        allowed = AUTO_ADDED - frozenset(gprefs['blocked_auto_formats'])
    return allowed


class Worker(Thread):
    def __init__(self, path, callback) -> None:
        Thread.__init__(self)
        self.daemon = True
        self.keep_running = True
        self.wake_up = Event()
        self.path, self.callback = path, callback
        self.staging: set[str] = set()
        self.observed: dict[str, Observation] = {}
        self.next_check_at: float | None = None
        self.allowed = allowed_formats()
        self.read_rules()

    def read_rules(self) -> None:
        try:
            self.compiled_rules = tuple(map(compile_rule, gprefs.get('add_filter_rules', ())))
        except Exception:
            self.compiled_rules = ()
            import traceback

            traceback.print_exc()

    def is_filename_allowed(self, filename):
        allowed = filter_filename(self.compiled_rules, filename)
        if allowed is None:
            ext = os.path.splitext(filename)[1][1:].lower()
            allowed = ext in self.allowed
        return allowed

    def run(self) -> None:
        self.tdir = tdir_in_cache('aa')
        try:
            while self.keep_running:
                timeout = None if self.next_check_at is None else max(0, self.next_check_at - time.monotonic())
                self.wake_up.wait(timeout)
                self.wake_up.clear()
                if not self.keep_running:
                    break
                try:
                    self.auto_add()
                except Exception:
                    import traceback

                    traceback.print_exc()
        finally:
            shutil.rmtree(self.tdir, ignore_errors=True)

    def files_ready_to_add(self, now: float | None = None) -> list[tuple[str, float]]:
        """Return (name, mtime) for files that are allowed to be added and that
        appear to have been completely written. Files that are still being
        written are remembered and self.next_check_at is set so that they are
        re-checked even if no further file system notifications arrive. This is
        needed because, on Linux, writes to existing files in a watched
        directory do not trigger notifications."""
        if now is None:
            now = time.monotonic()

        def join(name: str) -> str:
            return make_long_path_useable(os.path.join(self.path, name))

        names = frozenset(os.listdir(make_long_path_useable(self.path)))
        candidates: list[tuple[str, os.stat_result]] = []
        for name in names:
            if name in self.staging or is_partial_download(name, names) or not self.is_filename_allowed(name):
                continue
            path = join(name)
            try:
                st = os.stat(path)
            except OSError:
                continue  # deleted or renamed after listdir()
            # Firefox creates 0 byte placeholder files when downloading
            if stat.S_ISREG(st.st_mode) and st.st_size > 0 and os.access(path, os.R_OK | os.W_OK):
                candidates.append((name, st))

        observed, self.observed = self.observed, {}
        ready: list[tuple[str, float]] = []
        next_check_at: float | None = None
        for name, st in candidates:
            sig = (st.st_size, st.st_mtime_ns)
            obs = observed.get(name)
            if obs is None or obs.signature != sig:
                obs = Observation(sig, now)
            check_at = obs.unchanged_since + SETTLE_TIME
            if check_at <= now:
                if obs.complete is None:
                    try:
                        obs = obs._replace(complete=looks_complete(join(name), os.path.splitext(name)[1][1:].lower()))
                    except OSError:
                        # On Windows, this means the file is open for writing in another process
                        check_at = now + SETTLE_TIME
                if obs.complete is False:
                    check_at = obs.unchanged_since + INCOMPLETE_GRACE_TIME
            self.observed[name] = obs
            if check_at > now:
                next_check_at = check_at if next_check_at is None else min(next_check_at, check_at)
            else:
                ready.append((name, st.st_mtime))
        self.next_check_at = next_check_at
        return ready

    def auto_add(self) -> None:
        from calibre.ebooks.metadata.meta import metadata_from_filename
        from calibre.ebooks.metadata.opf2 import metadata_to_opf
        from calibre.utils.ipc.simple_worker import WorkerError, fork_job

        data = []
        for fname, mtime in sorted(self.files_ready_to_add(), key=lambda x: x[1]):
            f = os.path.join(self.path, fname)
            tdir = tempfile.mkdtemp(dir=self.tdir)
            try:
                fork_job('calibre.ebooks.metadata.meta', 'forked_read_metadata', (f, tdir), no_output=True)
            except WorkerError as e:
                prints('Failed to read metadata from:', fname)
                prints(e.orig_tb)
            except Exception:
                import traceback

                traceback.print_exc()

            # Ensure that the pre-metadata file size is present. If it isn't,
            # write 0 so that the file is rescanned
            szpath = os.path.join(tdir, 'size.txt')
            try:
                with open(szpath, 'rb') as f:
                    int(f.read())
            except Exception:
                with open(szpath, 'wb') as f:
                    f.write(b'0')

            opfpath = os.path.join(tdir, 'metadata.opf')
            try:
                if os.stat(opfpath).st_size < 30:
                    raise Exception('metadata reading failed')
            except Exception:
                mi = metadata_from_filename(fname)
                with open(opfpath, 'wb') as f:
                    f.write(metadata_to_opf(mi))
            self.staging.add(fname)
            self.observed.pop(fname, None)
            data.append((fname, tdir))
        if data:
            self.callback(data)


class AutoAdder(QObject):
    metadata_read = pyqtSignal(object)
    auto_convert = pyqtSignal(object)

    def __init__(self, path, parent) -> None:
        QObject.__init__(self, parent)
        if path and os.path.isdir(path) and os.access(path, os.R_OK | os.W_OK):
            self.watcher = QFileSystemWatcher(self)
            self.worker = Worker(path, self.metadata_read.emit)
            self.watcher.directoryChanged.connect(self.dir_changed, type=Qt.ConnectionType.QueuedConnection)
            self.metadata_read.connect(self.add_to_db, type=Qt.ConnectionType.QueuedConnection)
            QTimer.singleShot(2000, self.initialize)
            self.auto_convert.connect(self.do_auto_convert, type=Qt.ConnectionType.QueuedConnection)
        elif path:
            prints(path, 'is not a valid directory to watch for new ebooks, ignoring')

    def read_rules(self) -> None:
        if hasattr(self, 'worker'):
            self.worker.read_rules()

    def initialize(self) -> None:
        try:
            if os.listdir(self.worker.path):
                self.dir_changed()
        except Exception:
            pass
        self.watcher.addPath(self.worker.path)

    def dir_changed(self, *args) -> None:
        if os.path.isdir(self.worker.path) and os.access(self.worker.path, os.R_OK | os.W_OK):
            if not self.worker.is_alive():
                self.worker.start()
            self.worker.wake_up.set()

    def stop(self) -> None:
        if hasattr(self, 'worker'):
            self.worker.keep_running = False
            self.worker.wake_up.set()

    def wait(self) -> None:
        if hasattr(self, 'worker'):
            self.worker.join()

    def __enter__(self):
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))

    def __exit__(self, *args):
        QApplication.restoreOverrideCursor()

    def add_to_db(self, data) -> None:
        with self:
            self.do_add(data)

    def do_add(self, data) -> None:
        from calibre.ebooks.metadata.opf2 import OPF
        from calibre.gui2.library.models import BooksModel
        from calibre.gui2.ui import get_gui

        gui = get_gui()
        if gui is None:
            return
        m = gui.library_view.model()
        assert isinstance(m, BooksModel)
        count = 0

        needs_rescan = False
        duplicates = []
        added_ids = set()

        for fname, tdir in data:
            path_to_remove = os.path.join(self.worker.path, fname)
            paths = [path_to_remove]
            fpath = os.path.join(tdir, 'file_changed_by_plugins')
            if os.path.exists(fpath):
                with open(fpath) as f:
                    paths[0] = f.read()
            book_fmt = os.path.splitext(os.path.basename(paths[0]))[1][1:].upper()
            sz = os.path.join(tdir, 'size.txt')
            try:
                with open(sz, 'rb') as f:
                    sz = int(f.read())
                if sz != os.stat(make_long_path_useable(paths[0])).st_size:
                    raise Exception('Looks like the file was written to after we tried to read metadata')
            except Exception:
                needs_rescan = True
                try:
                    self.worker.staging.remove(fname)
                except KeyError:
                    pass

                continue

            mi = os.path.join(tdir, 'metadata.opf')
            if not os.access(mi, os.R_OK):
                continue
            with open(mi, 'rb') as f:
                mi = OPF(f, tdir, populate_spine=False).to_book_metadata()
            if gprefs.get('tag_map_on_add_rules'):
                from calibre.ebooks.metadata.tag_mapper import map_tags

                mi.tags = map_tags(mi.tags, gprefs['tag_map_on_add_rules'])
            if gprefs.get('author_map_on_add_rules'):
                from calibre.ebooks.metadata.author_mapper import compile_rules, map_authors

                new_authors = map_authors(mi.authors, compile_rules(gprefs['author_map_on_add_rules']))
                if new_authors != mi.authors:
                    mi.authors = new_authors
                    mi.author_sort = gui.current_db.new_api.author_sort_from_authors(mi.authors)
            mi = [mi]
            dups, ids = gui.current_db.add_books(paths, [book_fmt], mi, add_duplicates=not gprefs['auto_add_check_for_duplicates'], return_ids=True)
            added_ids |= set(ids)
            num = len(ids)
            if dups:
                path = dups[0][0]
                with open(os.path.join(tdir, 'dup_cache.' + dups[1][0].lower()), 'wb') as dest, open(path, 'rb') as src:
                    shutil.copyfileobj(src, dest)
                    dups[0][0] = dest.name
                duplicates.append(dups)

            try:
                os.remove(make_long_path_useable(path_to_remove))
                self.worker.staging.remove(fname)
            except Exception:
                import traceback

                traceback.print_exc()
            count += num

        if duplicates:
            paths, formats, metadata = [], [], []
            for p, f, mi in duplicates:
                paths.extend(p)
                formats.extend(f)
                metadata.extend(mi)
            dups = [(mic, mic.cover, [p]) for mic, p in zip(metadata, paths)]
            d = DuplicatesQuestion(m.db, dups, parent=gui)
            dups = tuple(d.duplicates)
            if dups:
                paths, formats, metadata = [], [], []
                for mi, cover, book_paths in dups:
                    paths.extend(book_paths)
                    formats.extend([p.rpartition('.')[-1] for p in book_paths])
                    metadata.extend([mi for i in book_paths])
                ids = gui.current_db.add_books(paths, formats, metadata, add_duplicates=True, return_ids=True)[1]
                added_ids |= set(ids)
                num = len(ids)
                count += num

        for fname, tdir in data:
            try:
                shutil.rmtree(tdir)
            except Exception:
                pass

        if added_ids and gprefs['auto_add_auto_convert']:
            self.auto_convert.emit(added_ids)

        if count > 0:
            m.books_added(count)
            gui.status_bar.show_message(
                (_('Added a book automatically from {src}') if count == 1 else _('Added {num} books automatically from {src}')).format(
                    num=count, src=self.worker.path
                ),
                2000,
            )
            gui.refresh_cover_browser()

        if needs_rescan:
            QTimer.singleShot(2000, self.dir_changed)

    def do_auto_convert(self, added_ids) -> None:
        from calibre.gui2.ui import get_gui

        gui = get_gui()
        assert gui is not None
        gui.iactions['Convert Books'].auto_convert_auto_add(added_ids)


def find_tests():
    import unittest
    import zipfile

    class TestAutoAdd(unittest.TestCase):
        def setUp(self) -> None:
            self.tdir = tempfile.mkdtemp()
            self.worker = Worker(self.tdir, lambda data: None)
            self.worker.allowed = AUTO_ADDED
            self.worker.compiled_rules = ()

        def tearDown(self) -> None:
            shutil.rmtree(self.tdir)

        def write(self, name: str, data: bytes) -> str:
            path = os.path.join(self.tdir, name)
            with open(path, 'wb') as f:
                f.write(data)
            return path

        def write_zip(self, name: str) -> bytes:
            path = os.path.join(self.tdir, name)
            with zipfile.ZipFile(path, 'w') as zf:
                zf.writestr('mimetype', 'application/epub+zip')
                zf.writestr('content.opf', os.urandom(4096))
            with open(path, 'rb') as f:
                return f.read()

        def ready(self, now: float) -> set[str]:
            return {x[0] for x in self.worker.files_ready_to_add(now)}

        def test_partial_download_names(self) -> None:
            names = frozenset(('a.epub', 'a.epub.part', 'b.epub', 'b.epub.aria2', 'c.epub'))
            for name in ('a.epub', 'b.epub', 'x.epub.crdownload', 'x.pdf.PART', '.x.epub', '._x.epub', '~$x.docx', 'x.epub.!qB'):
                self.assertTrue(is_partial_download(name, names), name)
            for name in ('c.epub', 'x.part.epub', 'x'):
                self.assertFalse(is_partial_download(name, names), name)

        def test_looks_complete(self) -> None:
            data = self.write_zip('x.epub')
            self.assertTrue(looks_complete(os.path.join(self.tdir, 'x.epub'), 'epub'))
            self.assertFalse(looks_complete(self.write('y.epub', data[: len(data) // 2]), 'epub'))
            pdf = b'%PDF-1.4\n' + b'x' * 10000 + b'\n%%EOF\n'
            self.assertTrue(looks_complete(self.write('x.pdf', pdf), 'pdf'))
            self.assertFalse(looks_complete(self.write('y.pdf', pdf[:5000]), 'pdf'))
            self.assertTrue(looks_complete(self.write('x.txt', b'xxx'), 'txt'))

        def test_files_ready_to_add(self) -> None:
            data = self.write_zip('done.epub')
            self.write('empty.epub', b'')
            self.write('ignored.epub.part', data)
            self.write('ignored.epub', data[:100])
            self.write('growing.epub', data[:100])
            self.write('trunc.epub', data[:100])
            t = 1000.0
            self.assertEqual(self.ready(t), set())
            self.assertEqual(self.worker.next_check_at, t + SETTLE_TIME)
            self.write('growing.epub', data[:200])
            t += SETTLE_TIME
            # growing.epub changed so it must settle again, trunc.epub has no
            # zip trailer so waits for the grace period
            self.assertEqual(self.ready(t), {'done.epub'})
            self.assertEqual(self.worker.next_check_at, t + SETTLE_TIME)
            self.write('growing.epub', data)
            self.worker.staging.add('done.epub')
            t += SETTLE_TIME
            self.assertEqual(self.ready(t), set())
            t += SETTLE_TIME
            self.assertEqual(self.ready(t), {'growing.epub'})
            self.assertEqual(self.worker.next_check_at, 1000.0 + INCOMPLETE_GRACE_TIME)
            # the download completes and the placeholder is removed
            os.remove(os.path.join(self.tdir, 'ignored.epub.part'))
            self.write('ignored.epub', data)
            self.assertEqual(self.ready(t), {'growing.epub'})
            t += SETTLE_TIME
            self.assertEqual(self.ready(t), {'growing.epub', 'ignored.epub'})
            t = 1000.0 + INCOMPLETE_GRACE_TIME
            self.assertEqual(self.ready(t), {'growing.epub', 'ignored.epub', 'trunc.epub'})
            self.assertIsNone(self.worker.next_check_at)

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestAutoAdd)
