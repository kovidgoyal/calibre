__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import re
from PyQt4.QtGui import QDialog, QLineEdit
from PyQt4.QtCore import SIGNAL, Qt

from calibre.gui2.dialogs.smartdevice_ui import Ui_Dialog
from calibre.gui2 import dynamic

class SmartdeviceDialog(QDialog, Ui_Dialog):

    def __init__(self, parent):
        QDialog.__init__(self, parent)
        Ui_Dialog.__init__(self)
        self.setupUi(self)

        self.msg.setText(
            _('This dialog starts and stops the smart device app interface. '
              'When you start the interface, you might see some messages from '
              'your computer\'s firewall or anti-virus manager asking you '
              'if it is OK for calibre to connect to the network. <B>Please '
              'answer yes</b>. If you do not, the app will not work. It will '
              'be unable to connect to calibre.'))

        self.passwd_msg.setText(
             _('Use a password if calibre is running on a network that '
              'is not secure. For example, if you run calibre on a laptop, '
              'use that laptop in an airport, and want to connect your '
              'smart device to calibre, you should use a password.'))

        self.auto_start_msg.setText(
            _('Check this box if you want calibre to automatically start the '
              'smart device interface when calibre starts. You should not do '
              'this if you are using a network that is not secure and you '
              'are not setting a password.'))
        self.connect(self.show_password, SIGNAL('stateChanged(int)'), self.toggle_password)

        self.device_manager = parent.device_manager
        if self.device_manager.get_option('smartdevice', 'autostart'):
            self.autostart_box.setChecked(True)
        pw = self.device_manager.get_option('smartdevice', 'password')
        if pw:
            self.password_box.setText(pw)

        if self.device_manager.is_running('smartdevice'):
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        else:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_button_clicked)
        self.stop_button.clicked.connect(self.stop_button_clicked)
        self.cancel_button.clicked.connect(self.cancel_button_clicked)
        self.OK_button.clicked.connect(self.accept)

    def start_button_clicked(self):
        self.device_manager.start_plugin('smartdevice')
        self.accept()

    def stop_button_clicked(self):
        self.device_manager.stop_plugin('smartdevice')
        self.accept()

    def cancel_button_clicked(self):
        QDialog.reject(self)

    def toggle_password(self, state):
        if state == Qt.Unchecked:
            self.password_box.setEchoMode(QLineEdit.Password)
        else:
            self.password_box.setEchoMode(QLineEdit.Normal)

    def accept(self):
        self.device_manager.set_option('smartdevice', 'password',
                                       unicode(self.password_box.text()))
        self.device_manager.set_option('smartdevice', 'autostart',
                                       self.autostart_box.isChecked())
        QDialog.accept(self)
