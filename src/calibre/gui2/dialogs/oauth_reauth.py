#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QDialog, QDialogButtonBox, QGridLayout, QIcon, QLabel, QPushButton, QSizePolicy, Qt

from calibre.utils.resources import get_image_path as I


class OAuthReauthMessage(QDialog):

    def __init__(self, parent=None, title=None, provider=None):
        QDialog.__init__(self, parent)
        self.gui = parent
        self.setWindowTitle(_('Email Authorization Required'))
        self.setWindowIcon(QIcon(I('mail.png')))

        l = QGridLayout(self)
        self.setLayout(l)

        la = QLabel()
        la.setPixmap(QIcon(I('dialog_warning.png')).pixmap(64, 64))
        la.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        l.addWidget(la, 0, 0, Qt.AlignmentFlag.AlignTop)

        pname = {'gmail': 'Google', 'outlook': 'Microsoft'}.get(provider, provider or 'your email provider')
        msg = _(
            '<h3>Email Authorization Expired</h3>'
            '<p>Your {0} authorization has expired or been revoked. '
            'This can happen if you changed your password, revoked access, '
            'or the authorization expired due to inactivity.</p>'
            '<p>Click <b>Re-authorize</b> to set up email again.</p>'
        ).format(pname)
        if title:
            msg = _('<p>Failed to email: {0}</p>').format(title) + msg

        self.msg = QLabel(msg)
        self.msg.setWordWrap(True)
        l.addWidget(self.msg, 0, 1)

        bb = QDialogButtonBox()
        self.reauth_btn = QPushButton(_('&Re-authorize'))
        self.reauth_btn.setIcon(QIcon(I('config.png')))
        self.reauth_btn.clicked.connect(self.do_reauth)
        bb.addButton(self.reauth_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 1, 0, 1, 2)

        self.resize(450, 250)

    def do_reauth(self):
        self.accept()
        if self.gui is not None:
            try:
                self.gui.iactions['Preferences'].do_config(
                    initial_plugin=('Sharing', 'Email'), close_after_initial=True)
            except Exception:
                pass


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = OAuthReauthMessage(title='Test Book', provider='gmail')
    d.exec()
