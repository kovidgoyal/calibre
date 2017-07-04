#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import QAction

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.quickview import Quickview
from calibre.gui2 import error_dialog, gprefs
from calibre.gui2.widgets import LayoutButton


class QuickviewButton(LayoutButton):  # {{{

    def __init__(self, gui, quickview_manager):
        self.qv = quickview_manager
        qaction = quickview_manager.qaction
        LayoutButton.__init__(self, I('eye-quickview.png'), _('Quickview'),
                              parent=gui, shortcut=qaction.shortcut().toString())
        self.toggled.connect(self.update_state)
        self.action_toggle = qaction
        self.action_toggle.triggered.connect(self.toggle)
        self.action_toggle.changed.connect(self.update_shortcut)

    def update_state(self, checked):
        if checked:
            self.set_state_to_hide()
            self.qv._show_quickview()
        else:
            self.set_state_to_show()
            self.qv._hide_quickview()

    def save_state(self):
        gprefs['quickview visible'] = bool(self.isChecked())

    def restore_state(self):
        if gprefs.get('quickview visible', False):
            self.toggle()

# }}}


class ShowQuickviewAction(InterfaceAction):

    name = 'Show Quickview'
    action_spec = (_('Show Quickview'), 'eye-quickview.png', None, _('Q'))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    current_instance = None

    def genesis(self):
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
        self.qv_button = QuickviewButton(self.gui, self)

    def _hide_quickview(self):
        '''
        This is called only from the QV button toggle
        '''
        if self.current_instance:
            if not self.current_instance.is_closed:
                self.current_instance._reject()
            self.current_instance = None

    def _show_quickview(self, *args):
        '''
        This is called only from the QV button toggle
        '''
        if self.current_instance:
            if not self.current_instance.is_closed:
                self.current_instance._reject()
            self.current_instance = None
        if self.gui.current_view() is not self.gui.library_view:
            error_dialog(self.gui, _('No quickview available'),
                _('Quickview is not available for books '
                  'on the device.')).exec_()
            return
        self.qv_button.set_state_to_hide()
        index = self.gui.library_view.currentIndex()
        self.current_instance = Quickview(self.gui, index)
        self.current_instance.reopen_after_dock_change.connect(self.open_quickview)
        self.set_search_shortcut()
        self.current_instance.show()
        self.current_instance.quickview_closed.connect(self.qv_button.set_state_to_show)

    def set_search_shortcut(self):
        if self.current_instance and not self.current_instance.is_closed:
            self.current_instance.set_shortcuts(self.search_action.shortcut().toString(),
                                                self.menuless_qaction.shortcut().toString())

    def open_quickview(self):
        '''
        QV moved from/to dock. Close and reopen the pane/window.
        Also called when QV is closed and the user asks to move the focus
        '''
        if self.current_instance and not self.current_instance.is_closed:
            self.current_instance.reject()
        self.current_instance = None
        self.qaction.triggered.emit()

    def refill_quickview(self):
        '''
        Called when the data or the columns shown in the QV pane might have changed.
        '''
        if self.current_instance and not self.current_instance.is_closed:
            self.current_instance.refill()

    def change_quickview_column(self, idx):
        '''
        Called from the column header context menu to change the QV query column
        '''
        self.focus_quickview()
        self.current_instance.slave(idx)

    def library_changed(self, db):
        '''
        If QV is open, close it then reopen it so the columns are correct
        '''
        if self.current_instance and not self.current_instance.is_closed:
            self.current_instance.reject()
            self.qaction.triggered.emit()

    def focus_quickview(self):
        '''
        Used to move the focus to the QV books table. Open QV if needed
        '''
        if not self.current_instance or self.current_instance.is_closed:
            self.open_quickview()
        else:
            self.current_instance.set_focus()

    def search_quickview(self):
        if not self.current_instance or self.current_instance.is_closed:
            return
        self.current_instance.do_search()
