#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback
from threading import Thread
from Queue import Queue, Empty
from functools import partial

from PyQt4.Qt import QObject, Qt, pyqtSignal, QTimer, QDialog, \
        QVBoxLayout, QTextBrowser, QLabel, QGroupBox, QDialogButtonBox

from calibre.ebooks.metadata.fetch import search, get_social_metadata
from calibre.gui2 import config, error_dialog
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.ebooks.metadata.covers import download_cover
from calibre.customize.ui import get_isbndb_key

class Worker(Thread):
    'Cover downloader'

    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.jobs = Queue()
        self.results = Queue()

    def run(self):
        while True:
            id, mi = self.jobs.get()
            if not getattr(mi, 'isbn', False):
                break
            try:
                cdata, errors = download_cover(mi)
                if cdata:
                    self.results.put((id, mi, True, cdata))
                else:
                    msg = []
                    for e in errors:
                        if not e[0]:
                            msg.append(e[-1] + ' - ' + e[1])
                    self.results.put((id, mi, False, '\n'.join(msg)))
            except:
                self.results.put((id, mi, False, traceback.format_exc()))

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.jobs.put((False, False))


class DownloadMetadata(Thread):
    'Metadata downloader'

    def __init__(self, db, ids, get_covers, set_metadata=True,
            get_social_metadata=True):
        Thread.__init__(self)
        self.daemon = True
        self.metadata = {}
        self.covers   = {}
        self.set_metadata = set_metadata
        self.get_social_metadata = get_social_metadata
        self.social_metadata_exceptions = []
        self.db = db
        self.updated = set([])
        self.get_covers = get_covers
        self.worker = Worker()
        self.results = Queue()
        self.keep_going = True
        for id in ids:
            self.metadata[id] = db.get_metadata(id, index_is_id=True)
            self.metadata[id].rating = None
        self.total = len(ids)
        if self.get_covers:
            self.total += len(ids)
        self.fetched_metadata = {}
        self.fetched_covers = {}
        self.failures = {}
        self.cover_failures = {}
        self.exception = self.tb = None

    def run(self):
        try:
            self._run()
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

    def _run(self):
        self.key = get_isbndb_key()
        if not self.key:
            self.key = None
        with self.worker:
            for id, mi in self.metadata.items():
                if not self.keep_going:
                    break
                args = {}
                if mi.isbn:
                    args['isbn'] = mi.isbn
                else:
                    if mi.is_null('title'):
                        self.failures[id] = \
                                _('Book has neither title nor ISBN')
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
                    if self.get_covers:
                        if fmi.isbn:
                            self.worker.jobs.put((id, fmi))
                        else:
                            self.results.put((id, 'cover', False, mi.title))
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
                    self.results.put((id, 'metadata', True, mi.title))
                else:
                    self.failures[id] = _('No matches found for this book')
                    self.results.put((id, 'metadata', False, mi.title))
                    self.results.put((id, 'cover', False, mi.title))
                self.commit_covers()

        self.commit_covers(True)

    def commit_covers(self, all=False):
        if all:
            self.worker.jobs.put((False, False))
        while True:
            try:
                id, fmi, ok, cdata = self.worker.results.get_nowait()
                if ok:
                    self.fetched_covers[id] = cdata
                    self.results.put((id, 'cover', ok, fmi.title))
                else:
                    self.results.put((id, 'cover', ok, fmi.title))
                    try:
                        self.cover_failures[id] = unicode(cdata)
                    except:
                        self.cover_failures[id] = repr(cdata)
            except Empty:
                if not all or not self.worker.is_alive():
                    return

