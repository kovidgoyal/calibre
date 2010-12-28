#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QToolButton, QMenu, pyqtSignal, QIcon

from calibre.gui2.actions import InterfaceAction
from calibre.utils.smtp import config as email_config
from calibre.constants import iswindows, isosx
from calibre.customize.ui import is_disabled
from calibre.devices.bambook.driver import BAMBOOK

class ShareConnMenu(QMenu): # {{{

    connect_to_folder = pyqtSignal()
    connect_to_itunes = pyqtSignal()
    connect_to_bambook = pyqtSignal()

    config_email = pyqtSignal()
    toggle_server = pyqtSignal()
    dont_add_to = frozenset(['toolbar-device', 'context-menu-device'])

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
        if is_disabled(BAMBOOK):
            mitem.setVisible(False)
        self.addSeparator()
        self.toggle_server_action = \
            self.addAction(QIcon(I('network-server.png')),
            _('Start Content Server'))
        self.toggle_server_action.triggered.connect(lambda x:
                self.toggle_server.emit())
        self.addSeparator()

        self.email_actions = []

    def server_state_changed(self, running):
        text = _('Start Content Server')
        if running:
            text = _('Stop Content Server')
        self.toggle_server_action.setText(text)

    def build_email_entries(self, sync_menu):
        from calibre.gui2.device import DeviceAction
        for ac in self.email_actions:
            self.removeAction(ac)
        self.email_actions = []
        self.memory = []
        opts = email_config().parse()
        if opts.accounts:
            self.email_to_menu = QMenu(_('Email to')+'...', self)
            keys = sorted(opts.accounts.keys())
            for account in keys:
                formats, auto, default = opts.accounts[account]
                dest = 'mail:'+account+';'+formats
                action1 = DeviceAction(dest, False, False, I('mail.png'),
                        _('Email to')+' '+account)
                action2 = DeviceAction(dest, True, False, I('mail.png'),
                        _('Email to')+' '+account+ _(' and delete from library'))
                map(self.email_to_menu.addAction, (action1, action2))
                map(self.memory.append, (action1, action2))
                if default:
                    map(self.addAction, (action1, action2))
                    map(self.email_actions.append, (action1, action2))
                self.email_to_menu.addSeparator()
                action1.a_s.connect(sync_menu.action_triggered)
                action2.a_s.connect(sync_menu.action_triggered)
            ac = self.addMenu(self.email_to_menu)
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
        bambook_visible = False
        if not is_disabled(BAMBOOK):
            device_ip = BAMBOOK.settings().extra_customization
            if device_ip != None and device_ip != '':
                bambook_visible = True
        self.connect_to_bambook_action.setVisible(bambook_visible)


# }}}

class SendToDeviceAction(InterfaceAction):

    name = 'Send To Device'
    action_spec = (_('Send to device'), 'sync.png', None, _('D'))
    dont_remove_from = frozenset(['toolbar-device'])
    dont_add_to = frozenset(['toolbar', 'context-menu'])

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

    def toggle_content_server(self):
        if self.gui.content_server is None:
           self.gui.start_content_server()
        else:
            self.gui.content_server.exit()
            self.gui.content_server = None
