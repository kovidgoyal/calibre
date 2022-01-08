#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import QIcon, QMenu, QTimer, QToolButton, pyqtSignal, QUrl

from calibre.gui2 import info_dialog, question_dialog, open_url
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.smartdevice import SmartdeviceDialog
from calibre.utils.icu import primary_sort_key
from calibre.utils.smtp import config as email_config


def local_url_for_content_server():
    from calibre.srv.opts import server_config
    opts = server_config()
    interface = opts.listen_on or '0.0.0.0'
    interface = {'0.0.0.0': '127.0.0.1', '::':'::1'}.get(interface)
    protocol = 'https' if opts.ssl_certfile and opts.ssl_keyfile else 'http'
    prefix = opts.url_prefix or ''
    port = opts.port
    return f'{protocol}://{interface}:{port}{prefix}'


def open_in_browser():
    open_url(QUrl(local_url_for_content_server()))


class ShareConnMenu(QMenu):  # {{{

    connect_to_folder = pyqtSignal()

    config_email = pyqtSignal()
    toggle_server = pyqtSignal()
    control_smartdevice = pyqtSignal()
    server_state_changed_signal = pyqtSignal(object, object)
    dont_add_to = frozenset(('context-menu-device',))

    DEVICE_MSGS = [_('Start wireless device connection'),
            _('Stop wireless device connection')]

    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        self.ip_text = ''
        mitem = self.addAction(QIcon.ic('devices/folder.png'), _('Connect to folder'))
        mitem.setEnabled(True)
        connect_lambda(mitem.triggered, self, lambda self: self.connect_to_folder.emit())
        self.connect_to_folder_action = mitem

        self.addSeparator()
        self.toggle_server_action = \
            self.addAction(QIcon.ic('network-server.png'),
            _('Start Content server'))
        connect_lambda(self.toggle_server_action.triggered, self, lambda self: self.toggle_server.emit())
        self.open_server_in_browser_action = self.addAction(
            QIcon.ic('forward.png'), _("Visit Content server in browser"))
        connect_lambda(self.open_server_in_browser_action.triggered, self, lambda self: open_in_browser())
        self.open_server_in_browser_action.setVisible(False)
        self.control_smartdevice_action = \
            self.addAction(QIcon.ic('dot_red.png'),
            self.DEVICE_MSGS[0])
        connect_lambda(self.control_smartdevice_action.triggered, self, lambda self: self.control_smartdevice.emit())
        self.addSeparator()

        self.email_actions = []

        if hasattr(parent, 'keyboard'):
            r = parent.keyboard.register_shortcut
            prefix = 'Share/Connect Menu '
            gr = ConnectShareAction.action_spec[0]
            for attr in ('folder', ):
                ac = getattr(self, 'connect_to_%s_action'%attr)
                r(prefix + attr, str(ac.text()), action=ac,
                        group=gr)
            r(prefix+' content server', _('Start/stop Content server'),
                    action=self.toggle_server_action, group=gr)
            r(prefix + ' open server in browser', self.open_server_in_browser_action.text(), action=self.open_server_in_browser_action, group=gr)

    def server_state_changed(self, running):
        from calibre.utils.mdns import get_external_ip, verify_ipV4_address
        text = _('Start Content server')
        if running:
            from calibre.srv.opts import server_config
            opts = server_config()
            listen_on = verify_ipV4_address(opts.listen_on) or get_external_ip()
            protocol = 'HTTPS' if opts.ssl_certfile and opts.ssl_keyfile else 'HTTP'
            try:
                ip_text = ' ' + _('[{ip}, port {port}, {protocol}]').format(
                        ip=listen_on, port=opts.port, protocol=protocol)
            except Exception:
                ip_text = f' [{listen_on} {protocol}]'
            self.ip_text = ip_text
            self.server_state_changed_signal.emit(running, ip_text)
            text = _('Stop Content server') + ip_text
        else:
            self.ip_text = ''
        self.toggle_server_action.setText(text)
        self.open_server_in_browser_action.setVisible(running)

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

            def sk(account):
                return primary_sort_key(opts.aliases.get(account) or account)

            for account in sorted(keys, key=sk):
                formats, auto, default = opts.accounts[account]
                subject = opts.subjects.get(account, '')
                alias = opts.aliases.get(account, '')
                dest = 'mail:'+account+';'+formats+';'+subject
                action1 = DeviceAction(dest, False, False, I('mail.png'),
                        alias or account)
                action2 = DeviceAction(dest, True, False, I('mail.png'),
                        (alias or account) + ' ' + _('(delete from library)'))
                self.email_to_menu.addAction(action1)
                self.email_to_and_delete_menu.addAction(action2)
                self.memory.append(action1)
                self.memory.append(action2)
                if default:
                    ac = DeviceAction(dest, False, False,
                            I('mail.png'), _('Email to') + ' ' +(alias or
                                account))
                    self.addAction(ac)
                    self.email_actions.append(ac)
                    ac.a_s.connect(sync_menu.action_triggered)
                action1.a_s.connect(sync_menu.action_triggered)
                action2.a_s.connect(sync_menu.action_triggered)
            action1 = DeviceAction('choosemail:', False, False, I('mail.png'),
                    _('Select recipients'))
            action2 = DeviceAction('choosemail:', True, False, I('mail.png'),
                    _('Select recipients') + ' ' + _('(delete from library)'))
            self.email_to_menu.addAction(action1)
            self.email_to_and_delete_menu.addAction(action2)
            self.memory.append(action1)
            self.memory.append(action2)
            tac1 = DeviceAction('choosemail:', False, False, I('mail.png'),
                    _('Email to selected recipients...'))
            self.addAction(tac1)
            tac1.a_s.connect(sync_menu.action_triggered)
            self.memory.append(tac1)
            self.email_actions.append(tac1)
            ac = self.addMenu(self.email_to_and_delete_menu)
            self.email_actions.append(ac)
            action1.a_s.connect(sync_menu.action_triggered)
            action2.a_s.connect(sync_menu.action_triggered)
        else:
            ac = self.addAction(QIcon.ic('mail.png'), _('Setup email based sharing of books'))
            self.email_actions.append(ac)
            ac.triggered.connect(self.setup_email)

    def setup_email(self, *args):
        self.config_email.emit()

    def set_state(self, device_connected, device):
        self.connect_to_folder_action.setEnabled(not device_connected)


