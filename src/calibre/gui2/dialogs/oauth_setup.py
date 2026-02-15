#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial

from qt.core import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QIcon,
    QLabel,
    QStackedLayout,
    Qt,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
    sip,
)

from calibre.gui2 import error_dialog


class OAuth2SetupDialog(QDialog):

    GMAIL_DOMAINS = ('@gmail.com', '@googlemail.com')
    OUTLOOK_DOMAINS = ('@outlook.com', '@hotmail.com', '@live.com', '@msn.com')
    flow_finished = pyqtSignal(object, str)  # tokens, error_msg

    def __init__(self, parent, provider='gmail', email=''):
        super().__init__(parent)
        self.setWindowTitle(_('Setup authentication'))
        self.resize(550, 400)
        self.tokens = None
        self.email_address = email
        from calibre.utils.oauth2 import get_available_providers
        self.available_providers = get_available_providers()
        self.provider, self.provider_detected = self._detect_provider(email, provider)
        self.flow_finished.connect(self.on_flow_finish, type=Qt.ConnectionType.QueuedConnection)
        self.setup_ui()

    def _detect_provider(self, email, fallback='gmail'):
        from calibre.utils.oauth2 import is_provider_available
        available_names = [p[0] for p in self.available_providers]
        email_lower = email.lower()
        if any(email_lower.endswith(d) for d in self.GMAIL_DOMAINS):
            if is_provider_available('gmail'):
                return 'gmail', True
        elif any(email_lower.endswith(d) for d in self.OUTLOOK_DOMAINS):
            if is_provider_available('outlook'):
                return 'outlook', True
        if fallback in available_names:
            return fallback, False
        if available_names:
            return available_names[0], False
        return fallback, False

    def setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(_('<h3>Setup OAuth 2.0 authentication</h3>'
            '<p>OAuth 2.0 is the recommended authentication method for Gmail and Outlook. '
            'It is more secure than using passwords.'))
        header.setWordWrap(True)
        layout.addWidget(header)
        self.stack = s = QStackedLayout()
        layout.addLayout(s)
        self.info_widget = w = QWidget(self)
        s.addWidget(w)
        w.l = l = QVBoxLayout(w)

        provider_group = QGroupBox(_('Email provider'))
        l.addWidget(provider_group)
        provider_layout = QFormLayout(provider_group)
        self.provider_combo = QComboBox()
        for provider_id, provider_display in self.available_providers:
            self.provider_combo.addItem(provider_display, provider_id)
        idx = self.provider_combo.findData(self.provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)

        if self.provider_detected:
            provider_name = {'gmail': 'Gmail', 'outlook': 'Outlook'}.get(self.provider, self.provider)
            self.provider_label = QLabel(f'<b>{provider_name}</b>')
            provider_layout.addRow(_('Provider:'), self.provider_label)
            self.provider_combo.hide()
        elif len(self.available_providers) > 1:
            self.provider_note = QLabel(_('<i>Could not detect provider from email domain.</i>'))
            self.provider_note.setWordWrap(True)
            provider_layout.addRow(self.provider_note)
            provider_layout.addRow(_('Provider:'), self.provider_combo)
        elif len(self.available_providers) == 1:
            provider_name = self.available_providers[0][1]
            self.provider_label = QLabel(f'<b>{provider_name}</b>')
            provider_layout.addRow(_('Provider:'), self.provider_label)
            self.provider_combo.hide()
        l.addWidget(provider_group)

        instructions_group = QGroupBox(_('Instructions'))
        instructions_layout = QVBoxLayout(instructions_group)
        instructions = QTextBrowser()
        instructions.setOpenExternalLinks(False)
        instructions.setMaximumHeight(120)
        instructions.setHtml(_('<ol>'
            '<li>Click "Authorize" below.</li>'
            "<li>Your web browser will open to the provider's login page.</li>"
            '<li>Sign in and grant calibre permission to send email.</li>'
            '<li>The browser will redirect back automatically.</li>'
            '</ol>'
            '<p><b>Note:</b> Calibre never sees your password.</p>'))
        instructions_layout.addWidget(instructions)
        l.addWidget(instructions_group)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        s.addWidget(self.status_label)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        bb.rejected.connect(self.reject)
        self.authorize_button = b = bb.addButton(_('Authorize'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('drm-unlocked.png'))
        b.clicked.connect(self.start_oauth_flow)
        b.setDefault(True)
        layout.addStretch(10)
        layout.addWidget(bb)
        s.setCurrentIndex(0)

    def get_selected_provider(self):
        return self.provider if self.provider_detected else self.provider_combo.currentData()

    def run_flow(self, provider):
        tokens, err = None, ''
        try:
            from calibre.utils.oauth2 import start_oauth_flow
            tokens = start_oauth_flow(provider)
        except Exception as e:
            err = str(e)
        if not sip.isdeleted(self):
            self.flow_finished.emit(tokens, err)

    def start_oauth_flow(self):
        self.stack.setCurrentIndex(1)
        self.authorize_button.setEnabled(False)
        self.status_label.setText('<p>' +
            _('Waiting for authorization in browser...') + '<br><br>' + _(
                'This window will close automatically if authorization succeeds.'))
        provider = self.get_selected_provider()

        from threading import Thread
        Thread(target=partial(self.run_flow, provider), daemon=True).start()

    def on_flow_finish(self, tokens, error_msg):
        self.tokens = tokens
        if error_msg:
            error_dialog(self, _('Authorization Failed'),
                _('OAuth 2.0 authorization failed. Click "Show details" for details.'), det_msg=error_msg, show=True)
            self.stack.setCurrentIndex(0)
            self.authorize_button.setEnabled(True)
            self.activateWindow()
            self.raise_()
        else:
            self.accept()
            if parent := self.parent():
                parent.activateWindow()
                parent.raise_()

    def reject(self):
        self.flow_finished.disconnect()
        super().reject()

    def get_tokens(self):
        return self.tokens


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = OAuth2SetupDialog(None, provider='gmail', email='test@gmail.com')
    d.exec()
    print('Got tokens:', d.tokens.keys() if d.tokens else 'None')
