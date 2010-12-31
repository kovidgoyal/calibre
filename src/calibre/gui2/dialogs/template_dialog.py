#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt4.Qt import Qt, QDialog, QDialogButtonBox
from calibre.gui2.dialogs.template_dialog_ui import Ui_TemplateDialog

class TemplateDialog(QDialog, Ui_TemplateDialog):

    def __init__(self, parent, text):
        QDialog.__init__(self, parent)
        Ui_TemplateDialog.__init__(self)
        self.setupUi(self)
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        if text is not None:
            self.textbox.setPlainText(text)
        self.textbox.setTabStopWidth(50)
        self.buttonBox.button(QDialogButtonBox.Ok).setText(_('&OK'))
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(_('&Cancel'))

