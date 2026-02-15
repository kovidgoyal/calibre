#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QIcon

from calibre.gui2.dialogs.message_box import MessageBox


class OAuthReauthMessage(MessageBox):

    def __init__(self, parent=None, title=None, provider=None):
        pname = {'gmail': 'Google', 'outlook': 'Microsoft'}.get(provider, provider or _('email provider'))
        msg = _(
            '<h3>Email authorization expired</h3>'
            '<p>Your {0} authorization has expired or been revoked. '
            'This can happen if you changed your password, revoked access, '
            'or the authorization expired due to inactivity.</p>'
            '<p>Click <b>Re-authorize</b> to set up authorization for email again.</p>'
        ).format(pname)
        if title:
            msg = _('<p>Failed to email: {0}</p>').format(title) + msg

        super().__init__(
            MessageBox.QUESTION, _('Email authorization required'), msg,
            parent=parent, show_copy_button=False, q_icon=QIcon.ic('dialog_warning.png'),
            yes_text=_('Re-&authorize'), yes_icon=QIcon.ic('config.png'), no_text=_('&Close'),
        )
        self.accepted.connect(show_email_preferences)


def show_email_preferences():
    from calibre.gui2.ui import get_gui
    if gui := get_gui():
        try:
            gui.iactions['Preferences'].do_config(
                initial_plugin=('Sharing', 'Email'), close_after_initial=True)
        except Exception:
            pass


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = OAuthReauthMessage(title='Test Book', provider='gmail')
    d.exec()
