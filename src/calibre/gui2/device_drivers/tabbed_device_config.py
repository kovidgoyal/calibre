#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import textwrap
import weakref
from typing import TYPE_CHECKING

from qt.core import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSpacerItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2.device_drivers.mtp_config import FormatsConfig, TemplateConfig
from calibre.prints import debug_print
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from calibre.devices.usbms.device import Device as UsbmsDevice
    from calibre.utils.config_base import ConfigProxy, OptionValues


def wrap_msg(msg: str) -> str:
    return textwrap.fill(msg.strip(), 100)


def setToolTipFor(widget: QWidget, tt: str) -> None:
    widget.setToolTip(wrap_msg(tt))


def create_checkbox(title: str, tt: str, state: object) -> QCheckBox:
    cb = QCheckBox(title)
    cb.setToolTip(wrap_msg(tt))
    cb.setChecked(bool(state))
    return cb


class TabbedDeviceConfig(QTabWidget):
    '''
    This is a generic Tabbed Device config widget. It designed for devices with more
    complex configuration. But, it is backwards compatible to the standard device
    configuration widget.

    The configuration made up of two default tabs plus extra tabs as needed for the
    device. The extra tabs are defined as part of the subclass of this widget for
    the device.

    The two default tabs are the "File Formats" and "Extra Customization". These
    tabs are the same as the two sections of the standard device configuration
    widget. The second of these tabs will only be created if the device driver has
    extra configuration options. All options on these tabs work the same way as for
    the standard device configuration widget.

    When implementing a subclass for a device driver, create tabs, subclassed from
    DeviceConfigTab, for each set of options. Within the tabs, group boxes, subclassed
    from DeviceOptionsGroupBox, are created to further group the options. The group
    boxes can be coded to support any control type and dependencies between them.

    Set validate_before_accept to True if you want validate() to be called
    when OK is pressed
    '''

    def __init__(
        self,
        device_settings: OptionValues,
        all_formats: Iterable[str],
        supports_subdirs: bool,
        must_read_metadata: bool,
        supports_use_author_sort: bool,
        extra_customization_message: str | list[str] | None,
        device: type[UsbmsDevice],
        extra_customization_choices: Mapping[int, Iterable[str]] | None = None,
        parent: QWidget | None = None,
        validate_before_accept: bool = False,
    ) -> None:
        QTabWidget.__init__(self, parent)
        self._device = weakref.ref(device)

        self.validate_before_accept = validate_before_accept
        self.device_settings = device_settings
        self.all_formats = set(all_formats)
        self.supports_subdirs = supports_subdirs
        self.must_read_metadata = must_read_metadata
        self.supports_use_author_sort = supports_use_author_sort
        self.extra_customization_message = extra_customization_message
        self.extra_customization_choices = extra_customization_choices

        try:
            self.device_name = device.get_gui_name()
        except TypeError:
            self.device_name = getattr(device, 'gui_name', None) or _('Device')

        if device.USER_CAN_ADD_NEW_FORMATS:
            self.all_formats = set(self.all_formats) | set(BOOK_EXTENSIONS)

        self.base = QWidget(self)
        # self.insertTab(0, self.base, _('Configure %s') % self.device.current_friendly_name)
        self.insertTab(0, self.base, _('File formats'))
        l = QGridLayout(self.base)
        self.base.setLayout(l)

        self.formats = FormatsConfig(self.all_formats, device_settings.format_map)
        if device.HIDE_FORMATS_CONFIG_BOX:
            self.formats.hide()

        self.opt_use_subdirs = create_checkbox(
            _('Use sub-folders'),
            _('Place files in sub-folders if the device supports them'),
            device_settings.use_subdirs,
        )
        self.opt_read_metadata = create_checkbox(
            _('Read metadata from files on device'),
            _('Read metadata from files on device'),
            device_settings.read_metadata,
        )

        self.template = TemplateConfig(device_settings.save_template)
        self.opt_use_author_sort = create_checkbox(_('Use author sort for author'), _('Use author sort for author'), device_settings.read_metadata)
        self.opt_use_author_sort.setObjectName('opt_use_author_sort')
        la = QLabel(_('Choose the formats to send to the %s') % self.device_name)
        la.setWordWrap(True)

        l.addWidget(la, 1, 0, 1, 1)
        l.addWidget(self.formats, 2, 0, 1, 1)
        l.addWidget(self.opt_read_metadata, 3, 0, 1, 1)
        l.addWidget(self.opt_use_subdirs, 4, 0, 1, 1)
        l.addWidget(self.opt_use_author_sort, 5, 0, 1, 1)
        l.addWidget(self.template, 6, 0, 1, 1)
        l.setRowStretch(2, 10)

        if device.HIDE_FORMATS_CONFIG_BOX:
            self.formats.hide()

        if supports_subdirs:
            self.opt_use_subdirs.setChecked(device_settings.use_subdirs)
        else:
            self.opt_use_subdirs.hide()
        if not must_read_metadata:
            self.opt_read_metadata.setChecked(device_settings.read_metadata)
        else:
            self.opt_read_metadata.hide()
        if supports_use_author_sort:
            self.opt_use_author_sort.setChecked(device_settings.use_author_sort)
        else:
            self.opt_use_author_sort.hide()

        self.extra_tab = ExtraCustomization(self.extra_customization_message, self.extra_customization_choices, self.device_settings)
        # Only display the extra customization tab if there are options on it.
        if self.extra_tab.has_extra_customizations:
            self.addTab(self.extra_tab, _('Extra customization'))

        self.setCurrentIndex(0)

    def addDeviceTab(self, tab: QWidget, label: str) -> None:
        '''
        This is used to add a new tab for the device config. The new tab will always be added
        as immediately before the "Extra Customization" tab.
        '''
        extra_tab_pos = self.indexOf(self.extra_tab)
        self.insertTab(extra_tab_pos, tab, label)

    def __getattr__(self, attr_name: str) -> object:
        "If the object doesn't have an attribute, then check each tab."
        for i in range(self.count()):
            atab = self.widget(i)
            try:
                return getattr(atab, attr_name)
            except AttributeError:
                pass
        raise AttributeError(attr_name)

    @property
    def device(self) -> type[UsbmsDevice]:
        ans = self._device()
        assert ans is not None
        return ans

    def format_map(self) -> list[str]:
        return self.formats.format_map

    def use_subdirs(self) -> bool:
        return self.opt_use_subdirs.isChecked()

    def read_metadata(self) -> bool:
        return self.opt_read_metadata.isChecked()

    def use_author_sort(self) -> bool:
        return self.opt_use_author_sort.isChecked()

    @property
    def opt_save_template(self) -> QLineEdit:
        # Really shouldn't be accessing the template this way
        return self.template.t

    def text(self) -> str:
        # Really shouldn't be accessing the template this way
        return self.template.t.text()

    @property
    def opt_extra_customization(self) -> list[QCheckBox | QComboBox | QLineEdit | None] | QLineEdit:
        return self.extra_tab.opt_extra_customization

    @property
    def label(self) -> QLineEdit:
        return self.opt_save_template

    def validate(self) -> bool:
        if hasattr(self, 'formats'):
            if not self.formats.validate():
                return False
            if not self.template.validate():
                return False
        return True

    def commit(self) -> ConfigProxy:
        debug_print('TabbedDeviceConfig::commit: start')
        p = self.device._configProxy()

        p['format_map'] = self.formats.format_map
        p['use_subdirs'] = self.use_subdirs()
        p['read_metadata'] = self.read_metadata()
        p['save_template'] = self.template.template
        p['extra_customization'] = self.extra_tab.extra_customization()

        return p


