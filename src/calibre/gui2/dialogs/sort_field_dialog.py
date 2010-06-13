#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt4.Qt import QDialog
from calibre.gui2.dialogs.sort_field_dialog_ui import Ui_SortFieldDialog

class SortFieldDialog(QDialog, Ui_SortFieldDialog):

    def __init__(self, parent, text):
        QDialog.__init__(self, parent)
        Ui_SortFieldDialog.__init__(self)
        self.setupUi(self)
        if text is not None:
            self.textbox.setText(text)
