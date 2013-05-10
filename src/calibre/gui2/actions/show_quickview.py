#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.quickview import Quickview
from calibre.gui2 import error_dialog

class ShowQuickviewAction(InterfaceAction):

    name = 'Show quickview'
    action_spec = (_('Show quickview'), 'search.png', None, _('Q'))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    current_instance = None

    def genesis(self):
        self.qaction.triggered.connect(self.show_quickview)

    def show_quickview(self, *args):
        if self.current_instance:
            if not self.current_instance.is_closed:
                return
            self.current_instance = None
        if self.gui.current_view() is not self.gui.library_view:
            error_dialog(self.gui, _('No quickview available'),
                _('Quickview is not available for books '
                  'on the device.')).exec_()
            return
        index = self.gui.library_view.currentIndex()
        if index.isValid():
            self.current_instance = \
                Quickview(self.gui, self.gui.library_view, index)
            self.current_instance.show()

    def change_quickview_column(self, idx):
        self.show_quickview()
        if self.current_instance:
            if self.current_instance.is_closed:
                return
            self.current_instance.change_quickview_column.emit(idx)

    def library_changed(self, db):
        if self.current_instance and not self.current_instance.is_closed:
            self.current_instance.set_database(db)