# }}}

class SendToDeviceAction(InterfaceAction):

    name = 'Send To Device'
    action_spec = (_('Send to device'), 'sync.png', None, _('D'))
    dont_add_to = frozenset(('menubar', 'toolbar', 'context-menu', 'toolbar-child'))

    def genesis(self):
        self.qaction.triggered.connect(self.do_sync)
        self.gui.create_device_menu()

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)

    def do_sync(self, *args):
        self.gui._sync_action_triggered()


class ConnectShareAction(InterfaceAction):

    name = 'Connect Share'
    action_spec = (_('Connect/share'), 'connect_share.png',
                   _('Share books using a web server or email. Connect to special devices, etc.'), None)
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup

    def genesis(self):
        self.content_server_is_running = False
        self.share_conn_menu = ShareConnMenu(self.gui)
        self.share_conn_menu.aboutToShow.connect(self.set_smartdevice_action_state)
        self.share_conn_menu.toggle_server.connect(self.toggle_content_server)
        self.share_conn_menu.control_smartdevice.connect(self.control_smartdevice)
        connect_lambda(self.share_conn_menu.config_email, self, lambda self:
            self.gui.iactions['Preferences'].do_config(initial_plugin=('Sharing', 'Email'), close_after_initial=True))
        self.qaction.setMenu(self.share_conn_menu)
        self.share_conn_menu.connect_to_folder.connect(self.gui.connect_to_folder)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)

    def set_state(self, device_connected, device):
        self.share_conn_menu.set_state(device_connected, device)

    def build_email_entries(self):
        m = self.gui.iactions['Send To Device'].qaction.menu()
        self.share_conn_menu.build_email_entries(m)

    def content_server_state_changed(self, running):
        self.share_conn_menu.server_state_changed(running)
        if running:
            self.content_server_is_running = True
            self.qaction.setIcon(QIcon.ic('connect_share_on.png'))
        else:
            self.content_server_is_running = False
            self.qaction.setIcon(QIcon.ic('connect_share.png'))

    def toggle_content_server(self):
        if self.gui.content_server is None:
            self.gui.start_content_server()
        else:
            self.gui.content_server.stop()
            self.stopping_msg = info_dialog(self.gui, _('Stopping'),
                    _('Stopping server, this could take up to a minute, please wait...'),
                    show_copy_button=False)
            QTimer.singleShot(1000, self.check_exited)
            self.stopping_msg.exec()

    def check_exited(self):
        if getattr(self.gui.content_server, 'is_running', False):
            QTimer.singleShot(50, self.check_exited)
            return
        self.gui.content_server = None
        self.stopping_msg.accept()

    def control_smartdevice(self):
        dm = self.gui.device_manager
        running = dm.is_running('smartdevice')
        if running:
            dm.stop_plugin('smartdevice')
            if dm.get_option('smartdevice', 'autostart'):
                if not question_dialog(self.gui, _('Disable autostart'),
                        _('Do you want wireless device connections to be'
                            ' started automatically when calibre starts?')):
                    dm.set_option('smartdevice', 'autostart', False)
        else:
            sd_dialog = SmartdeviceDialog(self.gui)
            sd_dialog.exec()
        self.set_smartdevice_action_state()

    def check_smartdevice_menus(self):
        if not self.gui.device_manager.is_enabled('smartdevice'):
            self.share_conn_menu.hide_smartdevice_menus()

    def set_smartdevice_action_state(self):
        from calibre.gui2.dialogs.smartdevice import get_all_ip_addresses
        dm = self.gui.device_manager

        forced_ip = dm.get_option('smartdevice', 'force_ip_address')
        if forced_ip:
            formatted_addresses = forced_ip
            show_port = True
        else:
            all_ips = get_all_ip_addresses()
            if len(all_ips) == 0:
                formatted_addresses = _('Still looking for IP addresses')
                show_port = False
            elif len(all_ips) > 3:
                formatted_addresses = _('Many IP addresses. See Start/Stop dialog.')
                show_port = False
            else:
                formatted_addresses = ' or '.join(get_all_ip_addresses())
                show_port = True

        running = dm.is_running('smartdevice')
        if not running:
            text = self.share_conn_menu.DEVICE_MSGS[0]
        else:
            use_fixed_port = dm.get_option('smartdevice', 'use_fixed_port')
            port_number = dm.get_option('smartdevice', 'port_number')
            if show_port and use_fixed_port:
                text = self.share_conn_menu.DEVICE_MSGS[1]  + ' [%s, port %s]'%(
                                            formatted_addresses, port_number)
            else:
                text = self.share_conn_menu.DEVICE_MSGS[1] + ' [' + formatted_addresses + ']'

        icon = 'green' if running else 'red'
        ac = self.share_conn_menu.control_smartdevice_action
        ac.setIcon(QIcon.ic('dot_%s.png'%icon))
        ac.setText(text)
