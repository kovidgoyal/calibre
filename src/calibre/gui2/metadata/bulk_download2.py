#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
from itertools import izip

from PyQt4.Qt import (QIcon, QDialog, QVBoxLayout, QTextBrowser,
        QDialogButtonBox, QApplication)

from calibre.gui2.dialogs.message_box import MessageBox
from calibre.gui2.threaded_jobs import ThreadedJob

def show_config(gui, parent):
    from calibre.gui2.preferences import show_config_widget
    show_config_widget('Sharing', 'Metadata download', parent=parent,
            gui=gui, never_shutdown=True)

def start_download(gui, ids, callback):
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
            download, (ids, gui.current_db), {}, callback)
    gui.job_manager.run_threaded_job(job)

class ViewLog(QDialog):

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
        self.setModal(False)
        self.resize(self.sizeHint())
        self.show()

    def copy_to_clipboard(self):
        txt = self.tb.toPlainText()
        QApplication.clipboard().setText(txt)

_vl = None
def view_log(job, parent):
    global _vl
    _vl = ViewLog(job.html_details, parent)

def apply(job, gui, q):
    q.vlb.clicked.disconnect()
    q.finished.diconnect()
    id_map, failed_ids = job.result
    print (id_map)

def proceed(gui, job):
    id_map, failed_ids = job.result
    fmsg = det_msg = ''
    if failed_ids:
        fmsg = _('Could not download metadata for %d of the books. Click'
                ' "Show details" to see which books.')%len(failed_ids)
        det_msg = '\n'.join([id_map[i].title for i in failed_ids])
    msg = '<p>' + _('Finished downloading metadata for %d books. '
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
    q.finished.connect(partial(job, gui, q))


def download(ids, db, log=None, abort=None, notifications=None):
    log('Starting metadata download for %d books'%len(ids))
    ids = list(ids)
    metadata = [db.get_metadata(i, index_is_id=True, get_user_categories=False)
        for i in ids]
    failed_ids = set()
    ans = {}
    for i, mi in izip(ids, metadata):
        ans[i] = mi
    log('Download complete, with %d failures'%len(failed_ids))
    return (ans, failed_ids)



