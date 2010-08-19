#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QMenu, QToolButton

from calibre.gui2.actions import InterfaceAction

class CopyToLibraryAction(InterfaceAction):

    name = 'Copy To Library'
    action_spec = (_('Copy to library'), 'lt.png',
            _('Copy selected books to the specified library'), None)
    popup_type = QToolButton.InstantPopup

    def genesis(self):
        self.menu = QMenu(self.gui)


