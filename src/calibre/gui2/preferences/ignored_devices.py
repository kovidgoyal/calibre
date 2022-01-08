#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>


import textwrap

from qt.core import (
    QIcon, QLabel, QListWidget, QListWidgetItem, QPushButton, Qt, QVBoxLayout
)

from calibre.customize.ui import enable_plugin
from calibre.gui2 import gprefs
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from polyglot.builtins import iteritems


class ConfigWidget(ConfigWidgetBase):

    restart_critical = False

    def genesis(self, gui):
        self.gui = gui
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.confirms_reset = False

        self.la = la = QLabel(_(
            'The list of devices that you have asked calibre to ignore. '
            'Uncheck a device to have calibre stop ignoring it.'))
        la.setWordWrap(True)
        l.addWidget(la)

        self.devices = f = QListWidget(self)
        l.addWidget(f)
        f.itemChanged.connect(self.changed_signal)
        f.itemDoubleClicked.connect(self.toggle_item)

        self.la2 = la = QLabel(_(
            'The list of device plugins you have disabled. Uncheck an entry '
            'to enable the plugin. calibre cannot detect devices that are '
            'managed by disabled plugins.'))
        la.setWordWrap(True)
        l.addWidget(la)

        self.device_plugins = f = QListWidget(f)
        l.addWidget(f)
        f.itemChanged.connect(self.changed_signal)
        f.itemDoubleClicked.connect(self.toggle_item)

        self.reset_confirmations_button = b = QPushButton(_('Reset allowed devices'))
        b.setToolTip(textwrap.fill(_(
            'This will erase the list of devices that calibre knows about'
            ' causing it to ask you for permission to manage them again,'
            ' the next time they connect')))
        b.clicked.connect(self.reset_confirmations)
        l.addWidget(b)

    def reset_confirmations(self):
        self.confirms_reset = True
        self.changed_signal.emit()

    def toggle_item(self, item):
        item.setCheckState(Qt.CheckState.Checked if item.checkState() == Qt.CheckState.Unchecked else
                Qt.CheckState.Unchecked)

    def initialize(self):
        self.confirms_reset = False
        self.devices.blockSignals(True)
        self.devices.clear()
        for dev in self.gui.device_manager.devices:
            for d, name in iteritems(dev.get_user_blacklisted_devices()):
                item = QListWidgetItem('%s [%s]'%(name, d), self.devices)
                item.setData(Qt.ItemDataRole.UserRole, (dev, d))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsSelectable)
                item.setCheckState(Qt.CheckState.Checked)
        self.devices.blockSignals(False)

        self.device_plugins.blockSignals(True)
        for dev in self.gui.device_manager.disabled_device_plugins:
            n = dev.get_gui_name()
            item = QListWidgetItem(n, self.device_plugins)
            item.setData(Qt.ItemDataRole.UserRole, dev)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsSelectable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setIcon(QIcon.ic('plugins.png'))
        self.device_plugins.sortItems()
        self.device_plugins.blockSignals(False)

    def restore_defaults(self):
        if self.devices.count() > 0:
            self.devices.clear()

    def commit(self):
        devs = {}
        for i in range(0, self.devices.count()):
            e = self.devices.item(i)
            dev, uid = e.data(Qt.ItemDataRole.UserRole)
            if dev not in devs:
                devs[dev] = []
            if e.checkState() == Qt.CheckState.Checked:
                devs[dev].append(uid)

        for dev, bl in iteritems(devs):
            dev.set_user_blacklisted_devices(bl)

        for i in range(self.device_plugins.count()):
            e = self.device_plugins.item(i)
            dev = e.data(Qt.ItemDataRole.UserRole)
            if e.checkState() == Qt.CheckState.Unchecked:
                enable_plugin(dev)
        if self.confirms_reset:
            gprefs['ask_to_manage_device'] = []

        return True  # Restart required


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Sharing', 'Ignored Devices')
