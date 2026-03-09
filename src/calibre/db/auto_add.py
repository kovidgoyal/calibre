#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import os
import time
from threading import Event, Thread

from calibre import prints
from calibre.db.adding import filter_filename
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils.filenames import make_long_path_useable

AUTO_ADDED = frozenset(BOOK_EXTENSIONS) - {'pdr', 'mbp', 'tan'}


class HeadlessAutoAdder:
    '''Watch a directory for new ebook files and add them to a calibre library
    without requiring any Qt/GUI dependencies.'''

    def __init__(self, watch_dir, db, callback=None, poll_interval=5,
                 add_duplicates=False, compiled_rules=(), blocked_formats=frozenset()):
        '''
        :param watch_dir: Directory to watch for new ebook files
        :param db: A calibre Cache (new API) database instance
        :param callback: Optional callable(book_id, mi) called after each book is added
        :param poll_interval: Seconds between directory scans
        :param add_duplicates: Whether to add books that already exist in the library
        :param compiled_rules: Compiled filter rules for filename matching
        :param blocked_formats: Set of lowercase format extensions to block
        '''
        self.watch_dir = os.path.abspath(watch_dir)
        self.db = db
        self.callback = callback
        self.poll_interval = poll_interval
        self.add_duplicates = add_duplicates
        self.compiled_rules = compiled_rules
        self.blocked_formats = frozenset(blocked_formats)
        self.allowed = AUTO_ADDED - self.blocked_formats
        self._stop_event = Event()
        self._worker = None
        self._staging = set()

    def is_filename_allowed(self, filename):
        allowed = filter_filename(self.compiled_rules, filename)
        if allowed is None:
            ext = os.path.splitext(filename)[1][1:].lower()
            allowed = ext in self.allowed
        return allowed

    def start(self, blocking=True):
        '''Start watching. If blocking=True, runs in the current thread.
        Otherwise starts a daemon background thread.'''
        if not os.path.isdir(self.watch_dir):
            raise ValueError(f'{self.watch_dir} is not a valid directory')
        if not os.access(self.watch_dir, os.R_OK | os.W_OK):
            raise ValueError(f'{self.watch_dir} is not readable/writable')
        self._stop_event.clear()
        if blocking:
            self._run()
        else:
            self._worker = Thread(target=self._run, daemon=True)
            self._worker.start()

    def stop(self):
        '''Signal the watcher to stop and wait for the worker thread to finish.'''
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=30)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._scan_and_add()
            except Exception:
                import traceback
                traceback.print_exc()
            self._stop_event.wait(self.poll_interval)

    def _scan_and_add(self):
        def join(*x):
            return make_long_path_useable(os.path.join(*x))

        files = []
        for entry in os.scandir(join(self.watch_dir)):
            name = entry.name
            if (name not in self._staging
                    and entry.is_file()
                    and entry.stat().st_size > 0
                    and os.access(join(self.watch_dir, name), os.R_OK | os.W_OK)
                    and self.is_filename_allowed(name)):
                files.append(name)

        if not files:
            return

        # Give any in-progress copies time to complete
        time.sleep(2)

        def safe_mtime(x):
            try:
                return os.path.getmtime(join(self.watch_dir, x))
            except OSError:
                return time.time()

        for fname in sorted(files, key=safe_mtime):
            fpath = join(self.watch_dir, fname)

            # Try opening the file for reading; if the OS prevents us,
            # the file is likely still being written to by another process.
            try:
                with open(fpath, 'rb'):
                    pass
            except OSError:
                continue

            self._staging.add(fname)
            try:
                self._add_file(fpath, fname)
            except Exception:
                import traceback
                prints(f'Failed to add {fname}:')
                traceback.print_exc()
            finally:
                try:
                    os.remove(make_long_path_useable(fpath))
                except OSError:
                    pass
                self._staging.discard(fname)

    def _add_file(self, fpath, fname):
        from calibre.ebooks.metadata.meta import get_metadata, metadata_from_filename

        fmt = os.path.splitext(fname)[1][1:].lower()
        if not fmt:
            return

        try:
            with open(fpath, 'rb') as stream:
                mi = get_metadata(stream, stream_type=fmt, use_libprs_metadata=True)
        except Exception:
            mi = metadata_from_filename(fname)

        if not mi.title:
            mi.title = os.path.splitext(fname)[0]
        if not mi.authors:
            mi.authors = [_('Unknown')]

        ids, duplicates = self.db.add_books(
            [(mi, {fmt: fpath})],
            add_duplicates=self.add_duplicates,
            run_hooks=False,
        )

        if ids:
            for book_id in ids:
                prints(f'Added: {mi.title} by {", ".join(mi.authors)} (id: {book_id})')
                if self.callback:
                    self.callback(book_id, mi)
        elif duplicates:
            prints(f'Skipped duplicate: {mi.title} by {", ".join(mi.authors)}')
