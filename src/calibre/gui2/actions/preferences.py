#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QIcon, QMenu, Qt

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.preferences.main import Preferences
from calibre.gui2 import error_dialog
from calibre.constants import DEBUG, isosx

class PreferencesAction(InterfaceAction):

    name = 'Preferences'
    action_spec = (_('Preferences'), 'config.png', None, _('Ctrl+P'))

    def genesis(self):
        pm = QMenu()
        pm.addAction(QIcon(I('config.png')), _('Preferences'), self.do_config)
        if isosx:
            pm.addAction(QIcon(I('config.png')), _('Change calibre behavior'), self.do_config)
        pm.addAction(QIcon(I('wizard.png')), _('Run welcome wizard'),
                self.gui.run_wizard)
        if not DEBUG:
            pm.addSeparator()
            ac = pm.addAction(QIcon(I('debug.png')), _('Restart in debug mode'),
                self.debug_restart)
            ac.setShortcut('Ctrl+Shift+R')
            self.gui.addAction(ac)

        self.qaction.setMenu(pm)
        self.preferences_menu = pm
        for x in (self.gui.preferences_action, self.qaction):
            x.triggered.connect(self.do_config)


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

