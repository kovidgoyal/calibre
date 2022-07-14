#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from qt.core import (QDialog, QLineEdit, Qt)

from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.smartdevice_ui import Ui_Dialog
from calibre.utils.mdns import get_all_ips
from polyglot.builtins import itervalues


def ipaddr_sort_key(ipaddr):
    if '.' in ipaddr:
        parts = tuple(map(int, ipaddr.split('.')))
        is_private = parts[0] in (192, 170, 10)
        return (0 if is_private else 1), parts


def get_all_ip_addresses():
    ipaddrs = list()
    for iface in itervalues(get_all_ips()):
        for addrs in iface:
            if 'broadcast' in addrs and addrs['addr'] != '127.0.0.1':
                ipaddrs.append(addrs['addr'])
    ipaddrs.sort(key=ipaddr_sort_key)
    return ipaddrs


class SmartdeviceDialog(QDialog, Ui_Dialog):

    def __init__(self, parent):
        QDialog.__init__(self, parent)
        Ui_Dialog.__init__(self)
        self.setupUi(self)

        self.password_box.setToolTip('<p>' +
             _('Use a password if calibre is running on a network that '
              'is not secure. For example, if you run calibre on a laptop, '
              'use that laptop in an airport, and want to connect your '
              'smart device to calibre, you should use a password.') + '</p>')

        self.autostart_box.setToolTip('<p>' +
            _('Check this box if you want calibre to automatically start the '
              'smart device interface when calibre starts. You should not do '
              'this if you are using a network that is not secure and you '
              'are not setting a password.') + '</p>')

        self.use_fixed_port.setToolTip('<p>' +
            _('Check this box if you want calibre to use a fixed network '
              'port. Normally you will not need to do this. However, if '
              'your device consistently fails to connect to calibre, '
              'try checking this box and entering a number.') + '</p>')

        self.fixed_port.setToolTip('<p>' +
            _('Try 9090. If calibre says that it fails to connect '
              'to the port, try another number. You can use any number between '
              '8,000 and 65,535.') + '</p>')

        self.ip_addresses.setToolTip('<p>' +
            _('These are the IP addresses for this computer. If you decide to have your device connect to '
              'calibre using a fixed IP address, one of these addresses should '
              'be the one you use. It is unlikely but possible that the correct '
              'IP address is not listed here, in which case you will need to go '
              "to your computer's control panel to get a complete list of "
              "your computer's network interfaces and IP addresses.") + '</p>')

        self.show_password.stateChanged[int].connect(self.toggle_password)
        self.use_fixed_port.stateChanged[int].connect(self.use_fixed_port_changed)

        self.device_manager = parent.device_manager

        if self.device_manager.get_option('smartdevice', 'autostart'):
            self.autostart_box.setChecked(True)

        pw = self.device_manager.get_option('smartdevice', 'password')
        if pw:
            self.password_box.setText(pw)

        self.orig_fixed_port = self.device_manager.get_option('smartdevice',
                                                             'use_fixed_port')
        self.orig_port_number = self.device_manager.get_option('smartdevice',
                                                          'port_number')
        self.fixed_port.setText(self.orig_port_number)
        self.use_fixed_port.setChecked(self.orig_fixed_port)
        if not self.orig_fixed_port:
            self.fixed_port.setEnabled(False)

        if pw:
            self.password_box.setText(pw)

        forced_ip = self.device_manager.get_option('smartdevice', 'force_ip_address')
        if forced_ip:
            self.ip_addresses.setText(forced_ip)
        else:
            self.ip_addresses.setText(', '.join(get_all_ip_addresses()))

        self.resize(self.sizeHint())

    def use_fixed_port_changed(self, state):
        self.fixed_port.setEnabled(Qt.CheckState(state) == Qt.CheckState.Checked)

    def toggle_password(self, state):
        self.password_box.setEchoMode(QLineEdit.EchoMode.Password if state ==
                Qt.CheckState.Unchecked else QLineEdit.EchoMode.Normal)

    def accept(self):
        port = str(self.fixed_port.text())
        if not port:
            error_dialog(self, _('Invalid port number'),
                _('You must provide a port number.'), show=True)
            return
        try:
            port = int(port)
        except:
            error_dialog(self, _('Invalid port number'),
                _('The port must be a number between 8000 and 65535.'), show=True)
            return

        if port < 8000 or port > 65535:
            error_dialog(self, _('Invalid port number'),
                _('The port must be a number between 8000 and 65535.'), show=True)
            return

        self.device_manager.set_option('smartdevice', 'password',
                                       str(self.password_box.text()))
        self.device_manager.set_option('smartdevice', 'autostart',
                                       self.autostart_box.isChecked())
        self.device_manager.set_option('smartdevice', 'use_fixed_port',
                                       self.use_fixed_port.isChecked())
        self.device_manager.set_option('smartdevice', 'port_number',
                                       str(self.fixed_port.text()))

        message = self.device_manager.start_plugin('smartdevice')

        if not self.device_manager.is_running('smartdevice'):
            error_dialog(self, _('Problem starting the wireless device'),
                _('The wireless device driver had problems starting. It said "%s"')%message,
                show=True)
            self.device_manager.set_option('smartdevice', 'use_fixed_port',
                                           self.orig_fixed_port)
            self.device_manager.set_option('smartdevice', 'port_number',
                                           self.orig_port_number)
        else:
            QDialog.accept(self)
