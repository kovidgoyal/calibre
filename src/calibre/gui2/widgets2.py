#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.gui2.complete2 import LineEdit
from calibre.gui2.widgets import history

class HistoryLineEdit2(LineEdit):

    @property
    def store_name(self):
        return 'lineedit_history_'+self._name

    def initialize(self, name):
        self._name = name
        self.history = history.get(self.store_name, [])
        self.set_separator(None)
        self.update_items_cache(self.history)
        self.setText('')
        self.editingFinished.connect(self.save_history)

    def save_history(self):
        ct = unicode(self.text())
        if len(ct) > 2:
            try:
                self.history.remove(ct)
            except ValueError:
                pass
            self.history.insert(0, ct)
            history.set(self.store_name, self.history)
            self.update_items_cache(self.history)

