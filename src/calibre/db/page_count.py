#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
import weakref
from collections.abc import Iterator
from contextlib import suppress
from queue import Queue, ShutDown
from threading import Event, Thread, current_thread
from typing import TYPE_CHECKING

import apsw

from calibre.customize.ui import all_input_formats
from calibre.db.constants import Pages
from calibre.library.page_count import Server
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.config import prefs
from calibre.utils.date import utcnow

if TYPE_CHECKING:
    from calibre.db.cache import Cache
CacheRef = weakref.ref['Cache']


class MaintainPageCounts(Thread):

    def __init__(self, db_new_api: 'Cache'):
        super().__init__(name='MaintainPageCounts', daemon=True)
        self.shutdown_event = Event()
        self.tick_event = Event()
        self.count_callback = lambda fmt_file: None
        self.dbref: CacheRef = weakref.ref(db_new_api)
        self.queue: Queue[int] = Queue()
        self.tdir = ''

    def queue_scan(self, book_id: int = 0):
        self.queue.put(book_id)

    def shutdown(self) -> None:
        self.shutdown_event.set()
        self.queue.shutdown(immediate=True)
        self.dbref = lambda: None

    def wait_for_worker_shutdown(self, timeout: float | None = None) -> None:
        # Because of a python bug Queue.shutdown() does not work if
        # current_thread() is not alive (for e.g. during interpreter shutdown)
        if current_thread().is_alive() and self.is_alive():
            self.join(timeout)

    def run(self):
        self.all_input_formats = {f.upper() for f in all_input_formats()}
        self.sort_order = {fmt.upper(): i for i, fmt in enumerate(prefs['input_format_order'])}
        for i, fmt in enumerate(('PDF', 'CBZ', 'CBR', 'CB7', 'TXT', 'TEXT', 'MD', 'TEXTTILE', 'MARKDOWN', 'EPUB')):
            self.sort_order[fmt] = -1000 + i
        g = self.queue.get
        with Server() as server, TemporaryDirectory() as tdir:
            self.tdir = tdir
            while not self.shutdown_event.is_set():
                with suppress(apsw.ConnectionClosedError):
                    try:
                        book_id = g()
                    except ShutDown:
                        break
                    if book_id:
                        self.count_book_and_commit(book_id, server)
                    else:
                        self.do_backlog(server)
                    self.tick_event.set()

    def do_backlog(self, server: Server) -> None:
        while not self.shutdown_event.is_set():
            batch = tuple(self.get_batch())
            if not batch:
                break
            for book_id in batch:
                if self.shutdown_event.is_set():
                    break
                self.count_book_and_commit(book_id, server)

    def get_batch(self, size: int = 100) -> Iterator[int]:
        ' Order results by book id to prioritise newer books '
        if db := self.dbref():
            with db.safe_read_lock:
                for rec in db.backend.execute(f'SELECT book FROM books_pages_link WHERE needs_scan=1 ORDER BY book DESC LIMIT {size}'):
                    yield rec[0]

    def count_book_and_commit(self, book_id: int, server: Server) ->  Pages | None:
        if (db := self.dbref()) is None or self.shutdown_event.is_set():
            return
        try:
            pages = self.count_book(db, book_id, server)
        except Exception:
            import traceback
            traceback.print_exc()
            pages = Pages(-1, 0, '', 0, utcnow())
        if pages is not None and not self.shutdown_event.is_set():
            db.set_pages(book_id, pages.pages, pages.algorithm, pages.format, pages.format_size)
        return pages

    def sort_key(self, fmt: str) -> int:
        return self.sort_order.get(fmt, len(self.sort_order) + 100)

    def count_book(self, db: 'Cache', book_id: int, server: Server) -> Pages:
        with db.safe_read_lock:
            fmts = db._formats(book_id)
            pages = db._get_pages(book_id)
        fmts = sorted({f.upper() for f in fmts or ()} & self.all_input_formats, key=self.sort_key)
        if not fmts:
            return Pages(-1, 0, '', 0, utcnow())
        prev_scan_result = None
        if pages is not None:
            idx = -1
            with suppress(ValueError):
                idx = fmts.index(pages.format)
            if idx > -1:
                sz = -1
                with suppress(Exception):
                    sz = db.format_db_size(book_id, pages.format)
                if sz == pages.format_size and pages.algorithm == server.ALGORITHM:
                    prev_scan_result = pages
                    if idx == 0:
                        return pages

        cleanups = []
        try:
            has_drmed = False
            for fmt in fmts:
                fmt_file = os.path.join(self.tdir, 'book.' + fmt.lower())
                try:
                    db.copy_format_to(book_id, fmt, fmt_file)
                    cleanups.append(fmt_file)
                    fmt_size = os.path.getsize(fmt_file)
                except Exception:
                    import traceback
                    traceback.print_exc()
                    continue
                try:
                    self.count_callback(fmt_file)
                    pages = server.count_pages(fmt_file)
                except Exception:
                    import traceback
                    traceback.print_exc()
                else:
                    if isinstance(pages, int):
                        return Pages(pages, server.ALGORITHM, fmt, fmt_size, utcnow())
                    if 'calibre.ebooks.DRMError:' in pages[1]:
                        print(f'Failed to count pages in book: {book_id} {fmt} because it is DRM locked', file=sys.stderr)
                        has_drmed = True
                    else:
                        print(f'Failed to count pages in book: {book_id} {fmt} with error:\n{pages[1]}', file=sys.stderr)
            return prev_scan_result or Pages(-3 if has_drmed else -2, 0, '', 0, utcnow())
        finally:
            for x in cleanups:
                with suppress(OSError):
                    os.remove(x)
