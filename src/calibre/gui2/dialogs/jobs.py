__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Display active jobs'''

from PyQt4.QtCore import Qt, QObject, SIGNAL, QSize, QString, QTimer
from PyQt4.QtGui import QDialog, QAbstractItemDelegate, QStyleOptionProgressBarV2, \
                        QApplication, QStyle

from calibre.gui2.dialogs.jobs_ui import Ui_JobsDialog
from calibre import __appname__

class ProgressBarDelegate(QAbstractItemDelegate):

    def sizeHint(self, option, index):
        return QSize(120, 30)

    def paint(self, painter, option, index):
        opts = QStyleOptionProgressBarV2()
        opts.rect = option.rect
        opts.minimum = 1
        opts.maximum = 100
        opts.textVisible = True
        percent, ok = index.model().data(index, Qt.DisplayRole).toInt()
        if not ok:
            percent = 0
        opts.progress = percent
        opts.text = QString(_('Unavailable') if percent == 0 else '%d%%'%percent)
        QApplication.style().drawControl(QStyle.CE_ProgressBar, opts, painter)

class JobsDialog(QDialog, Ui_JobsDialog):
    def __init__(self, window, model):
        QDialog.__init__(self, window)
        Ui_JobsDialog.__init__(self)
        self.setupUi(self)
        self.jobs_view.setModel(model)
        self.model = model
        self.setWindowModality(Qt.NonModal)
        self.setWindowTitle(__appname__ + _(' - Jobs'))
        QObject.connect(self.jobs_view.model(), SIGNAL('modelReset()'),
                        self.jobs_view.resizeColumnsToContents)
        QObject.connect(self.kill_button, SIGNAL('clicked()'),
                        self.kill_job)
        QObject.connect(self, SIGNAL('kill_job(int, PyQt_PyObject)'),
                        self.jobs_view.model().kill_job)
        self.pb_delegate = ProgressBarDelegate(self)
        self.jobs_view.setItemDelegateForColumn(2, self.pb_delegate)

        self.running_time_timer = QTimer(self)
        self.connect(self.running_time_timer, SIGNAL('timeout()'), self.update_running_time)
        self.running_time_timer.start(1000)

    def update_running_time(self, *args):
        try:
            self.model.running_time_updated()
        except: # Raises random exceptions on OS X
            pass

    def kill_job(self):
        for index in self.jobs_view.selectedIndexes():
            row = index.row()
            self.model.kill_job(row, self)
            return

    def closeEvent(self, e):
        self.jobs_view.write_settings()
        e.accept()