class DoDownload(QObject):

    idle_process = pyqtSignal()

    def __init__(self, parent, title, db, ids, get_covers, set_metadata=True,
            get_social_metadata=True):
        QObject.__init__(self, parent)
        self.pd = ProgressDialog(title, min=0, max=0, parent=parent)
        self.pd.canceled_signal.connect(self.cancel)
        self.idle_process.connect(self.do_one, type=Qt.QueuedConnection)
        self.downloader = None
        self.create = partial(DownloadMetadata, db, ids, get_covers,
                set_metadata=set_metadata,
                get_social_metadata=get_social_metadata)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.do_one, type=Qt.QueuedConnection)
        self.db = db
        self.updated = set([])
        self.total = len(ids)

    def exec_(self):
        self.timer.start(50)
        ret = self.pd.exec_()
        if getattr(self.downloader, 'exception', None) is not None and \
                ret == self.pd.Accepted:
            error_dialog(self.parent(), _('Failed'),
                    _('Failed to download metadata'), show=True)
        else:
            self.show_report()
        return ret

    def cancel(self, *args):
        self.timer.stop()
        self.downloader.keep_going = False
        self.pd.reject()

    def do_one(self):
        if self.downloader is None:
            self.downloader = self.create()
            self.downloader.start()
            self.pd.set_min(0)
            self.pd.set_max(self.downloader.total)
        try:
            r = self.downloader.results.get_nowait()
            self.handle_result(r)
        except Empty:
            pass
        if not self.downloader.is_alive():
            self.timer.stop()
            while True:
                try:
                    r = self.downloader.results.get_nowait()
                    self.handle_result(r)
                except Empty:
                    break
            self.pd.accept()

    def handle_result(self, r):
        id_, typ, ok, title = r
        what = _('cover') if typ == 'cover' else _('metadata')
        which = _('Downloaded') if ok else _('Failed to get')
        self.pd.set_msg(_('%s %s for: %s') % (which, what, title))
        self.pd.value += 1
        if ok:
            self.updated.add(id_)
            if typ == 'cover':
                try:
                    self.db.set_cover(id_,
                            self.downloader.fetched_covers.pop(id_))
                except:
                    self.downloader.cover_failures[id_] = \
                            traceback.format_exc()
            else:
                try:
                    self.set_metadata(id_)
                except:
                    self.downloader.failures[id_] = \
                            traceback.format_exc()

    def set_metadata(self, id_):
        mi = self.downloader.metadata[id_]
        if self.downloader.set_metadata:
            self.db.set_metadata(id_, mi)
        if not self.downloader.set_metadata and self.downloader.get_social_metadata:
            if mi.rating:
                self.db.set_rating(id_, mi.rating)
            if mi.tags:
                self.db.set_tags(id_, mi.tags)
            if mi.comments:
                self.db.set_comment(id_, mi.comments)
            if mi.series:
                self.db.set_series(id_, mi.series)
                if mi.series_index is not None:
                    self.db.set_series_index(id_, mi.series_index)

    def show_report(self):
        f, cf = self.downloader.failures, self.downloader.cover_failures
        report = []
        if f:
            report.append(
                '<h3>Failed to download metadata for the following:</h3><ol>')
            for id_, err in f.items():
                mi = self.downloader.metadata[id_]
                report.append('<li><b>%s</b><pre>%s</pre></li>' % (mi.title,
                    unicode(err)))
            report.append('</ol>')
        if cf:
            report.append(
                '<h3>Failed to download cover for the following:</h3><ol>')
            for id_, err in cf.items():
                mi = self.downloader.metadata[id_]
                report.append('<li><b>%s</b><pre>%s</pre></li>' % (mi.title,
                    unicode(err)))
            report.append('</ol>')

        if len(self.updated) != self.total or report:
            d = QDialog(self.parent())
            bb = QDialogButtonBox(QDialogButtonBox.Ok, parent=d)
            v1 = QVBoxLayout()
            d.setLayout(v1)
            d.setWindowTitle(_('Done'))
            v1.addWidget(QLabel(_('Successfully downloaded metadata for %d out of %d books') %
                (len(self.updated), self.total)))
            gb = QGroupBox(_('Details'), self.parent())
            v2 = QVBoxLayout()
            gb.setLayout(v2)
            b = QTextBrowser(self.parent())
            v2.addWidget(b)
            b.setHtml('\n'.join(report))
            v1.addWidget(gb)
            v1.addWidget(bb)
            bb.accepted.connect(d.accept)
            d.resize(800, 600)
            d.exec_()




