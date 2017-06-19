#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QVBoxLayout

from calibre.gui2.preferences import (ConfigWidgetBase, test_widget)
from calibre.gui2.keyboard import ShortcutConfig


class ConfigWidget(ConfigWidgetBase):

    def genesis(self, gui):
        self.gui = gui
        self.conf_widget = ShortcutConfig(self)
        self.conf_widget.changed_signal.connect(self.changed_signal)
        self._layout = l = QVBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)
        self.setLayout(l)
        l.addWidget(self.conf_widget)

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.conf_widget.initialize(self.gui.keyboard)

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.conf_widget.restore_defaults()

    def commit(self):
        self.conf_widget.commit()
        return ConfigWidgetBase.commit(self)

    def refresh_gui(self, gui):
        gui.keyboard.finalize()

    def highlight_group(self, group_name):
        self.conf_widget.highlight_group(group_name)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Advanced', 'Keyboard')
