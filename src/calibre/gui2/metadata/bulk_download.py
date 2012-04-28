#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time, shutil
from functools import partial
from threading import Thread

from PyQt4.Qt import (QIcon, QDialog,
        QDialogButtonBox, QLabel, QGridLayout, QPixmap, Qt)

from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.utils.ipc.simple_worker import fork_job, WorkerError
from calibre.ptempfile import (PersistentTemporaryDirectory,
        PersistentTemporaryFile)

# Start download {{{

class Job(ThreadedJob):

    ignore_html_details = True

    def consolidate_log(self):
        self.consolidated_log = self.log.plain_text
        self.log = None

    def read_consolidated_log(self):
        return self.consolidated_log

    @property
    def details(self):
        if self.consolidated_log is None:
            return self.log.plain_text
        return self.read_consolidated_log()

    @property
    def log_file(self):
        return open(self.download_debug_log, 'rb')

def show_config(gui, parent):
    from calibre.gui2.preferences import show_config_widget
    show_config_widget('Sharing', 'Metadata download', parent=parent,
            gui=gui, never_shutdown=True)

class ConfirmDialog(QDialog):

    def __init__(self, ids, parent):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Schedule download?'))
        self.setWindowIcon(QIcon(I('dialog_question.png')))

        l = self.l = QGridLayout()
        self.setLayout(l)

        i = QLabel(self)
        i.setPixmap(QPixmap(I('dialog_question.png')))
        l.addWidget(i, 0, 0)

        t = QLabel(
            '<p>'+_('The download of metadata for the <b>%d selected book(s)</b> will'
                ' run in the background. Proceed?')%len(ids) +
            '<p>'+_('You can monitor the progress of the download '
                'by clicking the rotating spinner in the bottom right '
                'corner.') +
            '<p>'+_('When the download completes you will be asked for'
                ' confirmation before calibre applies the downloaded metadata.')
            )
        t.setWordWrap(True)
        l.addWidget(t, 0, 1)
        l.setColumnStretch(0, 1)
        l.setColumnStretch(1, 100)

        self.identify = self.covers = True
        self.bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.bb.rejected.connect(self.reject)
        b = self.bb.addButton(_('Download only &metadata'),
                self.bb.AcceptRole)
        b.clicked.connect(self.only_metadata)
        b.setIcon(QIcon(I('edit_input.png')))
        b = self.bb.addButton(_('Download only &covers'),
                self.bb.AcceptRole)
        b.clicked.connect(self.only_covers)
        b.setIcon(QIcon(I('default_cover.png')))
        b = self.b = self.bb.addButton(_('&Configure download'), self.bb.ActionRole)
        b.setIcon(QIcon(I('config.png')))
        b.clicked.connect(partial(show_config, parent, self))
        l.addWidget(self.bb, 1, 0, 1, 2)
        b = self.bb.addButton(_('Download &both'),
                self.bb.AcceptRole)
        b.clicked.connect(self.accept)
        b.setDefault(True)
        b.setAutoDefault(True)
        b.setIcon(QIcon(I('ok.png')))

        self.resize(self.sizeHint())
        b.setFocus(Qt.OtherFocusReason)

    def only_metadata(self):
        self.covers = False
        self.accept()

    def only_covers(self):
        self.identify = False
        self.accept()

def split_jobs(ids, batch_size=100):
    ans = []
    ids = list(ids)
    while ids:
        jids = ids[:batch_size]
        ans.append(jids)
        ids = ids[batch_size:]
    return ans

def start_download(gui, ids, callback, ensure_fields=None):
    d = ConfirmDialog(ids, gui)
    ret = d.exec_()
    d.b.clicked.disconnect()
    if ret != d.Accepted:
        return
    tf = PersistentTemporaryFile('_metadata_bulk.log')
    tf.close()

    job = Job('metadata bulk download',
        _('Download metadata for %d books')%len(ids),
        download, (ids, tf.name, gui.current_db, d.identify, d.covers,
            ensure_fields), {}, callback)
    job.download_debug_log = tf.name
    gui.job_manager.run_threaded_job(job)
    gui.status_bar.show_message(_('Metadata download started'), 3000)

# }}}

