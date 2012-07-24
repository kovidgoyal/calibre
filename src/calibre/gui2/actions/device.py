#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QToolButton, QMenu, pyqtSignal, QIcon, QTimer

from calibre.gui2.actions import InterfaceAction
from calibre.utils.smtp import config as email_config
from calibre.constants import iswindows, isosx
from calibre.customize.ui import is_disabled
from calibre.devices.bambook.driver import BAMBOOK
from calibre.gui2.dialogs.smartdevice import SmartdeviceDialog
from calibre.gui2 import info_dialog

class ShareConnMenu(QMenu): # {{{

    connect_to_folder = pyqtSignal()
    connect_to_itunes = pyqtSignal()
    connect_to_bambook = pyqtSignal()

    config_email = pyqtSignal()
    toggle_server = pyqtSignal()
    control_smartdevice = pyqtSignal()
    dont_add_to = frozenset(['context-menu-device'])

    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        mitem = self.addAction(QIcon(I('devices/folder.png')), _('Connect to folder'))
        mitem.setEnabled(True)
        mitem.triggered.connect(lambda x : self.connect_to_folder.emit())
        self.connect_to_folder_action = mitem
        mitem = self.addAction(QIcon(I('devices/itunes.png')),
                _('Connect to iTunes'))
        mitem.setEnabled(True)
        mitem.triggered.connect(lambda x : self.connect_to_itunes.emit())
        self.connect_to_itunes_action = mitem
        if not (iswindows or isosx):
            mitem.setVisible(False)
        mitem = self.addAction(QIcon(I('devices/bambook.png')), _('Connect to Bambook'))
        mitem.setEnabled(True)
        mitem.triggered.connect(lambda x : self.connect_to_bambook.emit())
        self.connect_to_bambook_action = mitem
        bambook_visible = False
        if not is_disabled(BAMBOOK):
            device_ip = BAMBOOK.settings().extra_customization
            if device_ip:
                bambook_visible = True
        self.connect_to_bambook_action.setVisible(bambook_visible)

        self.addSeparator()
        self.toggle_server_action = \
            self.addAction(QIcon(I('network-server.png')),
            _('Start Content Server'))
        self.toggle_server_action.triggered.connect(lambda x:
                self.toggle_server.emit())
        self.control_smartdevice_action = \
            self.addAction(QIcon(I('dot_green.png')),
            _('Control Smart Device Connections'))
        self.control_smartdevice_action.triggered.connect(lambda x:
                self.control_smartdevice.emit())
        self.addSeparator()

        self.email_actions = []

        if hasattr(parent, 'keyboard'):
            r = parent.keyboard.register_shortcut
            prefix = 'Share/Connect Menu '
            gr = ConnectShareAction.action_spec[0]
            for attr in ('folder', 'bambook', 'itunes'):
                if not (iswindows or isosx) and attr == 'itunes':
                    continue
                ac = getattr(self, 'connect_to_%s_action'%attr)
                r(prefix + attr, unicode(ac.text()), action=ac,
                        group=gr)
            r(prefix+' content server', _('Start/stop content server'),
                    action=self.toggle_server_action, group=gr)

    def server_state_changed(self, running):
        from calibre.utils.mdns import get_external_ip
        text = _('Start Content Server')
        if running:
            text = _('Stop Content Server') + ' [%s]'%get_external_ip()
        self.toggle_server_action.setText(text)

    def hide_smartdevice_menus(self):
        self.control_smartdevice_action.setVisible(False)

    def build_email_entries(self, sync_menu):
        from calibre.gui2.device import DeviceAction
        for ac in self.email_actions:
            self.removeAction(ac)
        self.email_actions = []
        self.memory = []
        opts = email_config().parse()
        if opts.accounts:
            self.email_to_menu = QMenu(_('Email to')+'...', self)
            ac = self.addMenu(self.email_to_menu)
            self.email_actions.append(ac)
            self.email_to_and_delete_menu = QMenu(
                    _('Email to and delete from library')+'...', self)
            keys = sorted(opts.accounts.keys())
            for account in keys:
                formats, auto, default = opts.accounts[account]
                subject = opts.subjects.get(account, '')
                dest = 'mail:'+account+';'+formats+';'+subject
                action1 = DeviceAction(dest, False, False, I('mail.png'),
                        account)
                action2 = DeviceAction(dest, True, False, I('mail.png'),
                        account + ' ' + _('(delete from library)'))
                self.email_to_menu.addAction(action1)
                self.email_to_and_delete_menu.addAction(action2)
                map(self.memory.append, (action1, action2))
                if default:
                    ac = DeviceAction(dest, False, False,
                            I('mail.png'), _('Email to') + ' ' +account)
                    self.addAction(ac)
                    self.email_actions.append(ac)
                    ac.a_s.connect(sync_menu.action_triggered)
                action1.a_s.connect(sync_menu.action_triggered)
                action2.a_s.connect(sync_menu.action_triggered)
            ac = self.addMenu(self.email_to_and_delete_menu)
            self.email_actions.append(ac)
        else:
            ac = self.addAction(_('Setup email based sharing of books'))
            self.email_actions.append(ac)
            ac.triggered.connect(self.setup_email)

    def setup_email(self, *args):
        self.config_email.emit()

    def set_state(self, device_connected):
        self.connect_to_folder_action.setEnabled(not device_connected)
        self.connect_to_itunes_action.setEnabled(not device_connected)
        self.connect_to_bambook_action.setEnabled(not device_connected)


