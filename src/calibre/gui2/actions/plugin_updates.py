#!/usr/bin/env python
# License: GPLv3 Copyright: 2011, Grant Drake <grant.drake@gmail.com>

from qt.core import QApplication, QIcon, Qt

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.plugin_updater import FILTER_ALL, FILTER_UPDATE_AVAILABLE, PluginUpdaterDialog
from calibre.utils.localization import _


class PluginUpdaterAction(InterfaceAction):
    name = 'Plugin Updater'
    action_spec = (_('Plugin updater'), None, _('Update any plugins you have installed in calibre'), ())
    action_type = 'current'

    def genesis(self):
        self.qaction.setIcon(QIcon.ic('plugins/plugin_updater.png'))
        self.qaction.triggered.connect(self.check_for_plugin_updates)

    def check_for_plugin_updates(self):
        # Get the user to choose a plugin to install
        initial_filter = FILTER_UPDATE_AVAILABLE
        mods = QApplication.keyboardModifiers()
        if mods & Qt.KeyboardModifier.ControlModifier or mods & Qt.KeyboardModifier.ShiftModifier:
            initial_filter = FILTER_ALL

        d = PluginUpdaterDialog(self.gui, initial_filter=initial_filter)
        d.exec()
        if d.do_restart:
            self.gui.quit(restart=True)
