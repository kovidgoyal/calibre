#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals,  # division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import weakref, textwrap

from PyQt5.Qt import (
    QWidget, QLabel, QTabWidget, QGridLayout, QLineEdit, QVBoxLayout,
    QGroupBox, QComboBox, QSizePolicy, QDialog, QDialogButtonBox, QCheckBox,
    QSpacerItem)

from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2.device_drivers.mtp_config import (FormatsConfig, TemplateConfig)
from calibre.devices.usbms.driver import debug_print


def wrap_msg(msg):
    return textwrap.fill(msg.strip(), 100)


def setToolTipFor(widget, tt):
    widget.setToolTip(wrap_msg(tt))


def create_checkbox(title, tt, state):
    cb = QCheckBox(title)
    cb.setToolTip(wrap_msg(tt))
    cb.setChecked(bool(state))
    return cb


class TabbedDeviceConfig(QTabWidget):
    """
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
    """

    def __init__(self, device_settings, all_formats, supports_subdirs,
                    must_read_metadata, supports_use_author_sort,
                    extra_customization_message, device,
                    extra_customization_choices=None, parent=None):
        QTabWidget.__init__(self, parent)
        self._device = weakref.ref(device)

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
#         self.insertTab(0, self.base, _('Configure %s') % self.device.current_friendly_name)
        self.insertTab(0, self.base, _("File formats"))
        l = self.base.l = QGridLayout(self.base)
        self.base.setLayout(l)

        self.formats = FormatsConfig(self.all_formats, device_settings.format_map)
        if device.HIDE_FORMATS_CONFIG_BOX:
            self.formats.hide()

        self.opt_use_subdirs = create_checkbox(
                                           _("Use sub-directories"),
                                           _('Place files in sub-directories if the device supports them'),
                                           device_settings.use_subdirs
                                           )
        self.opt_read_metadata = create_checkbox(
                                             _("Read metadata from files on device"),
                                             _('Read metadata from files on device'),
                                             device_settings.read_metadata
                                             )

        self.template = TemplateConfig(device_settings.save_template)
        self.opt_use_author_sort = create_checkbox(
                                             _("Use author sort for author"),
                                             _("Use author sort for author"),
                                             device_settings.read_metadata
                                             )
        self.opt_use_author_sort.setObjectName("opt_use_author_sort")
        self.base.la = la = QLabel(_(
            'Choose the formats to send to the %s')%self.device_name)
        la.setWordWrap(True)

        l.addWidget(la,                         1, 0, 1, 1)
        l.addWidget(self.formats,               2, 0, 1, 1)
        l.addWidget(self.opt_read_metadata,     3, 0, 1, 1)
        l.addWidget(self.opt_use_subdirs,       4, 0, 1, 1)
        l.addWidget(self.opt_use_author_sort,   5, 0, 1, 1)
        l.addWidget(self.template,              6, 0, 1, 1)
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

        self.extra_tab = ExtraCustomization(self.extra_customization_message,
                                            self.extra_customization_choices,
                                            self.device_settings)
        # Only display the extra customization tab if there are options on it.
        if self.extra_tab.has_extra_customizations:
            self.addTab(self.extra_tab, _('Extra customization'))

        self.setCurrentIndex(0)

    def addDeviceTab(self, tab, label):
        '''
        This is used to add a new tab for the device config. The new tab will always be added
        as immediately before the "Extra Customization" tab.
        '''
        extra_tab_pos = self.indexOf(self.extra_tab)
        self.insertTab(extra_tab_pos, tab, label)

    def __getattr__(self, attr_name):
        "If the object doesn't have an attribute, then check each tab."
        try:
            return super(TabbedDeviceConfig, self).__getattr__(attr_name)
        except AttributeError as ae:
            for i in range(0, self.count()):
                atab = self.widget(i)
                try:
                    return getattr(atab, attr_name)
                except AttributeError:
                    pass
        raise ae

    @property
    def device(self):
        return self._device()

    def format_map(self):
        return self.formats.format_map

    def use_subdirs(self):
        return self.opt_use_subdirs.isChecked()

    def read_metadata(self):
        return self.opt_read_metadata.isChecked()

    def use_author_sort(self):
        return self.opt_use_author_sort.isChecked()

    @property
    def opt_save_template(self):
        # Really shouldn't be accessing the template this way
        return self.template.t

    def text(self):
        # Really shouldn't be accessing the template this way
        return self.template.t.text()

    @property
    def opt_extra_customization(self):
        return self.extra_tab.opt_extra_customization

    @property
    def label(self):
        return self.opt_save_template

    def validate(self):
        if hasattr(self, 'formats'):
            if not self.formats.validate():
                return False
            if not self.template.validate():
                return False
        return True

    def commit(self):
        debug_print("TabbedDeviceConfig::commit: start")
        p = self.device._configProxy()

        p['format_map'] = self.formats.format_map
        p['use_subdirs'] = self.use_subdirs()
        p['read_metadata'] = self.read_metadata()
        p['save_template'] = self.template.template
        p['extra_customization'] = self.extra_tab.extra_customization()

        return p


class DeviceConfigTab(QWidget):  # {{{
    '''
    This is an abstraction for a tab in the configuration. The main reason for it is to
    abstract the properties of the configuration tab. When a property is accessed, it
    will iterate over all known widgets looking for the property.
    '''

    def __init__(self, parent=None):
        QWidget.__init__(self)
        self.parent = parent

        self.device_widgets = []

    def addDeviceWidget(self, widget):
        self.device_widgets.append(widget)

    def __getattr__(self, attr_name):
        try:
            return super(DeviceConfigTab, self).__getattr__(attr_name)
        except AttributeError as ae:
            for awidget in self.device_widgets:
                try:
                    return getattr(awidget, attr_name)
                except AttributeError:
                    pass
        raise ae


