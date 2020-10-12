#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import QDialog, QVBoxLayout, QPlainTextEdit, QTimer, \
    QDialogButtonBox, QPushButton, QApplication, QIcon

from calibre.gui2 import error_dialog


class DebugDevice(QDialog):

    def __init__(self, gui, parent=None):
        QDialog.__init__(self, parent)
        self.gui = gui
        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)
        self.log = QPlainTextEdit(self)
        self._layout.addWidget(self.log)
        self.log.setPlainText(_('Getting debug information, please wait')+'...')
        self.copy = QPushButton(_('Copy to &clipboard'))
        self.copy.setDefault(True)
        self.setWindowTitle(_('Debug device detection'))
        self.setWindowIcon(QIcon(I('debug.png')))
        self.copy.clicked.connect(self.copy_to_clipboard)
        self.ok = QPushButton('&OK')
        self.ok.setAutoDefault(False)
        self.ok.clicked.connect(self.accept)
        self.bbox = QDialogButtonBox(self)
        self.bbox.addButton(self.copy, QDialogButtonBox.ActionRole)
        self.bbox.addButton(self.ok, QDialogButtonBox.AcceptRole)
        self._layout.addWidget(self.bbox)
        self.resize(750, 500)
        self.bbox.setEnabled(False)
        QTimer.singleShot(1000, self.debug)

    def debug(self):
        if self.gui.device_manager.is_device_connected:
            error_dialog(self, _('Device already detected'),
                    _('A device (%s) is already detected by calibre.'
                        ' If you wish to debug the detection of another device'
                        ', first disconnect this device.')%
                    self.gui.device_manager.connected_device.get_gui_name(),
                    show=True)
            self.bbox.setEnabled(True)
            return
        self.gui.debug_detection(self)

    def __call__(self, job):
        if not self.isVisible():
            return
        self.bbox.setEnabled(True)
        if job.failed:
            return error_dialog(self, _('Debugging failed'),
                    _('Running debug device detection failed. Click Show '
                        'Details for more information.'), det_msg=job.details,
                    show=True)
        self.log.setPlainText(job.result)

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.log.toPlainText())


if __name__ == '__main__':
    app = QApplication([])
    d = DebugDevice()
    d.exec_()
