#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import (
    QApplication, QComboBox, QDialog, QEvent, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QProgressDialog, QPushButton, Qt, QTextBrowser, QVBoxLayout,
)

from calibre.gui2 import error_dialog, info_dialog


class OAuth2SetupDialog(QDialog):

    GMAIL_DOMAINS = ('@gmail.com', '@googlemail.com')
    OUTLOOK_DOMAINS = ('@outlook.com', '@hotmail.com', '@live.com', '@msn.com')

    def __init__(self, parent, provider='gmail', email=''):
        super().__init__(parent)
        self.setWindowTitle(_('Setup OAuth 2.0 Authentication'))
        self.resize(550, 400)
        self.tokens = None
        self.email_address = email
        from calibre.utils.oauth2 import get_available_providers
        self.available_providers = get_available_providers()
        self.provider, self.provider_detected = self._detect_provider(email, provider)
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

        header = QLabel(_('<h3>Setup OAuth 2.0 Authentication</h3>'
            '<p>OAuth 2.0 is the recommended authentication method for Gmail and Outlook. '
            'It is more secure than using passwords and does not require app-specific passwords.</p>'))
        header.setWordWrap(True)
        layout.addWidget(header)

        provider_group = QGroupBox(_('Email Provider'))
        provider_layout = QFormLayout(provider_group)
        self.provider_combo = QComboBox()
        for provider_id, provider_display in self.available_providers:
            self.provider_combo.addItem(_(provider_display), provider_id)
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
        layout.addWidget(provider_group)

        instructions_group = QGroupBox(_('Instructions'))
        instructions_layout = QVBoxLayout(instructions_group)
        instructions = QTextBrowser()
        instructions.setOpenExternalLinks(False)
        instructions.setMaximumHeight(120)
        instructions.setHtml(_('<ol>'
            '<li>Click "Authorize" below</li>'
            '<li>Your web browser will open to the provider\'s login page</li>'
            '<li>Sign in and grant calibre permission to send email</li>'
            '<li>The browser will redirect back automatically</li>'
            '</ol>'
            '<p><b>Note:</b> Calibre never sees your password.</p>'))
        instructions_layout.addWidget(instructions)
        layout.addWidget(instructions_group)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.authorize_button = QPushButton(_('Authorize'))
        self.authorize_button.setDefault(True)
        self.authorize_button.clicked.connect(self.start_oauth_flow)
        button_layout.addWidget(self.authorize_button)
        self.cancel_button = QPushButton(_('Cancel'))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def get_selected_provider(self):
        return self.provider if self.provider_detected else self.provider_combo.currentData()

    def start_oauth_flow(self):
        provider = self.get_selected_provider()
        self.authorize_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.status_label.setText(_('Starting authorization...'))

        progress = QProgressDialog(
            _('Waiting for authorization in browser...\n\nThis dialog will close automatically when done.'),
            _('Cancel'), 0, 0, self)
        progress.setWindowTitle(_('OAuth Authorization'))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        from threading import Thread

        class FlowCompleteEvent(QEvent):
            EVENT_TYPE = QEvent.Type(QEvent.registerEventType())
            def __init__(self, success, error_msg):
                super().__init__(self.EVENT_TYPE)
                self.success = success
                self.error_msg = error_msg

        self.FlowCompleteEvent = FlowCompleteEvent

        def run_flow():
            try:
                from calibre.utils.oauth2 import OAuth2Error, start_oauth_flow as do_oauth_flow
                self.tokens = do_oauth_flow(provider)
                QApplication.instance().postEvent(self, FlowCompleteEvent(True, None))
            except OAuth2Error as e:
                QApplication.instance().postEvent(self, FlowCompleteEvent(False, str(e)))
            except Exception as e:
                QApplication.instance().postEvent(self, FlowCompleteEvent(False, str(e)))

        def handle_flow_complete(event):
            progress.close()
            if event.success:
                self.status_label.setText(_('<b style="color: green;">Authorization successful!</b>'))
                info_dialog(self, _('Success'), _('OAuth 2.0 authorization was successful!'), show=True)
                self.accept()
            else:
                self.status_label.setText(_('<b style="color: red;">Authorization failed</b>'))
                self.authorize_button.setEnabled(True)
                self.cancel_button.setEnabled(True)
                error_dialog(self, _('Authorization Failed'),
                    _('OAuth 2.0 authorization failed:\n\n{error}').format(error=event.error_msg or _('Unknown error')), show=True)

        self.handle_flow_complete = handle_flow_complete

        def cancel_flow():
            progress.close()
            self.status_label.setText(_('Authorization cancelled'))
            self.authorize_button.setEnabled(True)
            self.cancel_button.setEnabled(True)

        progress.canceled.connect(cancel_flow)
        Thread(target=run_flow, daemon=True).start()

    def event(self, e):
        if hasattr(self, 'FlowCompleteEvent') and isinstance(e, self.FlowCompleteEvent):
            self.handle_flow_complete(e)
            return True
        return super().event(e)

    def get_tokens(self):
        return self.tokens


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = OAuth2SetupDialog(None, provider='gmail', email='test@gmail.com')
    d.exec()
    print('Got tokens:', d.tokens.keys() if d.tokens else 'None')
