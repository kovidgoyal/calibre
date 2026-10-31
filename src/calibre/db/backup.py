#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import sys
import traceback
import weakref
from threading import Event, Thread
from typing import TYPE_CHECKING, cast

from calibre.ebooks.metadata.opf2 import metadata_to_opf

if TYPE_CHECKING:
    from typing import TextIO, TypedDict, Unpack

    from calibre.db.cache import Cache
    from calibre.db.legacy import LibraryDatabase

    class PrintKwargs(TypedDict, total=False):
        sep: str | None
        end: str | None
        file: TextIO | None
        flush: bool


def prints(*a: object, **kw: Unpack[PrintKwargs]) -> None:
    kw['file'] = sys.stderr
    return print(*a, **kw)


class Abort(Exception):
    pass


class MetadataBackup(Thread):
    """
    Continuously backup changed metadata into OPF files
    in the book directory. This class runs in its own
    thread.
    """

    def __init__(self, db: Cache | LibraryDatabase, interval: float = 2, scheduling_interval: float = 0.1) -> None:
        super().__init__(name='MetadataBackup', daemon=True)
        self.daemon = True
        self._db: weakref.ref[Cache] = weakref.ref(cast('Cache', getattr(db, 'new_api', db)))
        self.stop_running = Event()
        self.interval = interval
        self.scheduling_interval = scheduling_interval
        self.check_dirtied_annotations = 0

    @property
    def db(self) -> Cache:
        ans = self._db()
        if ans is None:
            raise Abort()
        return ans

    def stop(self) -> None:
        self.stop_running.set()

    def wait(self, interval: float) -> None:
        if self.stop_running.wait(interval):
            raise Abort()

    def run(self) -> None:
        while not self.stop_running.is_set():
            try:
                self.wait(self.interval)
                self.do_one()
            except Abort:
                break

    def do_one(self) -> None:
        self.check_dirtied_annotations += 1
        if self.check_dirtied_annotations > 2:
            self.check_dirtied_annotations = 0
            try:
                self.db.check_dirtied_annotations()
            except Exception:
                if self.stop_running.is_set() or self.db.is_closed:
                    return
                traceback.print_exc()

        try:
            book_id = self.db.get_a_dirtied_book()
            if book_id is None:
                return
        except Abort:
            raise
        except Exception:
            # Happens during interpreter shutdown
            return

        self.wait(0)

        try:
            mi, sequence = self.db.get_metadata_for_dump(book_id)
        except Exception:
            prints('Failed to get backup metadata for id:', book_id, 'once')
            traceback.print_exc()
            self.wait(self.interval)
            try:
                mi, sequence = self.db.get_metadata_for_dump(book_id)
            except Exception:
                prints('Failed to get backup metadata for id:', book_id, 'again, giving up')
                traceback.print_exc()
                return

        if mi is None:
            self.db.clear_dirtied(book_id, sequence)
            return

        # Give the GUI thread a chance to do something. Python threads don't
        # have priorities, so this thread would naturally keep the processor
        # until some scheduling event happens. The wait makes such an event
        self.wait(self.scheduling_interval)

        try:
            raw = metadata_to_opf(mi)
        except Exception:
            prints('Failed to convert to opf for id:', book_id)
            traceback.print_exc()
            self.db.clear_dirtied(book_id, sequence)
            return

        self.wait(self.scheduling_interval)

        try:
            self.db.write_backup(book_id, raw)
        except Exception:
            prints('Failed to write backup metadata for id:', book_id, 'once')
            traceback.print_exc()
            self.wait(self.interval)
            try:
                self.db.write_backup(book_id, raw)
            except Exception:
                prints('Failed to write backup metadata for id:', book_id, 'again, giving up')
                traceback.print_exc()
                return

        self.db.clear_dirtied(book_id, sequence)

    def break_cycles(self) -> None:
        # Legacy compatibility
        pass
