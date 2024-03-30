#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net' \
                '2010, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from qt.core import QDialog, QHBoxLayout, QIcon, QLabel, QPushButton, QSizePolicy, Qt, QVBoxLayout

from calibre.startup import connect_lambda


class Dialog(QDialog):

    def __init__(self, msg, name, parent, icon='dialog_warning.png'):
        super().__init__(parent)
        ic = QIcon.ic(icon)
        self.setWindowIcon(ic)
        self.l = l = QVBoxLayout(self)
        h = QHBoxLayout()
        la = QLabel(self)
        sp = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        sp.setHorizontalStretch(0), sp.setVerticalStretch(0)
        sp.setHeightForWidth(la.sizePolicy().hasHeightForWidth())
        la.setSizePolicy(sp)
        la.setPixmap(ic.pixmap(ic.availableSizes()[0]))
        h.addWidget(la)
        la = QLabel(msg)
        h.addWidget(la)
        la.setWordWrap(True)
        l.addLayout(h)
        h = QHBoxLayout()
        l.addLayout(h)
        self.button_lib = b = QPushButton(QIcon.ic('lt.png'), _('&Library'), self)
        h.addWidget(b)
        self.button_device = b = QPushButton(QIcon.ic('reader.png'), _('&Device'), self)
        h.addWidget(b)
        self.button_both = b = QPushButton(QIcon.ic('trash.png'), _('Library &and device'), self)
        h.addWidget(b)
        h.addStretch(10)
        self.button_cancel = b = QPushButton(QIcon.ic('window-close.png'), _('&Cancel'), self)
        h.addWidget(b)

        self.loc = None
        self.name = name
        self.button_cancel.setFocus(Qt.FocusReason.OtherFocusReason)
        connect_lambda(self.button_lib.clicked, self, lambda self: self.set_loc('lib'))
        connect_lambda(self.button_device.clicked, self, lambda self: self.set_loc('dev'))
        connect_lambda(self.button_both.clicked, self, lambda self: self.set_loc('both'))
        connect_lambda(self.button_cancel.clicked, self, lambda self: self.reject())
        self.resize(self.sizeHint())

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
    d = Dialog(msg, name, parent, icon=pixmap)
    ret = d.exec()
    d.break_cycles()
    return d.choice() if ret == QDialog.DialogCode.Accepted else None


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    confirm_location('testing this dialog', 'test dialog')
