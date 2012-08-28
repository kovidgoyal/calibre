#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import netifaces

from PyQt4.Qt import (QDialog, QLineEdit, Qt, QPushButton, QDialogButtonBox)

from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.smartdevice_ui import Ui_Dialog
from calibre.utils.config import prefs

def _cmp_ipaddr(l, r):
    lparts = ['%3s'%x for x in l.split('.')]
    rparts = ['%3s'%x for x in r.split('.')]

    if lparts[0] in ['192', '170', ' 10']:
        if rparts[0] not in ['192', '170', '10']:
            return -1
        return cmp(rparts, lparts)

    if rparts[0] in ['192', '170', ' 10']:
        return 1

    return cmp(lparts, rparts)

def _get_all_ip_addresses():
        ip_info = [netifaces.ifaddresses(x).get(netifaces.AF_INET, None)
                   for x in netifaces.interfaces()]

        all_ipaddrs = list()
        for iface in ip_info:
            if iface is not None:
                for addrs in iface:
                    if 'netmask' in addrs and addrs['addr'] != '127.0.0.1':
                        # We get VPN interfaces that were connected and then
                        # disconnected. Oh well. At least the 'right' IP addr
                        # is there.
                        all_ipaddrs.append(addrs['addr'])

        all_ipaddrs.sort(cmp=_cmp_ipaddr)
        return all_ipaddrs

_all_ip_addresses = []
def get_all_ip_addresses():
    global _all_ip_addresses
    if not _all_ip_addresses:
        _all_ip_addresses = _get_all_ip_addresses()
    return _all_ip_addresses

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
              '8,000 and 32,000.') + '</p>')


        self.ip_addresses.setToolTip('<p>' +
            _('These are the IP addresses detected by calibre for the computer '
              'running calibre. If you decide to have your device connect to '
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

        auto_mgmt_button = QPushButton(_('Enable automatic metadata management'))
        auto_mgmt_button.clicked.connect(self.auto_mgmt_button_clicked)
        auto_mgmt_button.setToolTip('<p>' +
            _('Enabling automatic metadata management tells calibre to send any '
              'changes you made to books\' metadata when your device is '
              'connected, which is the most useful setting when using the wireless '
              'device interface. If automatic metadata management is not '
              'enabled, changes are sent only when you send a book. You can '
              'get more information or change this preference to some other '
              'choice at Preferences -> Send to device -> Metadata management')
                                                    + '</p>')
        self.buttonBox.addButton(auto_mgmt_button, QDialogButtonBox.ActionRole)
        self.set_auto_management = False
        if prefs['manage_device_metadata'] == 'on_connect':
            auto_mgmt_button.setText(_('Automatic metadata management is enabled'))
            auto_mgmt_button.setEnabled(False)

        self.ip_addresses.setText(', '.join(get_all_ip_addresses()))

        self.resize(self.sizeHint())

    def auto_mgmt_button_clicked(self):
        self.set_auto_management = True

    def use_fixed_port_changed(self, state):
        self.fixed_port.setEnabled(state == Qt.Checked)

    def toggle_password(self, state):
        self.password_box.setEchoMode(QLineEdit.Password if state ==
                Qt.Unchecked else QLineEdit.Normal)

    def accept(self):
        port = unicode(self.fixed_port.text())
        if not port:
            error_dialog(self, _('Invalid port number'),
                _('You must provide a port number.'), show=True)
            return
        try:
            port = int(port)
        except:
            error_dialog(self, _('Invalid port number'),
                _('The port must be a number between 8000 and 32000.'), show=True)
            return

        if port < 8000 or port > 32000:
            error_dialog(self, _('Invalid port number'),
                _('The port must be a number between 8000 and 32000.'), show=True)
            return

        self.device_manager.set_option('smartdevice', 'password',
                                       unicode(self.password_box.text()))
        self.device_manager.set_option('smartdevice', 'autostart',
                                       self.autostart_box.isChecked())
        self.device_manager.set_option('smartdevice', 'use_fixed_port',
                                       self.use_fixed_port.isChecked())
        self.device_manager.set_option('smartdevice', 'port_number',
                                       unicode(self.fixed_port.text()))

        message = self.device_manager.start_plugin('smartdevice')

        if not self.device_manager.is_running('smartdevice'):
            error_dialog(self, _('Problem starting the wireless device'),
                _('The wireless device driver did not start. It said "%s"')%message,
                show=True)
            self.device_manager.set_option('smartdevice', 'use_fixed_port',
                                           self.orig_fixed_port)
            self.device_manager.set_option('smartdevice', 'port_number',
                                           self.orig_port_number)
        else:
            if self.set_auto_management:
                prefs.set('manage_device_metadata', 'on_connect')
            QDialog.accept(self)

