#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import QAction

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.quickview import Quickview
from calibre.gui2 import error_dialog


class ShowQuickviewAction(InterfaceAction):

    name = 'Show Quickview'
    action_spec = (_('Show Quickview'), 'search.png', None, _('Q'))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    current_instance = None

    def genesis(self):
        self.qaction.triggered.connect(self.show_quickview)

        self.focus_action = QAction(self.gui)
        self.gui.addAction(self.focus_action)
        self.gui.keyboard.register_shortcut('Focus To Quickview', _('Focus to Quickview'),
                     description=_('Move the focus to the Quickview panel/window'),
                     default_keys=('Shift+Q',), action=self.focus_action,
                     group=self.action_spec[0])
        self.focus_action.triggered.connect(self.focus_quickview)

        self.search_action = QAction(self.gui)
        self.gui.addAction(self.search_action)
        self.gui.keyboard.register_shortcut('Search from Quickview', _('Search from Quickview'),
                     description=_('Search for the currently selected Quickview item'),
                     default_keys=('Shift+S',), action=self.search_action,
                     group=self.action_spec[0])
        self.search_action.triggered.connect(self.search_quickview)
        self.search_action.changed.connect(self.set_search_shortcut)
        self.menuless_qaction.changed.connect(self.set_search_shortcut)

    def show_quickview(self, *args):
        if self.current_instance:
            if not self.current_instance.is_closed:
                self.current_instance.reject()
                self.current_instance = None
                return
            self.current_instance = None
        if self.gui.current_view() is not self.gui.library_view:
            error_dialog(self.gui, _('No quickview available'),
                _('Quickview is not available for books '
                  'on the device.')).exec_()
            return
        index = self.gui.library_view.currentIndex()
        if index.isValid():
            self.current_instance = Quickview(self.gui, index)
            self.current_instance.reopen_quickview.connect(self.reopen_quickview)
            self.set_search_shortcut()
            self.current_instance.show()

    def set_search_shortcut(self):
        if self.current_instance and not self.current_instance.is_closed:
            self.current_instance.set_shortcuts(self.search_action.shortcut().toString(),
                                                self.menuless_qaction.shortcut().toString())

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

    def search_quickview(self):
        if not self.current_instance or self.current_instance.is_closed:
            return
        self.current_instance.do_search()