class DeviceConfigTab(QWidget):  # {{{
    """
    This is an abstraction for a tab in the configuration. The main reason for it is to
    abstract the properties of the configuration tab. When a property is accessed, it
    will iterate over all known widgets looking for the property.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        QWidget.__init__(self)
        self.device_widgets: list[QWidget] = []

    def addDeviceWidget(self, widget: QWidget) -> None:
        self.device_widgets.append(widget)

    def __getattr__(self, attr_name: str) -> object:
        for awidget in self.device_widgets:
            try:
                return getattr(awidget, attr_name)
            except AttributeError:
                pass
        raise AttributeError(attr_name)


class ExtraCustomization(DeviceConfigTab):  # {{{
    opt_extra_customization: list[QCheckBox | QComboBox | QLineEdit | None] | QLineEdit

    def __init__(
        self,
        extra_customization_message: str | list[str] | None,
        extra_customization_choices: Mapping[int, Iterable[str]] | None,
        device_settings: OptionValues,
    ) -> None:
        super().__init__()

        debug_print('ExtraCustomization.__init__ - extra_customization_message=', extra_customization_message)
        debug_print('ExtraCustomization.__init__ - extra_customization_choices=', extra_customization_choices)
        debug_print('ExtraCustomization.__init__ - device_settings.extra_customization=', device_settings.extra_customization)
        debug_print('ExtraCustomization.__init__ - device_settings=', device_settings)
        self.extra_customization_message = extra_customization_message

        self.l = QVBoxLayout(self)
        self.setLayout(self.l)

        options_group = QGroupBox(_('Extra driver customization options'), self)
        self.l.addWidget(options_group)
        self.extra_layout = QGridLayout()
        self.extra_layout.setObjectName('extra_layout')
        options_group.setLayout(self.extra_layout)

        if extra_customization_message:
            extra_customization_choices = extra_customization_choices or {}

            def parse_msg(m: str) -> tuple[str, str]:
                msg, _, tt = m.partition(':::') if m else ('', '', '')
                return msg.strip(), textwrap.fill(tt.strip(), 100)

            if isinstance(extra_customization_message, list):
                self.opt_extra_customization = []
                if len(extra_customization_message) > 6:

                    def row_func(x: int, y: int) -> int:
                        return x // 2 * 2 + y

                    def col_func(x: int) -> int:
                        return x % 2

                else:

                    def row_func(x: int, y: int) -> int:
                        return x * 2 + y

                    def col_func(x: int) -> int:
                        return 0

                for i, m in enumerate(extra_customization_message):
                    label_text, tt = parse_msg(m)
                    if not label_text:
                        self.opt_extra_customization.append(None)
                        continue
                    if isinstance(device_settings.extra_customization[i], bool):
                        _opt_item = QCheckBox(label_text)
                        self.opt_extra_customization.append(_opt_item)
                        _opt_item.setToolTip(tt)
                        _opt_item.setChecked(bool(device_settings.extra_customization[i]))
                    elif i in extra_customization_choices:
                        cb = QComboBox(self)
                        self.opt_extra_customization.append(cb)
                        l = QLabel(label_text)
                        l.setToolTip(tt), cb.setToolTip(tt), l.setBuddy(cb), cb.setToolTip(tt)
                        for li in sorted(extra_customization_choices[i]):
                            cb.addItem(li)
                        cb.setCurrentIndex(max(0, cb.findText(device_settings.extra_customization[i])))
                    else:
                        _opt_line_item = QLineEdit(self)
                        self.opt_extra_customization.append(_opt_line_item)
                        l = QLabel(label_text)
                        l.setToolTip(tt)
                        _opt_line_item.setToolTip(tt)
                        l.setBuddy(_opt_line_item)
                        l.setWordWrap(True)
                        _opt_line_item.setText(device_settings.extra_customization[i])
                        _opt_line_item.setCursorPosition(0)
                        self.extra_layout.addWidget(l, row_func(i + 2, 0), col_func(i))
                    self.extra_layout.addWidget(self.opt_extra_customization[i], row_func(i + 2, 1), col_func(i))
                spacerItem1 = QSpacerItem(10, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
                self.extra_layout.addItem(spacerItem1, row_func(i + 2 + 2, 1), 0, 1, 2)
                self.extra_layout.setRowStretch(row_func(i + 2 + 2, 1), 2)
            else:
                self.opt_extra_customization = QLineEdit()
                label_text, tt = parse_msg(extra_customization_message)
                l = QLabel(label_text)
                l.setToolTip(tt)
                l.setBuddy(self.opt_extra_customization)
                l.setWordWrap(True)
                if device_settings.extra_customization:
                    self.opt_extra_customization.setText(device_settings.extra_customization)
                    self.opt_extra_customization.setCursorPosition(0)
                self.opt_extra_customization.setCursorPosition(0)
                self.extra_layout.addWidget(l, 0, 0)
                self.extra_layout.addWidget(self.opt_extra_customization, 1, 0)

    def extra_customization(self) -> list[bool | str | None] | str | None:
        ec: list[bool | str | None] | str | None = []
        if self.extra_customization_message:
            if isinstance(self.extra_customization_message, list):
                oec = self.opt_extra_customization
                assert isinstance(oec, list)
                for i in range(len(self.extra_customization_message)):
                    if oec[i] is None:
                        ec.append(None)
                        continue
                    _ec_item = oec[i]
                    assert _ec_item is not None
                    if isinstance(_ec_item, QCheckBox):
                        ec.append(_ec_item.isChecked())
                    elif isinstance(_ec_item, QComboBox):
                        ec.append(str(_ec_item.currentText()).strip())
                    elif isinstance(_ec_item, QLineEdit):
                        ec.append(str(_ec_item.text()).strip())
            else:
                oec = self.opt_extra_customization
                assert isinstance(oec, QLineEdit)
                ec = str(oec.text()).strip()
                if not ec:
                    ec = None

        return ec

    @property
    def has_extra_customizations(self) -> bool | str | list[str] | None:
        debug_print(
            'ExtraCustomization::has_extra_customizations - self.extra_customization_message',
            self.extra_customization_message,
        )
        return self.extra_customization_message and len(self.extra_customization_message) > 0


# }}}


class DeviceOptionsGroupBox(QGroupBox):
    """
    This is a container for the individual options for a device driver.
    """

    def __init__(self, parent: QWidget | None, device: type[UsbmsDevice] | None = None, title: str = _('Unknown')) -> None:
        QGroupBox.__init__(self, parent)

        self.device = device
        self.setTitle(title)


if __name__ == '__main__':
    from calibre.devices.kobo.driver import KOBO
    from calibre.devices.scanner import DeviceScanner
    from calibre.gui2 import Application

    s = DeviceScanner()
    s.scan()
    app = Application([])
    dev = KOBO(None)
    debug_print('KOBO:', KOBO)
    # dev.startup()
    # cd = dev.detect_managed_devices(s.devices)
    # dev.open(cd, 'test')
    cw = dev.config_widget()
    d = QDialog()
    dl = QVBoxLayout()
    d.setLayout(dl)
    dl.addWidget(cw)
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    dl.addWidget(bb)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    if d.exec() == QDialog.DialogCode.Accepted:
        cw.commit()
    dev.shutdown()
