#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial
from itertools import izip

from PyQt4.Qt import (QIcon, QDialog, QVBoxLayout, QTextBrowser, QSize,
        QDialogButtonBox, QApplication, QTimer, QLabel, QProgressBar,
        QGridLayout, QPixmap, Qt)

from calibre.gui2.dialogs.message_box import MessageBox
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.utils.icu import lower
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2 import question_dialog, error_dialog
from calibre.ebooks.metadata.sources.identify import identify, msprefs
from calibre.ebooks.metadata.sources.covers import download_cover
from calibre.ebooks.metadata.book.base import Metadata
from calibre.customize.ui import metadata_plugins
from calibre.ptempfile import PersistentTemporaryFile

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

def start_download(gui, ids, callback):
    d = ConfirmDialog(ids, gui)
    ret = d.exec_()
    d.b.clicked.disconnect()
    if ret != d.Accepted:
        return

    job = ThreadedJob('metadata bulk download',
            _('Download metadata for %d books')%len(ids),
            download, (ids, gui.current_db, d.identify, d.covers), {}, callback)
    gui.job_manager.run_threaded_job(job)
    gui.status_bar.show_message(_('Metadata download started'), 3000)
# }}}

class ViewLog(QDialog): # {{{

    def __init__(self, html, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)

        self.tb = QTextBrowser(self)
        self.tb.setHtml('<pre style="font-family: monospace">%s</pre>' % html)
        l.addWidget(self.tb)

        self.bb = QDialogButtonBox(QDialogButtonBox.Ok)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.copy_button = self.bb.addButton(_('Copy to clipboard'),
                self.bb.ActionRole)
        self.copy_button.setIcon(QIcon(I('edit-copy.png')))
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        l.addWidget(self.bb)
        self.setModal(False)
        self.resize(QSize(700, 500))
        self.setWindowTitle(_('Download log'))
        self.setWindowIcon(QIcon(I('debug.png')))
        self.show()

    def copy_to_clipboard(self):
        txt = self.tb.toPlainText()
        QApplication.clipboard().setText(txt)

_vl = None
def view_log(job, parent):
    global _vl
    _vl = ViewLog(job.html_details, parent)

# }}}

# Apply downloaded metadata {{{
class ApplyDialog(QDialog):

    def __init__(self, gui):
        QDialog.__init__(self, gui)

        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.addWidget(QLabel(_('Applying downloaded metadata to your library')))

        self.pb = QProgressBar(self)
        l.addWidget(self.pb)

        self.bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.bb.rejected.connect(self.reject)
        l.addWidget(self.bb)

        self.gui = gui
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.do_one)

    def start(self, id_map):
        self.id_map = list(id_map.iteritems())
        self.current_idx = 0
        self.failures = []
        self.ids = []
        self.canceled = False
        self.pb.setMinimum(0)
        self.pb.setMaximum(len(id_map))
        self.timer.start(50)

    def do_one(self):
        if self.canceled:
            return
        if self.current_idx >= len(self.id_map):
            self.timer.stop()
            self.finalize()
            return

        i, mi = self.id_map[self.current_idx]
        db = self.gui.current_db
        try:
            set_title = not mi.is_null('title')
            set_authors = not mi.is_null('authors')
            db.set_metadata(i, mi, commit=False, set_title=set_title,
                    set_authors=set_authors)
            self.ids.append(i)
        except:
            import traceback
            self.failures.append((i, traceback.format_exc()))

        try:
            if mi.cover:
                os.remove(mi.cover)
        except:
            pass

        self.pb.setValue(self.pb.value()+1)
        self.current_idx += 1

    def reject(self):
        self.canceled = True
        self.timer.stop()
        QDialog.reject(self)

    def finalize(self):
        if self.canceled:
            return
        if self.failures:
            msg = []
            db = self.gui.current_db
            for i, tb in self.failures:
                title = db.title(i, index_is_id=True)
                authors = db.authors(i, index_is_id=True)
                if authors:
                    authors = [x.replace('|', ',') for x in authors.split(',')]
                    title += ' - ' + authors_to_string(authors)
                msg.append(title+'\n\n'+tb+'\n'+('*'*80))

            parent = self if self.isVisible() else self.parent()
            error_dialog(parent, _('Some failures'),
                _('Failed to apply updated metadata for some books'
                    ' in your library. Click "Show Details" to see '
                    'details.'), det_msg='\n\n'.join(msg), show=True)
        if self.ids:
            cr = self.gui.library_view.currentIndex().row()
            self.gui.library_view.model().refresh_ids(
                self.ids, cr)
            if self.gui.cover_flow:
                self.gui.cover_flow.dataChanged()
        self.accept()

