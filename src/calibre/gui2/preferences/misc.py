#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QProgressDialog, QThread, Qt, pyqtSignal

from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.misc_ui import Ui_Form
from calibre.gui2 import error_dialog, config, warning_dialog, \
        open_local_file, info_dialog
from calibre.constants import isosx

# Check Integrity {{{

class VacThread(QThread):

    check_done = pyqtSignal(object, object)
    callback   = pyqtSignal(object, object)

    def __init__(self, parent, db):
        QThread.__init__(self, parent)
        self.db = db
        self._parent = parent

    def run(self):
        err = bad = None
        try:
            bad = self.db.check_integrity(self.callbackf)
        except:
            import traceback
            err = traceback.format_exc()
        self.check_done.emit(bad, err)

    def callbackf(self, progress, msg):
        self.callback.emit(progress, msg)


class CheckIntegrity(QProgressDialog):

    def __init__(self, db, parent=None):
        QProgressDialog.__init__(self, parent)
        self.db = db
        self.setCancelButton(None)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setWindowTitle(_('Checking database integrity'))
        self.setAutoReset(False)
        self.setValue(0)

        self.vthread = VacThread(self, db)
        self.vthread.check_done.connect(self.check_done,
                type=Qt.QueuedConnection)
        self.vthread.callback.connect(self.callback, type=Qt.QueuedConnection)
        self.vthread.start()

    def callback(self, progress, msg):
        self.setLabelText(msg)
        self.setValue(int(100*progress))

    def check_done(self, bad, err):
        if err:
            error_dialog(self, _('Error'),
                    _('Failed to check database integrity'),
                    det_msg=err, show=True)
        elif bad:
            titles = [self.db.title(x, index_is_id=True) for x in bad]
            det_msg = '\n'.join(titles)
            warning_dialog(self, _('Some inconsistencies found'),
                    _('The following books had formats listed in the '
                        'database that are not actually available. '
                        'The entries for the formats have been removed. '
                        'You should check them manually. This can '
                        'happen if you manipulate the files in the '
                        'library folder directly.'), det_msg=det_msg, show=True)
        self.reset()

# }}}

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        r = self.register
        r('worker_limit', config, restart_required=True)
        r('enforce_cpu_limit', config, restart_required=True)
        self.device_detection_button.clicked.connect(self.debug_device_detection)
        self.compact_button.clicked.connect(self.compact)
        self.button_all_books_dirty.clicked.connect(self.mark_dirty)
        self.button_open_config_dir.clicked.connect(self.open_config_dir)
        self.button_osx_symlinks.clicked.connect(self.create_symlinks)
        self.button_osx_symlinks.setVisible(isosx)

    def mark_dirty(self):
        db = self.gui.library_view.model().db
        db.dirtied(list(db.data.iterallids()))
        info_dialog(self, _('Backup metadata'),
            _('Metadata will be backed up while calibre is running, at the '
              'rate of 30 books per minute.'), show=True)

    def debug_device_detection(self, *args):
        from calibre.gui2.preferences.device_debug import DebugDevice
        d = DebugDevice(self)
        d.exec_()

    def compact(self, *args):
        from calibre.library.caches import MetadataBackup
        m = self.gui.library_view.model()
        if m.metadata_backup is not None:
            m.metadata_backup.stop()
        d = CheckIntegrity(m.db, self)
        d.exec_()
        m.metadata_backup = MetadataBackup(m.db)
        m.metadata_backup.start()

    def open_config_dir(self, *args):
        from calibre.utils.config import config_dir
        open_local_file(config_dir)

    def create_symlinks(self):
        from calibre.utils.osx_symlinks import create_symlinks
        loc, paths = create_symlinks()
        if loc is None:
            error_dialog(self, _('Error'),
                    _('Failed to install command line tools.'),
                    det_msg=paths, show=True)
        else:
            info_dialog(self, _('Command line tools installed'),
            '<p>'+_('Command line tools installed in')+' '+loc+
            '<br>'+ _('If you move calibre.app, you have to re-install '
                    'the command line tools.'),
                det_msg='\n'.join(paths), show=True)


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Advanced', 'Misc')

