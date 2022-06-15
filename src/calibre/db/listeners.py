#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

import weakref
from contextlib import suppress
from queue import Queue
from threading import Thread
from enum import Enum, auto


class EventType(Enum):
    #: When some metadata is changed for some books, with
    #: arguments: (name of changed field, set of affected book ids)
    metadata_changed = auto()

    #: When a format is added to a book, with arguments:
    #: (book_id, format)
    format_added = auto()

    #: When formats are removed from a book, with arguments:
    #: (mapping of book id to set of formats removed from the book)
    formats_removed = auto()

    #: When a new book record is created in the database, with the
    #: book id as the only argument
    book_created = auto()

    #: When books are removed from the database with the list of book
    #: ids as the only argument
    books_removed = auto()

    #: When items such as tags or authors are renamed in some or all books.
    #: Arguments: (field_name, affected book ids, map of old item id to new item id)
    items_renamed = auto()

    #: When items such as tags or authors are removed from some books.
    #: Arguments: (field_name, affected book ids, ids of removed items)
    items_removed = auto()

    #: When a book format is edited, with arguments: (book_id, fmt)
    book_edited = auto()

    #: When the indexing progress changes
    indexing_progress_changed = auto()


class EventDispatcher(Thread):

    def __init__(self):
        Thread.__init__(self, name='DBListener', daemon=True)
        self.refs = []
        self.queue = Queue()
        self.activated = False
        self.library_id = ''

    def add_listener(self, callback):
        # note that we intentionally leak dead weakrefs. To not do so would
        # require using a lock to serialize access to self.refs. Given that
        # currently the use case for listeners is register one and leave it
        # forever, this is a worthwhile tradeoff
        self.remove_listener(callback)
        ref = weakref.ref(callback)
        self.refs.append(ref)
        if not self.activated:
            self.activated = True
            self.start()

    def remove_listener(self, callback):
        ref = weakref.ref(callback)
        with suppress(ValueError):
            self.refs.remove(ref)

    def __call__(self, event_name, *args):
        if self.activated:
            self.queue.put((event_name, self.library_id, args))

    def close(self):
        if self.activated:
            self.queue.put(None)
            self.join()
            self.refs = []

    def run(self):
        while True:
            val = self.queue.get()
            if val is None:
                break
            for ref in self.refs:
                listener = ref()
                if listener is not None:
                    listener(*val)