_amd = None
def apply_metadata(job, gui, q, result):
    global _amd
    q.vlb.clicked.disconnect()
    q.finished.disconnect()
    if result != q.Accepted:
        return
    id_map, failed_ids, failed_covers, title_map, all_failed = job.result
    id_map = dict([(k, v) for k, v in id_map.iteritems() if k not in
        failed_ids])
    if not id_map:
        return

    modified = set()
    db = gui.current_db

    for i, mi in id_map.iteritems():
        lm = db.metadata_last_modified(i, index_is_id=True)
        if lm > mi.last_modified:
            title = db.title(i, index_is_id=True)
            authors = db.authors(i, index_is_id=True)
            if authors:
                authors = [x.replace('|', ',') for x in authors.split(',')]
                title += ' - ' + authors_to_string(authors)
            modified.add(title)

    if modified:
        modified = sorted(modified, key=lower)
        if not question_dialog(gui, _('Some books changed'), '<p>'+
                _('The metadata for some books in your library has'
                    ' changed since you started the download. If you'
                    ' proceed, some of those changes may be overwritten. '
                    'Click "Show details" to see the list of changed books. '
                    'Do you want to proceed?'), det_msg='\n'.join(modified)):
            return

    if _amd is None:
        _amd = ApplyDialog(gui)
    _amd.start(id_map)
    if len(id_map) > 3:
        _amd.exec_()

def proceed(gui, job):
    gui.status_bar.show_message(_('Metadata download completed'), 3000)
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

    if all_failed:
        q = error_dialog(gui, _('Download failed'),
            _('Failed to download metadata or covers for any of the %d'
               ' book(s).') % len(id_map), det_msg=det_msg)
    else:
        fmsg = det_msg = ''
        if failed_ids or failed_covers:
            fmsg = '<p>'+_('Could not download metadata and/or covers for %d of the books. Click'
                    ' "Show details" to see which books.')%len(failed_ids)
        msg = '<p>' + _('Finished downloading metadata for <b>%d book(s)</b>. '
            'Proceed with updating the metadata in your library?')%len(id_map)
        q = MessageBox(MessageBox.QUESTION, _('Download complete'),
                msg + fmsg, det_msg=det_msg, show_copy_button=bool(failed_ids),
                parent=gui)
        q.finished.connect(partial(apply_metadata, job, gui, q))

    q.vlb = q.bb.addButton(_('View log'), q.bb.ActionRole)
    q.vlb.setIcon(QIcon(I('debug.png')))
    q.vlb.clicked.connect(partial(view_log, job, q))
    q.det_msg_toggle.setVisible(bool(failed_ids | failed_covers))
    q.setModal(False)
    q.show()

# }}}

def merge_result(oldmi, newmi):
    dummy = Metadata(_('Unknown'))
    for f in msprefs['ignore_fields']:
        if ':' not in f:
            setattr(newmi, f, getattr(dummy, f))
    fields = set()
    for plugin in metadata_plugins(['identify']):
        fields |= plugin.touched_fields

    for f in fields:
        # Optimize so that set_metadata does not have to do extra work later
        if not f.startswith('identifier:'):
            if (not newmi.is_null(f) and getattr(newmi, f) == getattr(oldmi, f)):
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
    for i, mi in izip(ids, metadata):
        if abort.is_set():
            log.error('Aborting...')
            break
        title, authors, identifiers = mi.title, mi.authors, mi.identifiers
        title_map[i] = title
        if do_identify:
            results = []
            try:
                results = identify(log, abort, title=title, authors=authors,
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
            _('Downloaded %d of %d')%(count, len(ids))))
    log('Download complete, with %d failures'%len(failed_ids))
    return (ans, failed_ids, failed_covers, title_map, all_failed)



