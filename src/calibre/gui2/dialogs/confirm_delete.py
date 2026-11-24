#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

from typing import TYPE_CHECKING, overload

from qt.core import QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QIcon, QLabel, QMenu, Qt, QVBoxLayout

from calibre import confirm_config_name
from calibre.gui2 import dynamic
from calibre.gui2.dialogs.message_box import Icon
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Mapping

    from qt.core import QWidget

    from calibre.utils.config import DynamicConfig, XMLConfig


class Dialog(QDialog):
    def __init__(
        self,
        msg: str,
        name: str,
        parent: QWidget | None,
        config_set: DynamicConfig | XMLConfig = dynamic,
        icon: str = 'dialog_warning.png',
        title: str | None = None,
        confirm_msg: str | None = None,
        show_cancel_button: bool = True,
        extra_button: str | None = None,
        extra_button_choices: Mapping[str, str] | None = None,
    ) -> None:
        QDialog.__init__(self, parent)
        self.setWindowTitle(title or _('Are you sure?'))
        self.setWindowIcon(QIcon.ic(icon))
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        l.addLayout(h)

        self.icon_widget = Icon(self)
        self.icon_widget.set_icon(QIcon.ic(icon))

        self.msg = m = QLabel(self)
        m.setOpenExternalLinks(True)
        m.setMinimumWidth(350), m.setWordWrap(True), m.setObjectName('msg')
        m.setMaximumHeight(400)
        m.setText(msg)

        h.addWidget(self.icon_widget), h.addSpacing(10), h.addWidget(m)

        self.again = a = QCheckBox((confirm_msg or _('&Show this warning again')), self)
        a.setChecked(True), a.setObjectName('again')
        a.stateChanged.connect(self.toggle)
        l.addWidget(a)

        if show_cancel_button:
            buttons = QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
            standard_button = QDialogButtonBox.StandardButton.Yes
        else:
            buttons = QDialogButtonBox.StandardButton.Ok
            standard_button = QDialogButtonBox.StandardButton.Ok
        self.buttonBox = bb = QDialogButtonBox(buttons, self)
        bb.setObjectName('buttonBox')
        bb.setFocus(Qt.FocusReason.OtherFocusReason)
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        self.extra_button_clicked = False
        self.extra_button_choice = None
        if extra_button:
            b = bb.addButton(extra_button, QDialogButtonBox.ButtonRole.AcceptRole)
            assert b is not None
            if extra_button_choices:
                m = QMenu()
                b.setMenu(m)
                for acname, text in extra_button_choices.items():
                    ac = m.addAction(text)
                    assert ac is not None
                    ac.setObjectName(acname)
                    ac.triggered.connect(self.on_extra_choice_click)
            else:
                b.clicked.connect(self.on_extra_button_click)
        l.addWidget(bb)

        self.name = name
        self.config_set = config_set

        self.resize(self.sizeHint())
        standard_btn = bb.button(standard_button)
        assert standard_btn is not None
        standard_btn.setFocus(Qt.FocusReason.OtherFocusReason)

    def on_extra_button_click(self) -> None:
        self.extra_button_clicked = True

    def on_extra_choice_click(self) -> None:
        ac = self.sender()
        assert ac is not None
        self.extra_button_choice = ac.objectName()
        self.accept()

    def toggle(self, *args: object) -> None:
        self.config_set[confirm_config_name(self.name)] = self.again.isChecked()


@overload
def confirm(
    msg: str,
    name: str,
    parent: QWidget | None = None,
    pixmap: str = 'dialog_warning.png',
    title: str | None = None,
    show_cancel_button: bool = True,
    confirm_msg: str | None = None,
    config_set: DynamicConfig | XMLConfig | None = None,
    extra_button: None = None,
    extra_button_choices: None = None,
) -> bool: ...
@overload
def confirm(
    msg: str,
    name: str,
    parent: QWidget | None = None,
    pixmap: str = 'dialog_warning.png',
    title: str | None = None,
    show_cancel_button: bool = True,
    confirm_msg: str | None = None,
    config_set: DynamicConfig | XMLConfig | None = None,
    *,
    extra_button: str,
    extra_button_choices: Mapping[str, str],
) -> tuple[bool, str | None]: ...
@overload
def confirm(
    msg: str,
    name: str,
    parent: QWidget | None = None,
    pixmap: str = 'dialog_warning.png',
    title: str | None = None,
    show_cancel_button: bool = True,
    confirm_msg: str | None = None,
    config_set: DynamicConfig | XMLConfig | None = None,
    *,
    extra_button: str,
    extra_button_choices: None = None,
) -> tuple[bool, bool]: ...
def confirm(
    msg: str,
    name: str,
    parent: QWidget | None = None,
    pixmap: str = 'dialog_warning.png',
    title: str | None = None,
    show_cancel_button: bool = True,
    confirm_msg: str | None = None,
    config_set: DynamicConfig | XMLConfig | None = None,
    extra_button: str | None = None,
    extra_button_choices: Mapping[str, str] | None = None,
) -> bool | tuple[bool, str | None] | tuple[bool, bool]:
    config_set = config_set or dynamic
    if not config_set.get(confirm_config_name(name), True):
        if extra_button:
            if extra_button_choices:
                return True, None
            return True, False
        return True
    d = Dialog(
        msg,
        name,
        parent,
        config_set=config_set,
        icon=pixmap,
        extra_button=extra_button,
        title=title,
        confirm_msg=confirm_msg,
        show_cancel_button=show_cancel_button,
        extra_button_choices=extra_button_choices,
    )
    ret = d.exec() == QDialog.DialogCode.Accepted
    if extra_button:
        if extra_button_choices:
            ret = ret, d.extra_button_choice
        else:
            ret = ret, d.extra_button_clicked
    return ret
