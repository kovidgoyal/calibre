#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from threading import Thread
from Queue import Empty
import os, time, sys, shutil

from calibre.utils.ipc.job import ParallelJob
from calibre.utils.ipc.server import Server
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre import prints
from calibre.constants import filesystem_encoding


def debug(*args):
    prints(*args)
    sys.stdout.flush()

def serialize_metadata_for(formats, tdir, id_):
    from calibre.ebooks.metadata.meta import metadata_from_formats
    from calibre.ebooks.metadata.opf2 import metadata_to_opf
    mi = metadata_from_formats(formats)
    mi.cover = None
    cdata = None
    if mi.cover_data:
        cdata = mi.cover_data[-1]
    mi.cover_data = None
    if not mi.application_id:
        mi.application_id = '__calibre_dummy__'
    with open(os.path.join(tdir, '%s.opf'%id_), 'wb') as f:
        f.write(metadata_to_opf(mi))
    if cdata:
        with open(os.path.join(tdir, str(id_)), 'wb') as f:
            f.write(cdata)

def read_metadata_(task, tdir, notification=lambda x,y:x):
    from calibre.customize.ui import run_plugins_on_import
    for x in task:
        try:
            id_, formats = x
        except:
            continue
        try:
            if isinstance(formats, basestring): formats = [formats]
            import_map = {}
            fmts = []
            for format in formats:
                nfp = run_plugins_on_import(format)
                if not nfp or not os.access(nfp, os.R_OK):
                    nfp = format
                nfp = os.path.abspath(nfp)
                fmts.append(nfp)

            serialize_metadata_for(fmts, tdir, id_)

            for format, nfp in zip(formats, fmts):
                if isinstance(nfp, unicode):
                    nfp.encode(filesystem_encoding)
                x = lambda j : os.path.abspath(os.path.normpath(os.path.normcase(j)))
                if x(nfp) != x(format) and os.access(nfp, os.R_OK|os.W_OK):
                    fmt = os.path.splitext(format)[1].replace('.', '').lower()
                    nfmt = os.path.splitext(nfp)[1].replace('.', '').lower()
                    dest = os.path.join(tdir, '%s.%s'%(id_, nfmt))
                    shutil.copyfile(nfp, dest)
                    import_map[fmt] = dest
                    os.remove(nfp)
            if import_map:
                with open(os.path.join(tdir, str(id_)+'.import'), 'wb') as f:
                    for fmt, nfp in import_map.items():
                        f.write(fmt+':'+nfp+'\n')
            notification(0.5, id_)
        except:
            import traceback
            with open(os.path.join(tdir, '%s.error'%id_), 'wb') as f:
                f.write(traceback.format_exc())

class Progress(object):

    def __init__(self, result_queue, tdir):
        self.result_queue = result_queue
        self.tdir = tdir

    def __call__(self, id):
        cover = os.path.join(self.tdir, str(id))
        if not os.path.exists(cover): cover = None
        res = os.path.join(self.tdir, '%s.error'%id)
        if not os.path.exists(res):
            res = res.replace('.error', '.opf')
        self.result_queue.put((id, res, cover))

class ReadMetadata(Thread):

    def __init__(self, tasks, result_queue, spare_server=None):
        self.tasks, self.result_queue = tasks, result_queue
        self.spare_server = spare_server
        self.canceled = False
        Thread.__init__(self)
        self.daemon = True
        self.failure_details = {}
        self.tdir = PersistentTemporaryDirectory('_rm_worker')


    def run(self):
        jobs, ids = set([]), set([])
        for t in self.tasks:
            for b in t:
                ids.add(b[0])
        progress = Progress(self.result_queue, self.tdir)
        server = Server() if self.spare_server is None else self.spare_server
        try:
            for i, task in enumerate(self.tasks):
                job = ParallelJob('read_metadata',
                    'Read metadata (%d of %d)'%(i, len(self.tasks)),
                    lambda x,y:x,  args=[task, self.tdir])
                jobs.add(job)
                server.add_job(job)

            while not self.canceled:
                time.sleep(0.2)
                running = False
                for job in jobs:
                    while True:
                        try:
                            id = job.notifications.get_nowait()[-1]
                            if id in ids:
                                progress(id)
                                ids.remove(id)
                        except Empty:
                            break
                    job.update(consume_notifications=False)
                    if not job.is_finished:
                        running = True

                if not running:
                    break
        finally:
            server.close()
        time.sleep(1)

        if self.canceled:
            return

        for id in ids:
            progress(id)

        for job in jobs:
            if job.failed:
                prints(job.details)
            if os.path.exists(job.log_path):
                try:
                    os.remove(job.log_path)
                except:
                    pass


def read_metadata(paths, result_queue, chunk=50, spare_server=None):
    tasks = []
    pos = 0
    while pos < len(paths):
        tasks.append(paths[pos:pos+chunk])
        pos += chunk
    t = ReadMetadata(tasks, result_queue, spare_server=spare_server)
    t.start()
    return t


###########################################################################
############ Saving #####################
###########################################################################

class SaveWorker(Thread):

    def __init__(self, result_queue, db, ids, path, opts, spare_server=None):
        Thread.__init__(self)
        self.daemon = True
        self.path, self.opts = path, opts
        self.ids = ids
        self.library_path = db.library_path
        self.canceled = False
        self.result_queue = result_queue
        self.error = None
        self.spare_server = spare_server
        self.start()

    def run(self):
        from calibre.library.save_to_disk import config
        server = Server() if self.spare_server is None else self.spare_server
        ids = set(self.ids)
        tasks = server.split(list(ids))
        jobs = set([])
        c = config()
        recs = {}
        for pref in c.preferences:
            recs[pref.name] = getattr(self.opts, pref.name)

        for i, task in enumerate(tasks):
            tids = [x[-1] for x in task]
            job = ParallelJob('save_book',
                    'Save books (%d of %d)'%(i, len(tasks)),
                    lambda x,y:x,
                    args=[tids, self.library_path, self.path, recs])
            jobs.add(job)
            server.add_job(job)


        while not self.canceled:
            time.sleep(0.2)
            running = False
            for job in jobs:
                job.update(consume_notifications=False)
                while True:
                    try:
                        id, title, ok, tb = job.notifications.get_nowait()[0]
                        if id in ids:
                            self.result_queue.put((id, title, ok, tb))
                            ids.remove(id)
                    except Empty:
                        break
                if not job.is_finished:
                    running = True

            if not running:
                break

        server.close()
        time.sleep(1)

        if self.canceled:
            return

        for job in jobs:
            if job.failed:
                prints(job.details)
                self.error = job.details
            if os.path.exists(job.log_path):
                try:
                    os.remove(job.log_path)
                except:
                    pass


def save_book(task, library_path, path, recs, notification=lambda x,y:x):
    from calibre.library.database2 import LibraryDatabase2
    db = LibraryDatabase2(library_path)
    from calibre.library.save_to_disk import config, save_to_disk
    from calibre.customize.ui import apply_null_metadata
    opts = config().parse()
    for name in recs:
        setattr(opts, name, recs[name])


    def callback(id, title, failed, tb):
        notification((id, title, not failed, tb))
        return True

    with apply_null_metadata:
        save_to_disk(db, task, path, opts, callback)

