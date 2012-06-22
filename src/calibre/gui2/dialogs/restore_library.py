#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QDialog, QLabel, QVBoxLayout, QDialogButtonBox,
        QProgressBar, QSize, QTimer, pyqtSignal, Qt)

from calibre.library.restore import Restore
from calibre.gui2 import (error_dialog, question_dialog, warning_dialog,
    info_dialog)
from calibre import force_unicode
from calibre.constants import filesystem_encoding

class DBRestore(QDialog):

    update_signal = pyqtSignal(object, object)

    def __init__(self, parent, library_path):
        QDialog.__init__(self, parent)
        self.l = QVBoxLayout()
        self.setLayout(self.l)
        self.l1 = QLabel('<b>'+_('Restoring database from backups, do not'
            ' interrupt, this will happen in three stages')+'...')
        self.setWindowTitle(_('Restoring database'))
        self.l.addWidget(self.l1)
        self.pb = QProgressBar(self)
        self.l.addWidget(self.pb)
        self.pb.setMaximum(0)
        self.pb.setMinimum(0)
        self.msg = QLabel('')
        self.l.addWidget(self.msg)
        self.msg.setWordWrap(True)
        self.bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.l.addWidget(self.bb)
        self.bb.rejected.connect(self.reject)
        self.resize(self.sizeHint() + QSize(100, 50))
        self.error = None
        self.rejected = False
        self.library_path = library_path
        self.update_signal.connect(self.do_update, type=Qt.QueuedConnection)

        self.restorer = Restore(library_path, self)
        self.restorer.daemon = True

        # Give the metadata backup thread time to stop
        QTimer.singleShot(2000, self.start)


    def start(self):
        self.restorer.start()
        QTimer.singleShot(10, self.update)

    def reject(self):
        self.rejected = True
        self.restorer.progress_callback = lambda x, y: x
        QDialog.reject(self)

    def update(self):
        if self.restorer.is_alive():
            QTimer.singleShot(10, self.update)
        else:
            self.restorer.progress_callback = lambda x, y: x
            self.accept()

    def __call__(self, msg, step):
        self.update_signal.emit(msg, step)

    def do_update(self, msg, step):
        if msg is None:
            self.pb.setMaximum(step)
        else:
            self.msg.setText(msg)
            self.pb.setValue(step)

def _show_success_msg(restorer, parent=None):
    r = restorer
    olddb = _('The old database was saved as: %s')%force_unicode(r.olddb,
            filesystem_encoding)
    if r.errors_occurred:
        warning_dialog(parent, _('Success'),
                _('Restoring the database succeeded with some warnings'
                    ' click Show details to see the details. %s')%olddb,
                det_msg=r.report, show=True)
    else:
        info_dialog(parent, _('Success'),
                _('Restoring database was successful. %s')%olddb, show=True,
                show_copy_button=False)

def restore_database(db, parent=None):
    if not question_dialog(parent, _('Are you sure?'), '<p>'+
            _('Your list of books, with all their metadata is '
                'stored in a single file, called a database. '
                'In addition, metadata for each individual '
                'book is stored in that books\' folder, as '
                'a backup.'
                '<p>This operation will rebuild '
                'the database from the individual book '
                'metadata. This is useful if the '
                'database has been corrupted and you get a '
                'blank list of books.'
                '<p>Do you want to restore the database?')):
        return False
    db.conn.close()
    d = DBRestore(parent, db.library_path)
    d.exec_()
    r = d.restorer
    d.restorer = None
    if d.rejected:
        return True
    if r.tb is not None:
        error_dialog(parent, _('Failed'),
        _('Restoring database failed, click Show details to see details'),
        det_msg=r.tb, show=True)
    else:
        _show_success_msg(r, parent=parent)
    return True

def repair_library_at(library_path, parent=None):
    d = DBRestore(parent, library_path)
    d.exec_()
    if d.rejected:
        return False
    r = d.restorer
    if r.tb is not None:
        error_dialog(parent, _('Failed'),
        _('Restoring database failed, click Show details to see details'),
        det_msg=r.tb, show=True)
        return False
    _show_success_msg(r, parent=parent)
    return True


