#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.actions import InterfaceAction

class ChooseLibraryAction(InterfaceAction):

    name = 'Choose Library'
    action_spec = (_('%d books')%0, 'lt.png',
            _('Choose calibre library to work with'), None)

    def genesis(self):
        pass

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.qaction.triggered.connect(self.choose_library)

    def count_changed(self, new_count):
        text = self.action_spec[0]%new_count
        a = self.qaction
        a.setText(text)
        tooltip = self.action_spec[2] + '\n\n' + text
        a.setToolTip(tooltip)
        a.setStatusTip(tooltip)
        a.setWhatsThis(tooltip)

    def choose_library(self, *args):
        from calibre.gui2.dialogs.choose_library import ChooseLibrary
        db = self.gui.library_view.model().db
        c = ChooseLibrary(db, self.gui.library_moved, self.gui)
        c.exec_()


