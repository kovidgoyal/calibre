#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
from functools import partial
from threading import Thread

from PyQt5.Qt import (
    QWidget, pyqtSignal, QDialog, Qt, QLabel, QLineEdit, QDialogButtonBox,
    QGridLayout, QCheckBox, QIcon, QVBoxLayout, QPushButton, QPlainTextEdit,
    QHBoxLayout)

from calibre import prints
from calibre.gui2.wizard.send_email_ui import Ui_Form
from calibre.utils.smtp import config as smtp_prefs
from calibre.gui2 import error_dialog, question_dialog
from polyglot.builtins import unicode_type
from polyglot.binary import as_hex_unicode, from_hex_unicode
from polyglot.io import PolyglotStringIO


class TestEmail(QDialog):

    test_done = pyqtSignal(object)

    def __init__(self, pa, parent):
        QDialog.__init__(self, parent)
        self.test_func = parent.test_email_settings
        self.setWindowTitle(_("Test email settings"))
        self.setWindowIcon(QIcon(I('config.ui')))
        l = QVBoxLayout(self)
        opts = smtp_prefs().parse()
        self.from_ = la = QLabel(_("Send test mail from %s to:")%opts.from_)
        l.addWidget(la)
        self.to = le = QLineEdit(self)
        if pa:
            self.to.setText(pa)
        self.test_button = b = QPushButton(_('&Test'), self)
        b.clicked.connect(self.start_test)
        self.test_done.connect(self.on_test_done, type=Qt.QueuedConnection)
        self.h = h = QHBoxLayout()
        h.addWidget(le), h.addWidget(b)
        l.addLayout(h)
        if opts.relay_host:
            self.la = la = QLabel(_('Using: %(un)s:%(pw)s@%(host)s:%(port)s and %(enc)s encryption')%
                    dict(un=opts.relay_username, pw=from_hex_unicode(opts.relay_password),
                        host=opts.relay_host, port=opts.relay_port, enc=opts.encryption))
            l.addWidget(la)
        self.log = QPlainTextEdit(self)
        l.addWidget(self.log)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject), bb.accepted.connect(self.accept)
        l.addWidget(bb)

    def start_test(self, *args):
        if not self.to.text().strip():
            return error_dialog(self, _('No email address'), _(
                'No email address to send mail to has been specified. You'
                ' must specify a To: address before running the test.'), show=True)
        self.log.setPlainText(_('Sending email, please wait...'))
        self.test_button.setEnabled(False)
        t = Thread(target=self.run_test, name='TestEmailSending')
        t.daemon = True
        t.start()

    def run_test(self):
        try:
            tb = self.test_func(unicode_type(self.to.text())) or _('Email successfully sent')
        except Exception:
            import traceback
            tb = traceback.format_exc()
        self.test_done.emit(tb)

    def on_test_done(self, txt):
        if self.isVisible():
            self.test_button.setEnabled(True)
            self.log.setPlainText(txt)


class RelaySetup(QDialog):

    def __init__(self, service, parent):
        QDialog.__init__(self, parent)

        self.l = l = QGridLayout()
        self.setLayout(l)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.tl = QLabel(('<p>'+_('Setup sending email using') +
                ' <b>{name}</b><p>' +
            _('If you don\'t have an account, you can sign up for a free {name} email '
            'account at <a href="https://{url}">https://{url}</a>. {extra}')).format(
                **service))
        l.addWidget(self.tl, 0, 0, 3, 0)
        self.tl.setWordWrap(True)
        self.tl.setOpenExternalLinks(True)
        for name, label in (
                ['from_', _('Your %s &email address:')],
                ['username', _('Your %s &username:')],
                ['password', _('Your %s &password:')],
                ):
            la = QLabel(label%service['name'])
            le = QLineEdit(self)
            setattr(self, name, le)
            setattr(self, name+'_label', la)
            r = l.rowCount()
            l.addWidget(la, r, 0)
            l.addWidget(le, r, 1)
            la.setBuddy(le)
            if name == 'password':
                self.ptoggle = QCheckBox(_('&Show password'), self)
                l.addWidget(self.ptoggle, r, 2)
                self.ptoggle.stateChanged.connect(
                        lambda s: self.password.setEchoMode(self.password.Normal if s == Qt.Checked else self.password.Password))
        self.username.setText(service['username'])
        self.password.setEchoMode(self.password.Password)
        self.bl = QLabel('<p>' + _(
            'If you plan to use email to send books to your Kindle, remember to'
            ' add your %s email address to the allowed email addresses in your '
            'Amazon.com Kindle management page.')%service['name'])
        self.bl.setWordWrap(True)
        l.addWidget(self.bl, l.rowCount(), 0, 3, 0)
        l.addWidget(bb, l.rowCount(), 0, 3, 0)
        self.setWindowTitle(_('Setup') + ' ' + service['name'])
        self.resize(self.sizeHint())
        self.service = service

    def accept(self):
        un = unicode_type(self.username.text())
        if self.service.get('at_in_username', False) and '@' not in un:
            return error_dialog(self, _('Incorrect username'),
                    _('%s needs the full email address as your username') %
                    self.service['name'], show=True)
        QDialog.accept(self)


