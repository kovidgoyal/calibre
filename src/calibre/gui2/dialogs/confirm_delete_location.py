#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net' \
                '2010, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from functools import partial

from calibre.gui2.dialogs.confirm_delete_location_ui import Ui_Dialog
from PyQt4.Qt import QDialog, Qt, QPixmap, QIcon

class Dialog(QDialog, Ui_Dialog):

    def __init__(self, msg, name, parent):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.loc = None
        self.msg.setText(msg)
        self.name = name
        self.buttonBox.setFocus(Qt.OtherFocusReason)
        self.button_lib.clicked.connect(partial(self.set_loc, 'lib'))
        self.button_device.clicked.connect(partial(self.set_loc, 'dev'))
        self.button_both.clicked.connect(partial(self.set_loc, 'both'))

    def set_loc(self, loc):
        self.loc = loc
        self.accept()

    def choice(self):
        return self.loc
        

def confirm_location(msg, name, parent=None, pixmap='dialog_warning.png'):
    d = Dialog(msg, name, parent)
    d.label.setPixmap(QPixmap(I(pixmap)))
    d.setWindowIcon(QIcon(I(pixmap)))
    d.resize(d.sizeHint())
    if d.exec_() == d.Accepted:
        return d.choice()
    return None
