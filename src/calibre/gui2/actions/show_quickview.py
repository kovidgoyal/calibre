#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from calibre.utils.fonts.sfnt.glyf import ARGS_ARE_XY_VALUES

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.quickview import Quickview
from calibre.gui2 import error_dialog

class FocusToQuickviewAction(InterfaceAction):

    name = 'Focus To Quickview'
    action_spec = (_('Focus To Quickview'), 'search.png', None, ('Shift+Q'))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.focus_quickview)

    def focus_quickview(self, *args):
        from calibre.customize.ui import find_plugin
        qv = find_plugin('Show Quickview')
        if qv:
            qv.actual_plugin_.focus_quickview()


class FocusFromQuickviewAction(InterfaceAction):

    name = 'Focus From Quickview'
    action_spec = (_('Focus From Quickview'), 'search.png', None, ('Ctrl+Q'))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.focus_quickview)

    def focus_quickview(self, *args):
        self.gui.library_view.setFocus()

class ShowQuickviewAction(InterfaceAction):

    name = 'Show Quickview'
    action_spec = (_('Show Quickview'), 'search.png', None, (_('Q')))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    current_instance = None

    def genesis(self):
        self.qaction.triggered.connect(self.show_quickview)

    def show_quickview(self, *args):
        if self.current_instance:
            if not self.current_instance.is_closed:
                self.current_instance.reject()
            self.current_instance = None
            return
        if self.gui.current_view() is not self.gui.library_view:
            error_dialog(self.gui, _('No quickview available'),
                _('Quickview is not available for books '
                  'on the device.')).exec_()
            return
        index = self.gui.library_view.currentIndex()
        if index.isValid():
            self.current_instance = Quickview(self.gui, index)
            self.current_instance.reopen_quickview.connect(self.reopen_quickview)
            self.current_instance.show()

    def reopen_quickview(self):
        if self.current_instance and not self.current_instance.is_closed:
            self.current_instance.reject()
        self.current_instance = None
        self.show_quickview()

    def change_quickview_column(self, idx):
        self.show_quickview()
        if self.current_instance:
            if self.current_instance.is_closed:
                return
            self.current_instance.change_quickview_column.emit(idx)

    def library_changed(self, db):
        if self.current_instance and not self.current_instance.is_closed:
            self.current_instance.reject()

    def focus_quickview(self):
        if not (self.current_instance and not self.current_instance.is_closed):
            self.show_quickview()
        self.current_instance.set_focus()