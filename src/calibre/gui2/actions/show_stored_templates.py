#!/usr/bin/env python
# License: GPLv3 Copyright: 2020, Charles Haley

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.preferences.main import Preferences


class ShowTemplateFunctionsAction(InterfaceAction):

    name = 'Template Functions'
    action_spec = (_('Template functions'), 'debug.png', None, ())
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'

    def genesis(self):
        self.previous_text = _('Manage template functions')
        self.first_time = True
        self.qaction.triggered.connect(self.show_template_editor)

    def show_template_editor(self, *args):
        d = Preferences(self.gui, initial_plugin=('Advanced', 'TemplateFunctions'),
                close_after_initial=True)
        d.exec()
