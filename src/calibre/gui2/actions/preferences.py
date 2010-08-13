#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QIcon, QMenu

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.config import ConfigDialog
from calibre.gui2 import error_dialog, config

class PreferencesAction(InterfaceAction):

    name = 'Preferences'
    action_spec = (_('Preferences'), 'config.svg', None, _('Ctrl+P'))

    def genesis(self):
        pm = QMenu()
        pm.addAction(QIcon(I('config.svg')), _('Preferences'), self.do_config)
        pm.addAction(QIcon(I('wizard.svg')), _('Run welcome wizard'),
                self.gui.run_wizard)
        self.qaction.setMenu(pm)
        self.preferences_menu = pm
        for x in (self.gui.preferences_action, self.qaction):
            x.triggered.connect(self.do_config)


    def do_config(self, checked=False, initial_category='general'):
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
        d = ConfigDialog(self.gui, self.gui.library_view,
                server=self.gui.content_server, initial_category=initial_category)

        d.exec_()
        self.gui.content_server = d.server
        if self.gui.content_server is not None:
            self.gui.content_server.state_callback = \
                self.Dispatcher(self.gui.iactions['Connect Share'].content_server_state_changed)
            self.gui.content_server.state_callback(self.gui.content_server.is_running)

        if d.result() == d.Accepted:
            self.gui.read_toolbar_settings()
            self.gui.search.search_as_you_type(config['search_as_you_type'])
            self.gui.tags_view.set_new_model() # in case columns changed
            self.gui.iactions['Save To Disk'].reread_prefs()
            self.gui.tags_view.recount()
            self.gui.create_device_menu()
            self.gui.set_device_menu_items_state(bool(self.gui.device_connected))
            self.gui.tool_bar.apply_settings()