class SendEmail(QWidget, Ui_Form):

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

    def initialize(self, preferred_to_address):
        self.preferred_to_address = preferred_to_address
        opts = smtp_prefs().parse()
        self.smtp_opts = opts
        if opts.from_:
            self.email_from.setText(opts.from_)
        self.email_from.textChanged.connect(self.changed)
        if opts.relay_host:
            self.relay_host.setText(opts.relay_host)
        self.relay_host.textChanged.connect(self.changed)
        self.relay_port.setValue(opts.relay_port)
        self.relay_port.valueChanged.connect(self.changed)
        if opts.relay_username:
            self.relay_username.setText(opts.relay_username)
        self.relay_username.textChanged.connect(self.changed)
        if opts.relay_password:
            self.relay_password.setText(from_hex_unicode(opts.relay_password))
        self.relay_password.textChanged.connect(self.changed)
        getattr(self, 'relay_'+opts.encryption.lower()).setChecked(True)
        self.relay_tls.toggled.connect(self.changed)

        for x in ('gmx', 'hotmail'):
            button = getattr(self, 'relay_use_'+x)
            button.clicked.connect(partial(self.create_service_relay, x))
        self.relay_show_password.stateChanged.connect(
         lambda state : self.relay_password.setEchoMode(
             self.relay_password.Password if
             state == 0 else self.relay_password.Normal))
        self.test_email_button.clicked.connect(self.test_email)

    def changed(self, *args):
        self.changed_signal.emit()

    def test_email(self, *args):
        pa = self.preferred_to_address()
        to_set = pa is not None
        if self.set_email_settings(to_set):
            opts = smtp_prefs().parse()
            if not opts.relay_password or question_dialog(self, _('OK to proceed?'),
                    _('This will display your email password on the screen'
                    '. Is it OK to proceed?'), show_copy_button=False):
                TestEmail(pa, self).exec_()

    def test_email_settings(self, to):
        opts = smtp_prefs().parse()
        from calibre.utils.smtp import sendmail, create_mail
        buf = PolyglotStringIO()
        debug_out = partial(prints, file=buf)
        oout, oerr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = buf
        tb = None
        try:
            msg = create_mail(opts.from_, to, 'Test mail from calibre',
                    'Test mail from calibre')
            sendmail(msg, from_=opts.from_, to=[to],
                verbose=3, timeout=30, relay=opts.relay_host,
                username=opts.relay_username, debug_output=debug_out,
                password=from_hex_unicode(opts.relay_password),
                encryption=opts.encryption, port=opts.relay_port)
        except:
            import traceback
            tb = traceback.format_exc()
            tb += '\n\nLog:\n' + buf.getvalue()
        finally:
            sys.stdout, sys.stderr = oout, oerr
        return tb

    def create_service_relay(self, service, *args):
        service = {
                'gmx': {
                    'name': 'GMX',
                    'relay': 'mail.gmx.com',
                    'port': 587,
                    'username': '@gmx.com',
                    'url': 'www.gmx.com',
                    'extra': _('Before using this account to send mail, you must enable the'
                        ' "Enable access to this account via POP3 and IMAP" option in GMX'
                        ' under More > E-mail Settings > POP3 & IMAP.'),
                    'at_in_username': True,
                },
                'gmail': {
                    'name': 'Gmail',
                    'relay': 'smtp.gmail.com',
                    'port': 587,
                    'username': '@gmail.com',
                    'url': 'www.gmail.com',
                    'extra': _(
                        'Google recently deliberately broke their email sending protocol (SMTP) support in'
                        ' an attempt to force everyone to use their web interface so they can'
                        ' show you more ads. They are trying to claim that SMTP is insecure,'
                        ' that is incorrect and simply an excuse. To use a gmail account'
                        ' you will need to "allow less secure apps" as described'
                        ' <a href="https://support.google.com/accounts/answer/6010255">here</a>.'),
                    'at_in_username': True,
                },
                'hotmail': {
                    'name': 'Hotmail',
                    'relay': 'smtp.live.com',
                    'port': 587,
                    'username': '',
                    'url': 'www.hotmail.com',
                    'extra': _('If you are setting up a new'
                        ' hotmail account, Microsoft requires that you '
                        ' verify your account periodically, before it'
                        ' will let calibre send email.'),
                    'at_in_username': True,
                }
        }[service]
        d = RelaySetup(service, self)
        if d.exec_() != d.Accepted:
            return
        self.relay_username.setText(d.username.text())
        self.relay_password.setText(d.password.text())
        self.email_from.setText(d.from_.text())
        self.relay_host.setText(service['relay'])
        self.relay_port.setValue(service['port'])
        self.relay_tls.setChecked(True)

    def set_email_settings(self, to_set):
        from_ = unicode_type(self.email_from.text()).strip()
        if to_set and not from_:
            error_dialog(self, _('Bad configuration'),
                         _('You must set the From email address')).exec_()
            return False
        username = unicode_type(self.relay_username.text()).strip()
        password = unicode_type(self.relay_password.text()).strip()
        host = unicode_type(self.relay_host.text()).strip()
        enc_method = ('TLS' if self.relay_tls.isChecked() else 'SSL'
                if self.relay_ssl.isChecked() else 'NONE')
        if host:
            # Validate input
            if ((username and not password) or (not username and password)):
                error_dialog(self, _('Bad configuration'),
                            _('You must either set both the username <b>and</b> password for '
                            'the mail server or no username and no password at all.')).exec_()
                return False
            if not (username and password) and not question_dialog(
                    self, _('Are you sure?'),
                    _('No username and password set for mailserver. Most '
                      ' mailservers need a username and password. Are you sure?')):
                return False
        conf = smtp_prefs()
        conf.set('from_', from_)
        conf.set('relay_host', host if host else None)
        conf.set('relay_port', self.relay_port.value())
        conf.set('relay_username', username if username else None)
        conf.set('relay_password', as_hex_unicode(password))
        conf.set('encryption', enc_method)
        return True
