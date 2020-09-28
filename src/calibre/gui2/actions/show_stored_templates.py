#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.actions import InterfaceAction
from calibre.gui2.preferences.main import Preferences


class ShowStoredTemplatesAction(InterfaceAction):

    name = 'Stored Template'
    action_spec = (_('Stored Templates'), 'debug.png', None, ())
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'

    def genesis(self):
        self.previous_text = _('Manage stored templates')
        self.first_time = True
        self.qaction.triggered.connect(self.show_template_editor)

    def show_template_editor(self, *args):
        d = Preferences(self.gui, initial_plugin=('Advanced', 'StoredTemplates'),
                close_after_initial=True)
        d.exec_()

