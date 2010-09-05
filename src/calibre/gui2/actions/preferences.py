#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QIcon, QMenu

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.preferences.main import Preferences
from calibre.gui2 import error_dialog

class PreferencesAction(InterfaceAction):

    name = 'Preferences'
    action_spec = (_('Preferences'), 'config.png', None, _('Ctrl+P'))
    dont_remove_from = frozenset(['toolbar'])

    def genesis(self):
        pm = QMenu()
        pm.addAction(QIcon(I('config.png')), _('Preferences'), self.do_config)
        pm.addAction(QIcon(I('wizard.png')), _('Run welcome wizard'),
                self.gui.run_wizard)
        self.qaction.setMenu(pm)
        self.preferences_menu = pm
        for x in (self.gui.preferences_action, self.qaction):
            x.triggered.connect(self.do_config)


    def do_config(self, checked=False, initial_plugin=None):
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
        d = Preferences(self.gui, initial_plugin=initial_plugin)
        d.show()

        if d.committed:
            self.gui.must_restart_before_config = d.must_restart
            self.gui.tags_view.set_new_model() # in case columns changed
            self.gui.tags_view.recount()
            self.gui.create_device_menu()
            self.gui.set_device_menu_items_state(bool(self.gui.device_connected))
            self.gui.tool_bar.build_bar()
            self.gui.build_context_menus()
            self.gui.tool_bar.apply_settings()



