__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.QtGui import QDialog, QListWidgetItem

from libprs500.gui2 import file_icon_provider
from libprs500.gui2.dialogs.choose_format_ui import Ui_ChooseFormatDialog

class ChooseFormatDialog(QDialog, Ui_ChooseFormatDialog):
    
    def __init__(self, window, msg, formats):
        QDialog.__init__(self, window)
        Ui_ChooseFormatDialog.__init__(self)
        self.setupUi(self)
        
        self.msg.setText(msg)
        for format in formats:
            self.formats.addItem(QListWidgetItem(file_icon_provider().icon_from_ext(format.lower()),
                                                 format.upper()))
        self._formats = formats
        self.formats.setCurrentRow(0)
        
    def format(self):
        return self._formats[self.formats.currentRow()]
    
    