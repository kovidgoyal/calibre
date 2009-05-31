#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import cStringIO, sys
from binascii import hexlify, unhexlify

from PyQt4.Qt import QWidget, SIGNAL, QDialog, Qt

from calibre.gui2.wizard.send_email_ui import Ui_Form
from calibre.utils.smtp import config as smtp_prefs
from calibre.gui2.dialogs.test_email_ui import Ui_Dialog as TE_Dialog
from calibre.gui2 import error_dialog, info_dialog

class TestEmail(QDialog, TE_Dialog):

    def __init__(self, pa, parent):
        QDialog.__init__(self, parent)
        TE_Dialog.__init__(self)
        self.setupUi(self)
        opts = smtp_prefs().parse()
        self.test_func = parent.test_email_settings
        self.connect(self.test_button, SIGNAL('clicked(bool)'), self.test)
        self.from_.setText(unicode(self.from_.text())%opts.from_)
        if pa:
            self.to.setText(pa)
        if opts.relay_host:
            self.label.setText(_('Using: %s:%s@%s:%s and %s encryption')%
                    (opts.relay_username, unhexlify(opts.relay_password),
                        opts.relay_host, opts.relay_port, opts.encryption))

    def test(self):
        self.log.setPlainText(_('Sending...'))
        self.test_button.setEnabled(False)
        try:
            tb = self.test_func(unicode(self.to.text()))
            if not tb:
                tb = _('Mail successfully sent')
            self.log.setPlainText(tb)
        finally:
            self.test_button.setEnabled(True)


class SendEmail(QWidget, Ui_Form):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

    def initialize(self, preferred_to_address):
        self.preferred_to_address = preferred_to_address
        opts = smtp_prefs().parse()
        self.smtp_opts = opts
        if opts.from_:
            self.email_from.setText(opts.from_)
        if opts.relay_host:
            self.relay_host.setText(opts.relay_host)
        self.relay_port.setValue(opts.relay_port)
        if opts.relay_username:
            self.relay_username.setText(opts.relay_username)
        if opts.relay_password:
            self.relay_password.setText(unhexlify(opts.relay_password))
        (self.relay_tls if opts.encryption == 'TLS' else self.relay_ssl).setChecked(True)
        self.connect(self.relay_use_gmail, SIGNAL('clicked(bool)'),
                     self.create_gmail_relay)
        self.connect(self.relay_show_password, SIGNAL('stateChanged(int)'),
         lambda
         state:self.relay_password.setEchoMode(self.relay_password.Password if
             state == 0 else self.relay_password.Normal))
        self.connect(self.test_email_button, SIGNAL('clicked(bool)'),
                self.test_email)


    def test_email(self, *args):
        pa = self.preferred_to_address()
        to_set = pa is not None
        if self.set_email_settings(to_set):
          TestEmail(pa, self).exec_()

    def test_email_settings(self, to):
        opts = smtp_prefs().parse()
        from calibre.utils.smtp import sendmail, create_mail
        buf = cStringIO.StringIO()
        oout, oerr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = buf
        tb = None
        try:
            msg = create_mail(opts.from_, to, 'Test mail from calibre',
                    'Test mail from calibre')
            sendmail(msg, from_=opts.from_, to=[to],
                verbose=3, timeout=30, relay=opts.relay_host,
                username=opts.relay_username,
                password=unhexlify(opts.relay_password),
                encryption=opts.encryption, port=opts.relay_port)
        except:
            import traceback
            tb = traceback.format_exc()
            tb += '\n\nLog:\n' + buf.getvalue()
        finally:
            sys.stdout, sys.stderr = oout, oerr
        return tb

    def create_gmail_relay(self, *args):
        self.relay_username.setText('@gmail.com')
        self.relay_password.setText('')
        self.relay_host.setText('smtp.gmail.com')
        self.relay_port.setValue(587)
        self.relay_tls.setChecked(True)

        info_dialog(self, _('Finish gmail setup'),
            _('Dont forget to enter your gmail username and password')).exec_()
        self.relay_username.setFocus(Qt.OtherFocusReason)
        self.relay_username.setCursorPosition(0)

    def set_email_settings(self, to_set):
        from_ = unicode(self.email_from.text()).strip()
        if to_set and not from_:
            error_dialog(self, _('Bad configuration'),
                         _('You must set the From email address')).exec_()
            return False
        username = unicode(self.relay_username.text()).strip()
        password = unicode(self.relay_password.text()).strip()
        host = unicode(self.relay_host.text()).strip()
        if host and not (username and password):
            error_dialog(self, _('Bad configuration'),
                         _('You must set the username and password for '
                           'the mail server.')).exec_()
            return False
        conf = smtp_prefs()
        conf.set('from_', from_)
        conf.set('relay_host', host if host else None)
        conf.set('relay_port', self.relay_port.value())
        conf.set('relay_username', username if username else None)
        conf.set('relay_password', hexlify(password))
        conf.set('encryption', 'TLS' if self.relay_tls.isChecked() else 'SSL')
        return True



