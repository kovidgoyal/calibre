#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QToolButton, QAction, QIcon, QObject

from calibre.gui2 import Dispatcher

class InterfaceAction(QObject):

    name = 'Implement me'
    priority = 1
    positions = frozenset([])
    popup_type = QToolButton.MenuPopup

    #: Of the form: (text, icon_path, tooltip, keyboard shortcut)
    #: icon, tooltip and keybard shortcut can be None
    #: shortcut must be a translated string if not None
    action_spec = ('text', 'icon', None, None)

    def __init__(self, parent, site_customization):
        QObject.__init__(self, parent)
        self.setObjectName(self.name)
        self.gui = parent
        self.site_customization = site_customization

    def do_genesis(self):
        self.Dispatcher = partial(Dispatcher, parent=self)
        self.create_action()
        self.genesis()

    def create_action(self):
        text, icon, tooltip, shortcut = self.action_spec
        if icon is not None:
            action = QAction(QIcon(I(icon)), text, self.gui)
        else:
            action = QAction(text, self.gui)
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

    def location_selected(self, loc):
        pass

