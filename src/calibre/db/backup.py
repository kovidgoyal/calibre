#!/usr/bin/env python
# vim:fileencoding=UTF-8


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import weakref, traceback
from threading import Thread, Event

from calibre import prints
from calibre.ebooks.metadata.opf2 import metadata_to_opf


class Abort(Exception):
    pass


class MetadataBackup(Thread):
    '''
    Continuously backup changed metadata into OPF files
    in the book directory. This class runs in its own
    thread.
    '''

    def __init__(self, db, interval=2, scheduling_interval=0.1):
        Thread.__init__(self)
        self.daemon = True
        self._db = weakref.ref(getattr(db, 'new_api', db))
        self.stop_running = Event()
        self.interval = interval
        self.scheduling_interval = scheduling_interval
        self.check_dirtied_annotations = 0

    @property
    def db(self):
        ans = self._db()
        if ans is None:
            raise Abort()
        return ans

    def stop(self):
        self.stop_running.set()

    def wait(self, interval):
        if self.stop_running.wait(interval):
            raise Abort()

    def run(self):
        while not self.stop_running.is_set():
            try:
                self.wait(self.interval)
                self.do_one()
            except Abort:
                break

    def do_one(self):
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
        except:
            # Happens during interpreter shutdown
            return

        self.wait(0)

        try:
            mi, sequence = self.db.get_metadata_for_dump(book_id)
        except:
            prints('Failed to get backup metadata for id:', book_id, 'once')
            traceback.print_exc()
            self.wait(self.interval)
            try:
                mi, sequence = self.db.get_metadata_for_dump(book_id)
            except:
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
        except:
            prints('Failed to convert to opf for id:', book_id)
            traceback.print_exc()
            self.db.clear_dirtied(book_id, sequence)
            return

        self.wait(self.scheduling_interval)

        try:
            self.db.write_backup(book_id, raw)
        except:
            prints('Failed to write backup metadata for id:', book_id, 'once')
            traceback.print_exc()
            self.wait(self.interval)
            try:
                self.db.write_backup(book_id, raw)
            except:
                prints('Failed to write backup metadata for id:', book_id, 'again, giving up')
                traceback.print_exc()
                return

        self.db.clear_dirtied(book_id, sequence)

    def break_cycles(self):
        # Legacy compatibility
        pass
