#!/usr/bin/env  python2
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import (
    QDialog, Qt, QIcon, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QDialogButtonBox
)

from calibre import confirm_config_name
from calibre.gui2 import dynamic
from calibre.gui2.dialogs.message_box import Icon


class Dialog(QDialog):

    def __init__(self, msg, name, parent, config_set=dynamic, icon='dialog_warning.png',
                 title=None, confirm_msg=None, show_cancel_button=True):
        QDialog.__init__(self, parent)
        self.setWindowTitle(title or _("Are you sure?"))
        self.setWindowIcon(QIcon(I(icon)))
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        l.addLayout(h)

        self.icon_widget = Icon(self)
        self.icon_widget.set_icon(QIcon(I(icon)))

        self.msg = m = QLabel(self)
        m.setOpenExternalLinks(True)
        m.setMinimumWidth(350), m.setWordWrap(True), m.setObjectName("msg")
        m.setText(msg)

        h.addWidget(self.icon_widget), h.addSpacing(10), h.addWidget(m)

        self.again = a = QCheckBox((confirm_msg or _("&Show this warning again")), self)
        a.setChecked(True), a.setObjectName("again")
        a.stateChanged.connect(self.toggle)
        l.addWidget(a)

        buttons = QDialogButtonBox.Ok
        if show_cancel_button:
            buttons |= QDialogButtonBox.Cancel
        self.buttonBox = bb = QDialogButtonBox(buttons, self)
        bb.setObjectName("buttonBox")
        bb.setFocus(Qt.OtherFocusReason)
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        l.addWidget(bb)

        self.name = name
        self.config_set = config_set

        self.resize(self.sizeHint())

    def toggle(self, *args):
        self.config_set[confirm_config_name(self.name)] = self.again.isChecked()


def confirm(msg, name, parent=None, pixmap='dialog_warning.png', title=None,
        show_cancel_button=True, confirm_msg=None, config_set=None):
    config_set = config_set or dynamic
    if not config_set.get(confirm_config_name(name), True):
        return True
    d = Dialog(msg, name, parent, config_set=config_set, icon=pixmap,
               title=title, confirm_msg=confirm_msg, show_cancel_button=show_cancel_button)
    return d.exec_() == d.Accepted
