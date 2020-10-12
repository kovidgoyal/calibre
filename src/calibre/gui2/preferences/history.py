#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from PyQt5.Qt import QComboBox, Qt

from calibre.gui2 import config as gui_conf
from polyglot.builtins import unicode_type


class HistoryBox(QComboBox):

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        self.setEditable(True)

    def initialize(self, opt_name, default, help=None):
        self.opt_name = opt_name
        self.set_value(default)
        if help:
            self.setStatusTip(help)
            help = '\n'.join(textwrap.wrap(help))
            self.setToolTip(help)
            self.setWhatsThis(help)

    def set_value(self, val):
        history = gui_conf[self.opt_name]
        if val not in history:
            history.append(val)
        self.clear()
        self.addItems(history)
        self.setCurrentIndex(self.findText(val, Qt.MatchFixedString))

    def save_history(self, opt_name):
        history = [unicode_type(self.itemText(i)) for i in range(self.count())]
        ct = self.text()
        if ct not in history:
            history = [ct] + history
        gui_conf[opt_name] = history[:10]

    def text(self):
        return unicode_type(self.currentText()).strip()
