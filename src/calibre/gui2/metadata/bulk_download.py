#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
from itertools import izip
from threading import Event

from PyQt4.Qt import (QIcon, QDialog,
        QDialogButtonBox, QLabel, QGridLayout, QPixmap, Qt)

from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.ebooks.metadata.sources.identify import identify, msprefs
from calibre.ebooks.metadata.sources.covers import download_cover
from calibre.ebooks.metadata.book.base import Metadata
from calibre.customize.ui import metadata_plugins
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.date import as_utc

# Start download {{{
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

def start_download(gui, ids, callback):
    d = ConfirmDialog(ids, gui)
    ret = d.exec_()
    d.b.clicked.disconnect()
    if ret != d.Accepted:
        return

    for batch in split_jobs(ids):
        job = ThreadedJob('metadata bulk download',
            _('Download metadata for %d books')%len(batch),
            download, (batch, gui.current_db, d.identify, d.covers), {}, callback)
        gui.job_manager.run_threaded_job(job)
    gui.status_bar.show_message(_('Metadata download started'), 3000)

# }}}

def get_job_details(job):
    id_map, failed_ids, failed_covers, title_map, all_failed = job.result
    det_msg = []
    for i in failed_ids | failed_covers:
        title = title_map[i]
        if i in failed_ids:
            title += (' ' + _('(Failed metadata)'))
        if i in failed_covers:
            title += (' ' + _('(Failed cover)'))
        det_msg.append(title)
    det_msg = '\n'.join(det_msg)
    return id_map, failed_ids, failed_covers, all_failed, det_msg

def merge_result(oldmi, newmi):
    dummy = Metadata(_('Unknown'))
    for f in msprefs['ignore_fields']:
        if ':' not in f:
            setattr(newmi, f, getattr(dummy, f))
    fields = set()
    for plugin in metadata_plugins(['identify']):
        fields |= plugin.touched_fields

    def is_equal(x, y):
        if hasattr(x, 'tzinfo'):
            x = as_utc(x)
        if hasattr(y, 'tzinfo'):
            y = as_utc(y)
        return x == y

    for f in fields:
        # Optimize so that set_metadata does not have to do extra work later
        if not f.startswith('identifier:'):
            if (not newmi.is_null(f) and is_equal(getattr(newmi, f),
                    getattr(oldmi, f))):
                setattr(newmi, f, getattr(dummy, f))

    newmi.last_modified = oldmi.last_modified

    return newmi

def download(ids, db, do_identify, covers,
        log=None, abort=None, notifications=None):
    ids = list(ids)
    metadata = [db.get_metadata(i, index_is_id=True, get_user_categories=False)
        for i in ids]
    failed_ids = set()
    failed_covers = set()
    title_map = {}
    ans = {}
    count = 0
    all_failed = True
    '''
    # Test apply dialog
    all_failed = do_identify = covers = False
    '''
    for i, mi in izip(ids, metadata):
        if abort.is_set():
            log.error('Aborting...')
            break
        title, authors, identifiers = mi.title, mi.authors, mi.identifiers
        title_map[i] = title
        if do_identify:
            results = []
            try:
                results = identify(log, Event(), title=title, authors=authors,
                    identifiers=identifiers)
            except:
                pass
            if results:
                all_failed = False
                mi = merge_result(mi, results[0])
                identifiers = mi.identifiers
                if not mi.is_null('rating'):
                    # set_metadata expects a rating out of 10
                    mi.rating *= 2
            else:
                log.error('Failed to download metadata for', title)
                failed_ids.add(i)
                # We don't want set_metadata operating on anything but covers
                mi = merge_result(mi, mi)
        if covers:
            cdata = download_cover(log, title=title, authors=authors,
                    identifiers=identifiers)
            if cdata is not None:
                with PersistentTemporaryFile('.jpg', 'downloaded-cover-') as f:
                    f.write(cdata[-1])
                    mi.cover = f.name
                all_failed = False
            else:
                failed_covers.add(i)
        ans[i] = mi
        count += 1
        notifications.put((count/len(ids),
            _('Downloaded %(num)d of %(tot)d')%dict(num=count, tot=len(ids))))
    log('Download complete, with %d failures'%len(failed_ids))
    return (ans, failed_ids, failed_covers, title_map, all_failed)



