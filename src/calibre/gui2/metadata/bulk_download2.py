#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QIcon

from calibre.gui2.dialogs.message_box import MessageBox
from calibre.gui2.threaded_jobs import ThreadedJob

def show_config(gui, parent):
    from calibre.gui2.preferences import show_config_widget
    show_config_widget('Sharing', 'Metadata download', parent=parent,
            gui=gui, never_shutdown=True)

def start_download(gui, ids, callback):
    q = MessageBox(MessageBox.QUESTION,  _('Schedule download?'),
            _('The download of metadata for <b>%d book(s)</b> will'
                ' run in the background. Proceed?')%len(ids),
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


def download(ids, db, log=None, abort=None, notifications=None):
    ids = list(ids)
    metadata = [db.get_metadata(i, index_is_id=True, get_user_categories=False)
        for i in ids]
    return (ids, [mi.last_modified for mi in metadata])



