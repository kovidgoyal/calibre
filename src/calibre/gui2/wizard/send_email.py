#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import cStringIO, sys
from binascii import hexlify, unhexlify
from functools import partial

from PyQt4.Qt import QWidget, pyqtSignal, QDialog, Qt, QLabel, \
        QLineEdit, QDialogButtonBox, QGridLayout, QCheckBox

from calibre.gui2.wizard.send_email_ui import Ui_Form
from calibre.utils.smtp import config as smtp_prefs
from calibre.gui2.dialogs.test_email_ui import Ui_Dialog as TE_Dialog
from calibre.gui2 import error_dialog

class TestEmail(QDialog, TE_Dialog):

    def __init__(self, pa, parent):
        QDialog.__init__(self, parent)
        TE_Dialog.__init__(self)
        self.setupUi(self)
        opts = smtp_prefs().parse()
        self.test_func = parent.test_email_settings
        self.test_button.clicked.connect(self.test)
        self.from_.setText(unicode(self.from_.text())%opts.from_)
        if pa:
            self.to.setText(pa)
        if opts.relay_host:
            self.label.setText(_('Using: %s:%s@%s:%s and %s encryption')%
                    (opts.relay_username, unhexlify(opts.relay_password),
                        opts.relay_host, opts.relay_port, opts.encryption))

    def test(self, *args):
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
            self.relay_password.setText(unhexlify(opts.relay_password))
        self.relay_password.textChanged.connect(self.changed)
        getattr(self, 'relay_'+opts.encryption.lower()).setChecked(True)
        self.relay_tls.toggled.connect(self.changed)

        for x in ('gmail', 'hotmail'):
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

    def create_service_relay(self, service, *args):
        service = {
                'gmail': {
                    'name': 'Gmail',
                    'relay': 'smtp.gmail.com',
                    'port': 587,
                    'username': '@gmail.com',
                    'url': 'www.gmail.com',
                    'extra': ''
                },
                'hotmail': {
                    'name': 'Hotmail',
                    'relay': 'smtp.live.com',
                    'port': 587,
                    'username': '',
                    'url': 'www.hotmail.com',
                    'extra': _('If you are setting up a new'
                        ' hotmail account, you must log in to it '
                        ' once before you will be able to send mails.'),
                }
        }[service]
        d = QDialog(self)
        l = QGridLayout()
        d.setLayout(l)
        bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        d.tl = QLabel(('<p>'+_('Setup sending email using') +
                ' <b>{name}</b><p>' +
            _('If you don\'t have an account, you can sign up for a free {name} email '
            'account at <a href="http://{url}">http://{url}</a>. {extra}')).format(
                **service))
        l.addWidget(d.tl, 0, 0, 3, 0)
        d.tl.setWordWrap(True)
        d.tl.setOpenExternalLinks(True)
        for name, label in (
                ['from_', _('Your %s &email address:')],
                ['username', _('Your %s &username:')],
                ['password', _('Your %s &password:')],
                ):
            la = QLabel(label%service['name'])
            le = QLineEdit(d)
            setattr(d, name, le)
            setattr(d, name+'_label', la)
            r = l.rowCount()
            l.addWidget(la, r, 0)
            l.addWidget(le, r, 1)
            la.setBuddy(le)
            if name == 'password':
                d.ptoggle = QCheckBox(_('&Show password'), d)
                l.addWidget(d.ptoggle, r, 2)
                d.ptoggle.stateChanged.connect(
                        lambda s: d.password.setEchoMode(d.password.Normal if s
                            == Qt.Checked else d.password.Password))
        d.username.setText(service['username'])
        d.password.setEchoMode(d.password.Password)
        d.bl = QLabel('<p>' + _(
            'If you plan to use email to send books to your Kindle, remember to'
            ' add the your %s email address to the allowed email addresses in your '
            'Amazon.com Kindle management page.')%service['name'])
        d.bl.setWordWrap(True)
        l.addWidget(d.bl, l.rowCount(), 0, 3, 0)
        l.addWidget(bb, l.rowCount(), 0, 3, 0)
        d.setWindowTitle(_('Setup') + ' ' + service['name'])
        d.resize(d.sizeHint())
        bb.setVisible(True)
        if d.exec_() != d.Accepted:
            return
        self.relay_username.setText(d.username.text())
        self.relay_password.setText(d.password.text())
        self.email_from.setText(d.from_.text())
        self.relay_host.setText(service['relay'])
        self.relay_port.setValue(service['port'])
        self.relay_tls.setChecked(True)

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
        conf.set('encryption', 'TLS' if self.relay_tls.isChecked() else 'SSL'
                if self.relay_ssl.isChecked() else 'NONE')
        return True



