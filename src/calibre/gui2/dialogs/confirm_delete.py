#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

from qt.core import (
    QDialog, Qt, QIcon, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QDialogButtonBox
)

from calibre import confirm_config_name
from calibre.gui2 import dynamic
from calibre.gui2.dialogs.message_box import Icon


class Dialog(QDialog):

    def __init__(self, msg, name, parent, config_set=dynamic, icon='dialog_warning.png',
                 title=None, confirm_msg=None, show_cancel_button=True, extra_button=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(title or _("Are you sure?"))
        self.setWindowIcon(QIcon.ic(icon))
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        l.addLayout(h)

        self.icon_widget = Icon(self)
        self.icon_widget.set_icon(QIcon.ic(icon))

        self.msg = m = QLabel(self)
        m.setOpenExternalLinks(True)
        m.setMinimumWidth(350), m.setWordWrap(True), m.setObjectName("msg")
        m.setText(msg)

        h.addWidget(self.icon_widget), h.addSpacing(10), h.addWidget(m)

        self.again = a = QCheckBox((confirm_msg or _("&Show this warning again")), self)
        a.setChecked(True), a.setObjectName("again")
        a.stateChanged.connect(self.toggle)
        l.addWidget(a)

        if show_cancel_button:
            buttons = QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
            standard_button = QDialogButtonBox.StandardButton.Yes
        else:
            buttons = QDialogButtonBox.StandardButton.Ok
            standard_button = QDialogButtonBox.StandardButton.Ok
        self.buttonBox = bb = QDialogButtonBox(buttons, self)
        bb.setObjectName("buttonBox")
        bb.setFocus(Qt.FocusReason.OtherFocusReason)
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        self.extra_button_clicked = False
        if extra_button:
            b = bb.addButton(extra_button, QDialogButtonBox.ButtonRole.AcceptRole)
            b.clicked.connect(self.on_extra_button_click)
        l.addWidget(bb)

        self.name = name
        self.config_set = config_set

        self.resize(self.sizeHint())
        bb.button(standard_button).setFocus(Qt.FocusReason.OtherFocusReason)

    def on_extra_button_click(self):
        self.extra_button_clicked = True

    def toggle(self, *args):
        self.config_set[confirm_config_name(self.name)] = self.again.isChecked()


def confirm(msg, name, parent=None, pixmap='dialog_warning.png', title=None,
        show_cancel_button=True, confirm_msg=None, config_set=None, extra_button=None):
    config_set = config_set or dynamic
    if not config_set.get(confirm_config_name(name), True):
        if extra_button:
            return True, False
        return True
    d = Dialog(msg, name, parent, config_set=config_set, icon=pixmap, extra_button=extra_button,
               title=title, confirm_msg=confirm_msg, show_cancel_button=show_cancel_button)
    ret = d.exec() == QDialog.DialogCode.Accepted
    if extra_button:
        ret = ret, d.extra_button_clicked
    return ret
