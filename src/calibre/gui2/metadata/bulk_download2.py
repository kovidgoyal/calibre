#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
from itertools import izip

from PyQt4.Qt import (QIcon, QDialog, QVBoxLayout, QTextBrowser, QSize,
        QDialogButtonBox, QApplication, QTimer, QLabel, QProgressBar)

from calibre.gui2.dialogs.message_box import MessageBox
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.utils.icu import lower
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2 import question_dialog, error_dialog

def show_config(gui, parent):
    from calibre.gui2.preferences import show_config_widget
    show_config_widget('Sharing', 'Metadata download', parent=parent,
            gui=gui, never_shutdown=True)

def start_download(gui, ids, callback, identify, covers):
    q = MessageBox(MessageBox.QUESTION,  _('Schedule download?'),
            '<p>'+_('The download of metadata for the <b>%d selected book(s)</b> will'
                ' run in the background. Proceed?')%len(ids) +
            '<p>'+_('You can monitor the progress of the download '
                'by clicking the rotating spinner in the bottom right '
                'corner.') +
            '<p>'+_('When the download completes you will be asked for'
                ' confirmation before calibre applies the downloaded metadata.'),
            show_copy_button=False, parent=gui)
    b = q.bb.addButton(_('Configure download'), q.bb.ActionRole)
    b.setIcon(QIcon(I('config.png')))
    b.clicked.connect(partial(show_config, gui, q))
    q.det_msg_toggle.setVisible(False)

    ret = q.exec_()
    b.clicked.disconnect()
    if ret != q.Accepted:
        return

    job = ThreadedJob('metadata bulk download',
            _('Download metadata for %d books')%len(ids),
            download, (ids, gui.current_db, identify, covers), {}, callback)
    gui.job_manager.run_threaded_job(job)

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
        self.resize(QSize(500, 400))
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

class ApplyDialog(QDialog):

    def __init__(self, id_map, gui):
        QDialog.__init__(self, gui)

        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.addWidget(QLabel(_('Applying downloaded metadata to your library')))

        self.pb = QProgressBar(self)
        l.addWidget(self.pb)
        self.pb.setMinimum(0)
        self.pb.setMaximum(len(id_map))

        self.bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.bb.rejected.connect(self.reject)
        self.bb.accepted.connect(self.accept)
        l.addWidget(self.bb)

        self.db = gui.current_db
        self.id_map = list(id_map.iteritems())
        self.current_idx = 0

        self.failures = []
        self.canceled = False

        QTimer.singleShot(20, self.do_one)
        self.exec_()

    def do_one(self):
        if self.canceled:
            return
        i, mi = self.id_map[self.current_idx]
        try:
            set_title = not mi.is_null('title')
            set_authors = not mi.is_null('authors')
            self.db.set_metadata(i, mi, commit=False, set_title=set_title,
                    set_authors=set_authors)
        except:
            import traceback
            self.failures.append((i, traceback.format_exc()))

        self.pb.setValue(self.pb.value()+1)

        if self.current_idx >= len(self.id_map) - 1:
            self.finalize()
        else:
            self.current_idx += 1
            QTimer.singleShot(20, self.do_one)

    def reject(self):
        self.canceled = True
        QDialog.reject(self)

    def finalize(self):
        if self.canceled:
            return
        if self.failures:
            msg = []
            for i, tb in self.failures:
                title = self.db.title(i, index_is_id=True)
                authors = self.db.authors(i, index_is_id=True)
                if authors:
                    authors = [x.replace('|', ',') for x in authors.split(',')]
                    title += ' - ' + authors_to_string(authors)
                msg.append(title+'\n\n'+tb+'\n'+('*'*80))

            error_dialog(self, _('Some failures'),
                _('Failed to apply updated metadata for some books'
                    ' in your library. Click "Show Details" to see '
                    'details.'), det_msg='\n\n'.join(msg), show=True)
        self.accept()

_amd = None
def apply_metadata(job, gui, q, result):
    global _amd
    q.vlb.clicked.disconnect()
    q.finished.disconnect()
    if result != q.Accepted:
        return
    id_map, failed_ids = job.result
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

    _amd = ApplyDialog(id_map, gui)

def proceed(gui, job):
    id_map, failed_ids = job.result
    fmsg = det_msg = ''
    if failed_ids:
        fmsg = _('Could not download metadata for %d of the books. Click'
                ' "Show details" to see which books.')%len(failed_ids)
        det_msg = '\n'.join([id_map[i].title for i in failed_ids])
    msg = '<p>' + _('Finished downloading metadata for <b>%d book(s)</b>. '
        'Proceed with updating the metadata in your library?')%len(id_map)
    q = MessageBox(MessageBox.QUESTION, _('Download complete'),
            msg + fmsg, det_msg=det_msg, show_copy_button=bool(failed_ids),
            parent=gui)
    q.vlb = q.bb.addButton(_('View log'), q.bb.ActionRole)
    q.vlb.setIcon(QIcon(I('debug.png')))
    q.vlb.clicked.connect(partial(view_log, job, q))
    q.det_msg_toggle.setVisible(bool(failed_ids))
    q.setModal(False)
    q.show()
    q.finished.connect(partial(apply_metadata, job, gui, q))


def download(ids, db, identify, covers,
        log=None, abort=None, notifications=None):
    ids = list(ids)
    metadata = [db.get_metadata(i, index_is_id=True, get_user_categories=False)
        for i in ids]
    failed_ids = set()
    ans = {}
    count = 0
    for i, mi in izip(ids, metadata):
        if abort.is_set():
            log.error('Aborting...')
            break
        # TODO: Apply ignore_fields and set unchanged values to null values
        ans[i] = mi
        count += 1
        notifications.put((count/len(ids),
            _('Downloaded %d of %d')%(count, len(ids))))
    log('Download complete, with %d failures'%len(failed_ids))
    return (ans, failed_ids)