# }}}

class SendToDeviceAction(InterfaceAction):

    name = 'Send To Device'
    action_spec = (_('Send to device'), 'sync.png', None, _('D'))
    dont_add_to = frozenset(['menubar', 'toolbar', 'context-menu', 'toolbar-child'])

    def genesis(self):
        self.qaction.triggered.connect(self.do_sync)
        self.gui.create_device_menu()

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def do_sync(self, *args):
        self.gui._sync_action_triggered()


class ConnectShareAction(InterfaceAction):

    name = 'Connect Share'
    action_spec = (_('Connect/share'), 'connect_share.png', None, None)
    popup_type = QToolButton.InstantPopup

    def genesis(self):
        self.share_conn_menu = ShareConnMenu(self.gui)
        self.share_conn_menu.toggle_server.connect(self.toggle_content_server)
        self.share_conn_menu.control_smartdevice.connect(self.control_smartdevice)
        self.share_conn_menu.config_email.connect(partial(
            self.gui.iactions['Preferences'].do_config,
            initial_plugin=('Sharing', 'Email')))
        self.qaction.setMenu(self.share_conn_menu)
        self.share_conn_menu.connect_to_folder.connect(self.gui.connect_to_folder)
        self.share_conn_menu.connect_to_itunes.connect(self.gui.connect_to_itunes)
        self.share_conn_menu.connect_to_bambook.connect(self.gui.connect_to_bambook)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def set_state(self, device_connected):
        self.share_conn_menu.set_state(device_connected)

    def build_email_entries(self):
        m = self.gui.iactions['Send To Device'].qaction.menu()
        self.share_conn_menu.build_email_entries(m)

    def content_server_state_changed(self, running):
        self.share_conn_menu.server_state_changed(running)
        if running:
            self.qaction.setIcon(QIcon(I('connect_share_on.png')))
        else:
            self.qaction.setIcon(QIcon(I('connect_share.png')))

    def toggle_content_server(self):
        if self.gui.content_server is None:
            self.gui.start_content_server()
        else:
            self.gui.content_server.threaded_exit()
            self.stopping_msg = info_dialog(self.gui, _('Stopping'),
                    _('Stopping server, this could take upto a minute, please wait...'),
                    show_copy_button=False)
            QTimer.singleShot(1000, self.check_exited)

    def check_exited(self):
        if self.gui.content_server.is_running:
            QTimer.singleShot(20, self.check_exited)
            if not self.stopping_msg.isVisible():
                self.stopping_msg.exec_()
            return
        self.gui.content_server = None
        self.stopping_msg.accept()

    def control_smartdevice(self):
        sd_dialog = SmartdeviceDialog(self.gui)
        sd_dialog.exec_()
        self.set_smartdevice_icon()

    def check_smartdevice_menus(self):
        if not self.gui.device_manager.is_enabled('smartdevice'):
            self.share_conn_menu.hide_smartdevice_menus()

    def set_smartdevice_icon(self):
        running = self.gui.device_manager.is_running('smartdevice')
        if running:
            self.share_conn_menu.control_smartdevice_action.setIcon(QIcon(I('dot_green.png')))
        else:
            self.share_conn_menu.control_smartdevice_action.setIcon(QIcon(I('dot_red.png')))
