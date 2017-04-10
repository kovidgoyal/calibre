#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time

from PyQt5.Qt import (
    QCheckBox, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QSize, Qt,
    QTabWidget, QTimer, QUrl, QVBoxLayout, QWidget, pyqtSignal, QHBoxLayout,
    QPushButton
)

from calibre import as_unicode
from calibre.gui2 import (
    Dispatcher, config, error_dialog, info_dialog, open_url, warning_dialog
)
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.srv.opts import server_config, options


class MainTab(QWidget):

    changed_signal = pyqtSignal()
    start_server = pyqtSignal()
    stop_server = pyqtSignal()
    test_server = pyqtSignal()
    show_logs = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_(
            'calibre contains an internet server that allows you to'
            ' access your book collection using a browser from anywhere'
            ' in the world. Any changes to the settings will only take'
            ' effect after a server restart.'))
        la.setWordWrap(True)
        l.addWidget(la)
        l.addSpacing(10)
        self.opt_auth = cb = QCheckBox(_('Require username/password to access the content server'))
        l.addWidget(cb)
        self.auth_desc = la = QLabel(self)
        la.setStyleSheet('QLabel { font-size: smaller }')
        la.setWordWrap(True)
        l.addSpacing(25)
        self.opt_autolaunch_server = al = QCheckBox(_('Run server &automatically when calibre starts'))
        l.addWidget(al)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        for text, name in [(_('&Start server'), 'start_server'), (_('St&op server'), 'stop_server'),
                           (_('&Test server'), 'test_server'), (_('Show server &logs'), 'show_logs')]:
            b = QPushButton(text)
            b.clicked.connect(getattr(self, name).emit)
            setattr(self, name + '_button', b)
            if name == 'show_logs':
                h.addStretch(10)
            h.addWidget(b)

    def genesis(self):
        opts = server_config()
        self.opt_auth.setChecked(opts.auth)
        self.opt_auth.stateChanged.connect(self.auth_changed)
        self.change_auth_desc()
        self.update_button_state()

    def change_auth_desc(self):
        self.auth_desc.setText(
            _('Remember to create some user accounts in the "Users" tab') if self.opt_auth.isChecked() else
            _('Requiring a username/password prevents unauthorized people from'
              ' accessing your calibre library. It is also needed for some features'
              ' such as last read position/annotation syncing and making'
              ' changes to the library.')
        )

    def auth_changed(self):
        self.changed_signal.emit()
        self.change_auth_desc()

    def restore_defaults(self):
        self.auth_changed.setChecked(options['auth'].default)

    def update_button_state(self):
        gui = self.parent().gui
        is_running = gui.content_server is not None and gui.content_server.is_running
        self.start_server_button.setEnabled(not is_running)
        self.stop_server_button.setEnabled(is_running)
        self.test_server_button.setEnabled(is_running)


class ConfigWidget(ConfigWidgetBase):

    def __init__(self, *args, **kw):
        ConfigWidgetBase.__init__(self, *args, **kw)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.tabs_widget = t = QTabWidget(self)
        self.main_tab = m = MainTab(self)
        t.addTab(m, _('Main'))
        m.start_server.connect(self.start_server)
        m.stop_server.connect(self.stop_server)
        m.test_server.connect(self.test_server)
        m.show_logs.connect(self.view_server_logs)
        self.opt_autolaunch_server = m.opt_autolaunch_server
        for tab in self.tabs:
            if hasattr(tab, 'changed_signal'):
                tab.changed_signal.connect(self.changed_signal.emit)

    @property
    def tabs(self):
        return (self.tabs_widget.widget(i) for i in range(self.tabs_widget.count()))

    @property
    def server(self):
        return self.gui.server

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        for tab in self.tabs:
            if hasattr(tab, 'restore_defaults'):
                tab.restore_defaults()

    def genesis(self, gui):
        self.gui = gui
        for tab in self.tabs:
            tab.genesis()

        r = self.register
        r('autolaunch_server', config)

    def start_server(self):
        ConfigWidgetBase.commit(self)
        self.setCursor(Qt.BusyCursor)
        try:
            self.gui.start_content_server(check_started=False)
            while (not self.gui.content_server.is_running and
                    self.gui.content_server.exception is None):
                time.sleep(0.1)
            if self.gui.content_server.exception is not None:
                error_dialog(self, _('Failed to start content server'),
                        as_unicode(self.gui.content_server.exception)).exec_()
                return
            self.main_tab.update_button_state()
        finally:
            self.unsetCursor()

    def stop_server(self):
        self.gui.content_server.threaded_exit()
        self.stopping_msg = info_dialog(self, _('Stopping'),
                _('Stopping server, this could take up to a minute, please wait...'),
                show_copy_button=False)
        QTimer.singleShot(500, self.check_exited)
        self.stopping_msg.exec_()

    def check_exited(self):
        if getattr(self.gui.content_server, 'is_running', False):
            QTimer.singleShot(20, self.check_exited)
            return

        self.gui.content_server = None
        self.main_tab.update_button_state()
        self.stopping_msg.accept()

    def test_server(self):
        prefix = unicode(self.opt_url_prefix.text()).strip()
        open_url(QUrl('http://127.0.0.1:'+str(self.opt_port.value())+prefix))

    def view_server_logs(self):
        from calibre.srv.embedded import log_paths
        log_error_file, log_access_file = log_paths()
        d = QDialog(self)
        d.resize(QSize(800, 600))
        layout = QVBoxLayout()
        d.setLayout(layout)
        layout.addWidget(QLabel(_('Error log:')))
        el = QPlainTextEdit(d)
        layout.addWidget(el)
        try:
            el.setPlainText(lopen(log_error_file, 'rb').read().decode('utf8', 'replace'))
        except EnvironmentError:
            el.setPlainText('No error log found')
        layout.addWidget(QLabel(_('Access log:')))
        al = QPlainTextEdit(d)
        layout.addWidget(al)
        try:
            al.setPlainText(lopen(log_access_file, 'rb').read().decode('utf8', 'replace'))
        except EnvironmentError:
            al.setPlainText('No access log found')
        bx = QDialogButtonBox(QDialogButtonBox.Ok)
        layout.addWidget(bx)
        bx.accepted.connect(d.accept)
        d.show()

    def commit(self):
        ConfigWidgetBase.commit(self)
        warning_dialog(self, _('Restart needed'),
                _('You need to restart the server for changes to'
                    ' take effect'), show=True)
        return False

    def refresh_gui(self, gui):
        gui.content_server = self.server
        if gui.content_server is not None:
            gui.content_server.state_callback = \
                Dispatcher(gui.iactions['Connect Share'].content_server_state_changed)
            gui.content_server.state_callback(gui.content_server.is_running)


if __name__ == '__main__':
    from PyQt5.Qt import QApplication
    app = QApplication([])
    test_widget('Sharing', 'Server')
