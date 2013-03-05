#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QApplication, Qt, QIcon
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.plugin_updater import (PluginUpdaterDialog,
                                                 FILTER_ALL, FILTER_UPDATE_AVAILABLE)

class PluginUpdaterAction(InterfaceAction):

    name = 'Plugin Updater'
    action_spec = (_('Plugin Updater'), None, _('Update any plugins you have installed in calibre'), ())
    action_type = 'current'

    def genesis(self):
        self.qaction.setIcon(QIcon(I('plugins/plugin_updater.png')))
        self.qaction.triggered.connect(self.check_for_plugin_updates)

    def check_for_plugin_updates(self):
        # Get the user to choose a plugin to install
        initial_filter = FILTER_UPDATE_AVAILABLE
        mods = QApplication.keyboardModifiers()
        if mods & Qt.ControlModifier or mods & Qt.ShiftModifier:
            initial_filter = FILTER_ALL

        d = PluginUpdaterDialog(self.gui, initial_filter=initial_filter)
        d.exec_()
        if d.do_restart:
            self.gui.quit(restart=True)
