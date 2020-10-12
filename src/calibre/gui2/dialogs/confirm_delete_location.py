#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net' \
                '2010, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.dialogs.confirm_delete_location_ui import Ui_Dialog
from PyQt5.Qt import QDialog, Qt, QPixmap, QIcon


class Dialog(QDialog, Ui_Dialog):

    def __init__(self, msg, name, parent):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.loc = None
        self.msg.setText(msg)
        self.name = name
        self.buttonBox.setFocus(Qt.OtherFocusReason)
        connect_lambda(self.button_lib.clicked, self, lambda self: self.set_loc('lib'))
        connect_lambda(self.button_device.clicked, self, lambda self: self.set_loc('dev'))
        connect_lambda(self.button_both.clicked, self, lambda self: self.set_loc('both'))

    def set_loc(self, loc):
        self.loc = loc
        self.accept()

    def choice(self):
        return self.loc

    def break_cycles(self):
        for x in ('lib', 'device', 'both'):
            b = getattr(self, 'button_'+x)
            try:
                b.clicked.disconnect()
            except:
                pass


def confirm_location(msg, name, parent=None, pixmap='dialog_warning.png'):
    d = Dialog(msg, name, parent)
    d.label.setPixmap(QPixmap(I(pixmap)))
    d.setWindowIcon(QIcon(I(pixmap)))
    d.resize(d.sizeHint())
    ret = d.exec_()
    d.break_cycles()
    if ret == d.Accepted:
        return d.choice()
    return None
