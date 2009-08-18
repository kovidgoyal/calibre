#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QComboBox, QStringList, Qt

from calibre.gui2 import config as gui_conf

class HistoryBox(QComboBox):

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        self.setEditable(True)

    def initialize(self, opt_name, default, help=None):
        history = gui_conf[opt_name]
        if default not in history:
            history.append(default)
        self.addItems(QStringList(history))
        self.setCurrentIndex(self.findText(default, Qt.MatchFixedString))
        if help is not None:
            self.setToolTip(help)
            self.setWhatsThis(help)

    def save_history(self, opt_name):
        history = [unicode(self.itemText(i)) for i in range(self.count())]
        ct = self.text()
        if ct not in history:
            history = [ct] + history
        gui_conf[opt_name] = history[:10]

    def text(self):
        return unicode(self.currentText()).strip()



