#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QToolButton, QAction, QIcon

from calibre.customize import InterfaceActionBase
from calibre.gui2 import Dispatcher

class InterfaceAction(InterfaceActionBase):

    supported_platforms = ['windows', 'osx', 'linux']
    author         = 'Kovid Goyal'
    type = _('User Interface Action')

    positions = frozenset([])
    separators = frozenset([])

    popup_type = QToolButton.MenuPopup

    #: Of the form: (text, icon_path, tooltip, keyboard shortcut)
    #: tooltip and keybard shortcut can be None
    #: shortcut must be a translated string if not None
    action_spec = ('text', 'icon', None, None)

    def do_genesis(self, gui):
        self.gui = gui
        self.Dispatcher = partial(Dispatcher, parent=gui)
        self.create_action()
        self.genesis()

    def create_action(self):
        text, icon, tooltip, shortcut = self.action_spec
        action = QAction(QIcon(I(icon)), text, self)
        text = tooltip if tooltip else text
        action.setToolTip(text)
        action.setStatusTip(text)
        action.setWhatsThis(text)
        action.setAutoRepeat(False)
        if shortcut:
            action.setShortcut(shortcut)
        self.qaction = action

    def genesis(self):
        pass

