#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt4.Qt import QDialog
from calibre.gui2.dialogs.comments_dialog_ui import Ui_CommentsDialog

class CommentsDialog(QDialog, Ui_CommentsDialog):

    def __init__(self, parent, text):
        QDialog.__init__(self, parent)
        Ui_CommentsDialog.__init__(self)
        self.setupUi(self)
        if text is not None:
            self.textbox.setPlainText(text)
        self.textbox.setTabChangesFocus(True)
