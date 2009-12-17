#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import QDialog, QVBoxLayout, QPlainTextEdit, QTimer, \
    QDialogButtonBox, QPushButton, QApplication, QIcon

class DebugDevice(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)
        self.log = QPlainTextEdit(self)
        self._layout.addWidget(self.log)
        self.log.setPlainText(_('Getting debug information')+'...')
        self.copy = QPushButton(_('Copy to &clipboard'))
        self.copy.setDefault(True)
        self.setWindowTitle(_('Debug device detection'))
        self.setWindowIcon(QIcon(I('debug.svg')))
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
        try:
            from calibre.devices import debug
            raw = debug()
            self.log.setPlainText(raw)
        finally:
            self.bbox.setEnabled(True)

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.log.toPlainText())

if __name__ == '__main__':
    app = QApplication([])
    d = DebugDevice()
    d.exec_()
