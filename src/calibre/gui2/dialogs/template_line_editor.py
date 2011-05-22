#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (SIGNAL, QLineEdit)
from calibre.gui2.dialogs.template_dialog import TemplateDialog

class TemplateLineEditor(QLineEdit):

    '''
    Extend the context menu of a QLineEdit to include more actions.
    '''

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        action_open_editor = menu.addAction(_('Open Editor'))

        self.connect(action_open_editor, SIGNAL('triggered()'), self.open_editor)
        menu.exec_(event.globalPos())

    def open_editor(self):
        t = TemplateDialog(self, self.text())
        if t.exec_():
            self.setText(t.textbox.toPlainText())


