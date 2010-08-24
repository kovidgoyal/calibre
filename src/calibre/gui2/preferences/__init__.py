#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget, pyqtSignal

class PreferenceWidget(QWidget):

    category = None
    name     = None

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.has_changed = False
        self.changed.connect(lambda : setattr(self, 'has_changed', True))
        self.setupUi(self)

    def genesis(self, gui):
        raise NotImplementedError()

    def reset_to_defaults(self):
        pass

    def commit(self):
        pass

    def add_boolean(self, widget_name, preference_interface, pref_name):
        pass
