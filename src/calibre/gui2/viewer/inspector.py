#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import QDialog, QDialogButtonBox, QVBoxLayout, QIcon
from PyQt5.QtWebKitWidgets import QWebInspector

from calibre.gui2 import gprefs

class WebInspector(QDialog):

    def __init__(self, parent, page):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Inspect book code'))
        self.setWindowIcon(QIcon(I('debug.png')))
        l = QVBoxLayout()
        self.setLayout(l)

        self.inspector = QWebInspector(self)
        self.inspector.setPage(page)
        l.addWidget(self.inspector)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Close)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        self.resize(self.sizeHint())

        geom = gprefs.get('viewer_inspector_geom', None)
        if geom is not None:
            self.restoreGeometry(geom)

    def save_geometry(self):
        gprefs['viewer_inspector_geom'] = bytearray(self.saveGeometry())

    def closeEvent(self, ev):
        self.save_geometry()
        return QDialog.closeEvent(self, ev)

    def accept(self):
        self.save_geometry()
        QDialog.accept(self)

    def reject(self):
        self.save_geometry()
        QDialog.reject(self)