class ExtraCustomization(DeviceConfigTab):  # {{{

    def __init__(self, extra_customization_message, extra_customization_choices, device_settings):
        super(ExtraCustomization, self).__init__()

        debug_print("ExtraCustomization.__init__ - extra_customization_message=", extra_customization_message)
        debug_print("ExtraCustomization.__init__ - extra_customization_choices=", extra_customization_choices)
        debug_print("ExtraCustomization.__init__ - device_settings.extra_customization=", device_settings.extra_customization)
        debug_print("ExtraCustomization.__init__ - device_settings=", device_settings)
        self.extra_customization_message = extra_customization_message

        self.l = QVBoxLayout(self)
        self.setLayout(self.l)

        options_group = QGroupBox(_("Extra driver customization options"), self)
        self.l.addWidget(options_group)
        self.extra_layout = QGridLayout()
        self.extra_layout.setObjectName("extra_layout")
        options_group.setLayout(self.extra_layout)

        if extra_customization_message:
            extra_customization_choices = extra_customization_choices or {}

            def parse_msg(m):
                msg, _, tt = m.partition(':::') if m else ('', '', '')
                return msg.strip(), textwrap.fill(tt.strip(), 100)

            if isinstance(extra_customization_message, list):
                self.opt_extra_customization = []
                if len(extra_customization_message) > 6:
                    row_func = lambda x, y: ((x/2) * 2) + y
                    col_func = lambda x: x%2
                else:
                    row_func = lambda x, y: x*2 + y
                    col_func = lambda x: 0

                for i, m in enumerate(extra_customization_message):
                    label_text, tt = parse_msg(m)
                    if not label_text:
                        self.opt_extra_customization.append(None)
                        continue
                    if isinstance(device_settings.extra_customization[i], bool):
                        self.opt_extra_customization.append(QCheckBox(label_text))
                        self.opt_extra_customization[-1].setToolTip(tt)
                        self.opt_extra_customization[i].setChecked(bool(device_settings.extra_customization[i]))
                    elif i in extra_customization_choices:
                        cb = QComboBox(self)
                        self.opt_extra_customization.append(cb)
                        l = QLabel(label_text)
                        l.setToolTip(tt), cb.setToolTip(tt), l.setBuddy(cb), cb.setToolTip(tt)
                        for li in sorted(extra_customization_choices[i]):
                            self.opt_extra_customization[i].addItem(li)
                        cb.setCurrentIndex(max(0, cb.findText(device_settings.extra_customization[i])))
                    else:
                        self.opt_extra_customization.append(QLineEdit(self))
                        l = QLabel(label_text)
                        l.setToolTip(tt)
                        self.opt_extra_customization[i].setToolTip(tt)
                        l.setBuddy(self.opt_extra_customization[i])
                        l.setWordWrap(True)
                        self.opt_extra_customization[i].setText(device_settings.extra_customization[i])
                        self.opt_extra_customization[i].setCursorPosition(0)
                        self.extra_layout.addWidget(l, row_func(i + 2, 0), col_func(i))
                    self.extra_layout.addWidget(self.opt_extra_customization[i],
                                                row_func(i + 2, 1), col_func(i))
                spacerItem1 = QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
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

    def extra_customization(self):
        ec = []
        if self.extra_customization_message:
            if isinstance(self.extra_customization_message, list):
                for i in range(0, len(self.extra_customization_message)):
                    if self.opt_extra_customization[i] is None:
                        ec.append(None)
                        continue
                    if hasattr(self.opt_extra_customization[i], 'isChecked'):
                        ec.append(self.opt_extra_customization[i].isChecked())
                    elif hasattr(self.opt_extra_customization[i], 'currentText'):
                        ec.append(unicode(self.opt_extra_customization[i].currentText()).strip())
                    else:
                        ec.append(unicode(self.opt_extra_customization[i].text()).strip())
            else:
                ec = unicode(self.opt_extra_customization.text()).strip()
                if not ec:
                    ec = None

        return ec

    @property
    def has_extra_customizations(self):
        debug_print("ExtraCustomization::has_extra_customizations - self.extra_customization_message", self.extra_customization_message)
        return self.extra_customization_message and len(self.extra_customization_message) > 0

# }}}


class DeviceOptionsGroupBox(QGroupBox):
    """
    This is a container for the individual options for a device driver.
    """

    def __init__(self, parent, device=None, title=_("Unknown")):
        QGroupBox.__init__(self, parent)

        self.device = device
        self.setTitle(title)


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.devices.kobo.driver import KOBO
    from calibre.devices.scanner import DeviceScanner
    s = DeviceScanner()
    s.scan()
    app = Application([])
    dev = KOBO(None)
    debug_print("KOBO:", KOBO)
#     dev.startup()
#     cd = dev.detect_managed_devices(s.devices)
#     dev.open(cd, 'test')
    cw = dev.config_widget()
    d = QDialog()
    d.l = QVBoxLayout()
    d.setLayout(d.l)
    d.l.addWidget(cw)
    bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
    d.l.addWidget(bb)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    if d.exec_() == d.Accepted:
        cw.commit()
    dev.shutdown()
