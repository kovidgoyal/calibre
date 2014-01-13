#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import (QDialog, QDialogButtonBox)

from calibre.gui2.tweak_book import tprefs

class Dialog(QDialog):

    def __init__(self, title, name, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(title)
        self.name = name
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)

        self.setup_ui()

        self.resize(self.sizeHint())
        geom = tprefs.get(name + '-geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)
        if hasattr(self, 'splitter'):
            state = tprefs.get(name + '-splitter-state', None)
            if state is not None:
                self.splitter.restoreState(state)

    def accept(self):
        tprefs.set(self.name + '-geometry', bytearray(self.saveGeometry()))
        if hasattr(self, 'splitter'):
            tprefs.set(self.name + '-splitter-state', bytearray(self.splitter.saveState()))
        QDialog.accept(self)

    def reject(self):
        tprefs.set(self.name + '-geometry', bytearray(self.saveGeometry()))
        if hasattr(self, 'splitter'):
            tprefs.set(self.name + '-splitter-state', bytearray(self.splitter.saveState()))
        QDialog.reject(self)

    def setup_ui(self):
        raise NotImplementedError('You must implement this method in Dialog subclasses')