def get_job_details(job):
    (aborted, good_ids, tdir, log_file, failed_ids, failed_covers, title_map,
            lm_map, all_failed) = job.result
    det_msg = []
    for i in failed_ids | failed_covers:
        title = title_map[i]
        if i in failed_ids:
            title += (' ' + _('(Failed metadata)'))
        if i in failed_covers:
            title += (' ' + _('(Failed cover)'))
        det_msg.append(title)
    det_msg = '\n'.join(det_msg)
    return (aborted, good_ids, tdir, log_file, failed_ids, failed_covers,
            all_failed, det_msg, lm_map)

class HeartBeat(object):
    CHECK_INTERVAL = 300 # seconds
    ''' Check that the file count in tdir changes every five minutes '''

    def __init__(self, tdir):
        self.tdir = tdir
        self.last_count = len(os.listdir(self.tdir))
        self.last_time = time.time()

    def __call__(self):
        if time.time() - self.last_time > self.CHECK_INTERVAL:
            c = len(os.listdir(self.tdir))
            if c == self.last_count:
                return False
            self.last_count = c
            self.last_time = time.time()
        return True

class Notifier(Thread):

    def __init__(self, notifications, title_map, tdir, total):
        Thread.__init__(self)
        self.daemon = True
        self.notifications, self.title_map = notifications, title_map
        self.tdir, self.total = tdir, total
        self.seen = set()
        self.keep_going = True

    def run(self):
        while self.keep_going:
            try:
                names = os.listdir(self.tdir)
            except:
                pass
            else:
                for x in names:
                    if x.endswith('.log'):
                        try:
                            book_id = int(x.partition('.')[0])
                        except:
                            continue
                        if book_id not in self.seen and book_id in self.title_map:
                            self.seen.add(book_id)
                            self.notifications.put((
                                float(len(self.seen))/self.total,
                                _('Processed %s')%self.title_map[book_id]))
            time.sleep(1)

def download(all_ids, tf, db, do_identify, covers, ensure_fields,
        log=None, abort=None, notifications=None):
    batch_size = 10
    batches = split_jobs(all_ids, batch_size=batch_size)
    tdir = PersistentTemporaryDirectory('_metadata_bulk')
    heartbeat = HeartBeat(tdir)

    failed_ids = set()
    failed_covers = set()
    title_map = {}
    lm_map = {}
    ans = set()
    all_failed = True
    aborted = False
    count = 0
    notifier = Notifier(notifications, title_map, tdir, len(all_ids))
    notifier.start()

    try:
        for ids in batches:
            if abort.is_set():
                log.error('Aborting...')
                break
            metadata = {i:db.get_metadata(i, index_is_id=True,
                get_user_categories=False) for i in ids}
            for i in ids:
                title_map[i] = metadata[i].title
                lm_map[i] = metadata[i].last_modified
            metadata = {i:metadata_to_opf(mi, default_lang='und') for i, mi in
                    metadata.iteritems()}
            try:
                ret = fork_job('calibre.ebooks.metadata.sources.worker', 'main',
                        (do_identify, covers, metadata, ensure_fields, tdir),
                        abort=abort, heartbeat=heartbeat, no_output=True)
            except WorkerError as e:
                if e.orig_tb:
                    raise Exception('Failed to download metadata. Original '
                            'traceback: \n\n'+e.orig_tb)
                raise
            count += batch_size

            fids, fcovs, allf = ret['result']
            if not allf:
                all_failed = False
            failed_ids = failed_ids.union(fids)
            failed_covers = failed_covers.union(fcovs)
            ans = ans.union(set(ids) - fids)
            for book_id in ids:
                lp = os.path.join(tdir, '%d.log'%book_id)
                if os.path.exists(lp):
                    with open(tf, 'ab') as dest, open(lp, 'rb') as src:
                        dest.write(('\n'+'#'*20 + ' Log for %s '%title_map[book_id] +
                            '#'*20+'\n').encode('utf-8'))
                        shutil.copyfileobj(src, dest)

        if abort.is_set():
            aborted = True
        log('Download complete, with %d failures'%len(failed_ids))
        return (aborted, ans, tdir, tf, failed_ids, failed_covers, title_map,
                lm_map, all_failed)
    finally:
        notifier.keep_going = False


