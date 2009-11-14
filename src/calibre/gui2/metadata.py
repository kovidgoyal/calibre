#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback
from threading import Thread
from Queue import Queue, Empty


from calibre.ebooks.metadata.fetch import search, get_social_metadata
from calibre.ebooks.metadata.library_thing import cover_from_isbn
from calibre.customize.ui import get_isbndb_key

class Worker(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.setDaemon(True)
        self.jobs = Queue()
        self.results = Queue()

    def run(self):
        while True:
            isbn = self.jobs.get()
            if not isbn:
                break
            try:
                cdata, _ = cover_from_isbn(isbn)
                if cdata:
                    self.results.put((isbn, cdata))
            except:
                traceback.print_exc()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.jobs.put(False)


class DownloadMetadata(Thread):

    def __init__(self, db, ids, get_covers, set_metadata=True,
            get_social_metadata=True):
        Thread.__init__(self)
        self.setDaemon(True)
        self.metadata = {}
        self.covers   = {}
        self.set_metadata = set_metadata
        self.get_social_metadata = get_social_metadata
        self.social_metadata_exceptions = []
        self.db = db
        self.updated = set([])
        self.get_covers = get_covers
        self.worker = Worker()
        for id in ids:
            self.metadata[id] = db.get_metadata(id, index_is_id=True)

    def run(self):
        self.exception = self.tb = None
        try:
            self._run()
        except Exception, e:
            self.exception = e
            import traceback
            self.tb = traceback.format_exc()

    def _run(self):
        self.key = get_isbndb_key()
        if not self.key:
            self.key = None
        self.fetched_metadata = {}
        self.failures = {}
        with self.worker:
            for id, mi in self.metadata.items():
                args = {}
                if mi.isbn:
                    args['isbn'] = mi.isbn
                else:
                    if not mi.title:
                        self.failures[id] = \
                                (str(id), _('Book has neither title nor ISBN'))
                        continue
                    args['title'] = mi.title
                    if mi.authors:
                        args['author'] = mi.authors[0]
                if self.key:
                    args['isbndb_key'] = self.key
                results, exceptions = search(**args)
                if results:
                    fmi = results[0]
                    self.fetched_metadata[id] = fmi
                    if fmi.isbn and self.get_covers:
                        self.worker.jobs.put(fmi.isbn)
                    mi.smart_update(fmi)
                    if mi.isbn and self.get_social_metadata:
                        self.social_metadata_exceptions = get_social_metadata(mi)
                    if not self.get_social_metadata:
                        mi.tags = []
                else:
                    self.failures[id] = (mi.title,
                        _('No matches found for this book'))
                self.commit_covers()

        self.commit_covers(True)
        if self.set_metadata:
            for id in self.fetched_metadata:
                self.db.set_metadata(id, self.metadata[id])
        self.updated = set(self.fetched_metadata)


    def commit_covers(self, all=False):
        if all:
            self.worker.jobs.put(False)
        while True:
            try:
                isbn, cdata = self.worker.results.get(False)
                for id, mi in self.metadata.items():
                    if mi.isbn == isbn:
                        self.db.set_cover(id, cdata)
            except Empty:
                if not all or not self.worker.is_alive():
                    return


