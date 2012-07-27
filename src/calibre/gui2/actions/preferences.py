#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QIcon, Qt

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.preferences.main import Preferences
from calibre.gui2 import error_dialog
from calibre.constants import DEBUG, isosx

class PreferencesAction(InterfaceAction):

    name = 'Preferences'
    action_spec = (_('Preferences'), 'config.png', None, _('Ctrl+P'))
    action_add_menu = True
    action_menu_clone_qaction = _('Change calibre behavior')

    def genesis(self):
        pm = self.qaction.menu()
        cm = partial(self.create_menu_action, pm)
        if isosx:
            pm.addAction(QIcon(I('config.png')), _('Preferences'), self.do_config)
        cm('welcome wizard', _('Run welcome wizard'),
                icon='wizard.png', triggered=self.gui.run_wizard)
        cm('plugin updater', _('Get plugins to enhance calibre'),
                icon='plugins/plugin_updater.png', triggered=self.get_plugins)
        if not DEBUG:
            pm.addSeparator()
            cm('restart', _('Restart in debug mode'), icon='debug.png',
                    triggered=self.debug_restart, shortcut='Ctrl+Shift+R')

        self.preferences_menu = pm
        for x in (self.gui.preferences_action, self.qaction):
            x.triggered.connect(self.do_config)

    def get_plugins(self):
        from calibre.gui2.dialogs.plugin_updater import (PluginUpdaterDialog,
                FILTER_NOT_INSTALLED)
        d = PluginUpdaterDialog(self.gui,
                initial_filter=FILTER_NOT_INSTALLED)
        d.exec_()
        if d.do_restart:
            self.gui.quit(restart=True)

    def do_config(self, checked=False, initial_plugin=None,
            close_after_initial=False):
        if self.gui.job_manager.has_jobs():
            d = error_dialog(self.gui, _('Cannot configure'),
                    _('Cannot configure while there are running jobs.'))
            d.exec_()
            return
        if self.gui.must_restart_before_config:
            d = error_dialog(self.gui, _('Cannot configure'),
                    _('Cannot configure before calibre is restarted.'))
            d.exec_()
            return
        d = Preferences(self.gui, initial_plugin=initial_plugin,
                close_after_initial=close_after_initial)
        d.show()
        d.run_wizard_requested.connect(self.gui.run_wizard,
                type=Qt.QueuedConnection)

    def debug_restart(self, *args):
        self.gui.quit(restart=True, debug_on_restart=True)

