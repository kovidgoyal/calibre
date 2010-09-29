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
from calibre.gui2 import config
from calibre.ebooks.metadata.covers import download_cover
from calibre.customize.ui import get_isbndb_key
from calibre import prints
from calibre.constants import DEBUG

class Worker(Thread):
    'Cover downloader'

    def __init__(self):
        Thread.__init__(self)
        self.setDaemon(True)
        self.jobs = Queue()
        self.results = Queue()

    def run(self):
        while True:
            mi = self.jobs.get()
            if not getattr(mi, 'isbn', False):
                break
            try:
                cdata, errors = download_cover(mi)
                if cdata:
                    self.results.put((mi.isbn, cdata))
                elif DEBUG:
                    prints('Cover download failed:', errors)
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
            self.metadata[id].rating = None

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
                    if mi.is_null('title'):
                        self.failures[id] = \
                                (str(id), _('Book has neither title nor ISBN'))
                        continue
                    args['title'] = mi.title
                    if mi.authors and mi.authors[0] != _('Unknown'):
                        args['author'] = mi.authors[0]
                if self.key:
                    args['isbndb_key'] = self.key
                results, exceptions = search(**args)
                if results:
                    fmi = results[0]
                    self.fetched_metadata[id] = fmi
                    if fmi.isbn and self.get_covers:
                        self.worker.jobs.put(fmi)
                    if (not config['overwrite_author_title_metadata']):
                        fmi.authors = mi.authors
                        fmi.author_sort = mi.author_sort
                        fmi.title = mi.title
                    mi.smart_update(fmi)
                    if mi.isbn and self.get_social_metadata:
                        self.social_metadata_exceptions = get_social_metadata(mi)
                        if mi.rating:
                            mi.rating *= 2
                    if not self.get_social_metadata:
                        mi.tags = []
                else:
                    self.failures[id] = (mi.title,
                        _('No matches found for this book'))
                self.commit_covers()

        self.commit_covers(True)
        for id in self.fetched_metadata:
            mi = self.metadata[id]
            if self.set_metadata:
                self.db.set_metadata(id, mi)
            if not self.set_metadata and self.get_social_metadata:
                if mi.rating:
                    self.db.set_rating(id, mi.rating)
                if mi.tags:
                    self.db.set_tags(id, mi.tags)
                if mi.comments:
                    self.db.set_comment(id, mi.comments)
                if mi.series:
                    self.db.set_series(id, mi.series)
                    if mi.series_index is not None:
                        self.db.set_series_index(id, mi.series_index)

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


