#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>

import errno
import json
import os
import textwrap
import time

import sip
from PyQt5.Qt import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QFrame, QHBoxLayout, QIcon, QLabel, QLineEdit, QListWidget, QPlainTextEdit,
    QPushButton, QScrollArea, QSize, QSizePolicy, QSpinBox, Qt, QTabWidget, QTimer,
    QToolButton, QUrl, QVBoxLayout, QWidget, pyqtSignal
)

from calibre import as_unicode
from calibre.gui2 import (
    choose_files, choose_save_file, config, error_dialog, gprefs, info_dialog,
    open_url, warning_dialog
)
from calibre.gui2.preferences import AbortCommit, ConfigWidgetBase, test_widget
from calibre.srv.code import custom_list_template as default_custom_list_template
from calibre.srv.embedded import custom_list_template
from calibre.srv.library_broker import load_gui_libraries
from calibre.srv.opts import change_settings, options, server_config
from calibre.srv.users import (
    UserManager, create_user_data, validate_password, validate_username
)
from calibre.utils.icu import primary_sort_key

# Advanced {{{


def init_opt(widget, opt, layout):
    widget.name, widget.default_val = opt.name, opt.default
    if opt.longdoc:
        widget.setWhatsThis(opt.longdoc)
        widget.setStatusTip(opt.longdoc)
        widget.setToolTip(textwrap.fill(opt.longdoc))
    layout.addRow(opt.shortdoc + ':', widget)


class Bool(QCheckBox):

    changed_signal = pyqtSignal()

    def __init__(self, name, layout):
        opt = options[name]
        QCheckBox.__init__(self)
        self.stateChanged.connect(self.changed_signal.emit)
        init_opt(self, opt, layout)

    def get(self):
        return self.isChecked()

    def set(self, val):
        self.setChecked(bool(val))


class Int(QSpinBox):

    changed_signal = pyqtSignal()

    def __init__(self, name, layout):
        QSpinBox.__init__(self)
        self.setRange(0, 10000)
        opt = options[name]
        self.valueChanged.connect(self.changed_signal.emit)
        init_opt(self, opt, layout)

    def get(self):
        return self.value()

    def set(self, val):
        self.setValue(int(val))


class Float(QDoubleSpinBox):

    changed_signal = pyqtSignal()

    def __init__(self, name, layout):
        QDoubleSpinBox.__init__(self)
        self.setRange(0, 10000)
        self.setDecimals(1)
        opt = options[name]
        self.valueChanged.connect(self.changed_signal.emit)
        init_opt(self, opt, layout)

    def get(self):
        return self.value()

    def set(self, val):
        self.setValue(float(val))


class Text(QLineEdit):

    changed_signal = pyqtSignal()

    def __init__(self, name, layout):
        QLineEdit.__init__(self)
        self.setClearButtonEnabled(True)
        opt = options[name]
        self.textChanged.connect(self.changed_signal.emit)
        init_opt(self, opt, layout)

    def get(self):
        return self.text().strip() or None

    def set(self, val):
        self.setText(type(u'')(val or ''))


class Path(QWidget):

    changed_signal = pyqtSignal()

    def __init__(self, name, layout):
        QWidget.__init__(self)
        self.dname = name
        opt = options[name]
        self.l = l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.text = t = QLineEdit(self)
        t.setClearButtonEnabled(True)
        t.textChanged.connect(self.changed_signal.emit)
        l.addWidget(t)

        self.b = b = QToolButton(self)
        l.addWidget(b)
        b.setIcon(QIcon(I('document_open.png')))
        b.setToolTip(_("Browse for the file"))
        b.clicked.connect(self.choose)
        init_opt(self, opt, layout)

    def get(self):
        return self.text.text().strip() or None

    def set(self, val):
        self.text.setText(type(u'')(val or ''))

    def choose(self):
        ans = choose_files(self, 'choose_path_srv_opts_' + self.dname, _('Choose a file'), select_only_single_file=True)
        if ans:
            self.set(ans[0])


class Choices(QComboBox):

    changed_signal = pyqtSignal()

    def __init__(self, name, layout):
        QComboBox.__init__(self)
        self.setEditable(False)
        opt = options[name]
        self.choices = opt.choices
        tuple(map(self.addItem, opt.choices))
        self.currentIndexChanged.connect(self.changed_signal.emit)
        init_opt(self, opt, layout)

    def get(self):
        return self.currentText()

    def set(self, val):
        if val in self.choices:
            self.setCurrentText(val)
        else:
            self.setCurrentIndex(0)


class AdvancedTab(QWidget):

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(l.AllNonFixedFieldsGrow)
        self.widgets = []
        self.widget_map = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for name in sorted(options, key=lambda n: options[n].shortdoc.lower()):
            if name in ('auth', 'port', 'allow_socket_preallocation', 'userdb'):
                continue
            opt = options[name]
            if opt.choices:
                w = Choices
            elif isinstance(opt.default, bool):
                w = Bool
            elif isinstance(opt.default, (int, long)):
                w = Int
            elif isinstance(opt.default, float):
                w = Float
            else:
                w = Text
                if name in ('ssl_certfile', 'ssl_keyfile'):
                    w = Path
            w = w(name, l)
            setattr(self, 'opt_' + name, w)
            self.widgets.append(w)
            self.widget_map[name] = w

    def genesis(self):
        opts = server_config()
        for w in self.widgets:
            w.set(getattr(opts, w.name))
            w.changed_signal.connect(self.changed_signal.emit)

    def restore_defaults(self):
        for w in self.widgets:
            w.set(w.default_val)

    def get(self, name):
        return self.widget_map[name].get()

    @property
    def settings(self):
        return {w.name: w.get() for w in self.widgets}

    @property
    def has_ssl(self):
        return bool(self.get('ssl_certfile')) and bool(self.get('ssl_keyfile'))

# }}}


class MainTab(QWidget):  # {{{

    changed_signal = pyqtSignal()
    start_server = pyqtSignal()
    stop_server = pyqtSignal()
    test_server = pyqtSignal()
    show_logs = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(
            _(
                'calibre contains an internet server that allows you to'
                ' access your book collection using a browser from anywhere'
                ' in the world. Any changes to the settings will only take'
                ' effect after a server restart.'
            )
        )
        la.setWordWrap(True)
        l.addWidget(la)
        l.addSpacing(10)
        self.fl = fl = QFormLayout()
        l.addLayout(fl)
        self.opt_port = sb = QSpinBox(self)
        if options['port'].longdoc:
            sb.setToolTip(options['port'].longdoc)
        sb.setRange(1, 65535)
        sb.valueChanged.connect(self.changed_signal.emit)
        fl.addRow(options['port'].shortdoc + ':', sb)
        l.addSpacing(25)
        self.opt_auth = cb = QCheckBox(
            _('Require &username and password to access the content server')
        )
        l.addWidget(cb)
        self.auth_desc = la = QLabel(self)
        la.setStyleSheet('QLabel { font-size: small; font-style: italic }')
        la.setWordWrap(True)
        l.addWidget(la)
        l.addSpacing(25)
        self.opt_autolaunch_server = al = QCheckBox(
            _('Run server &automatically when calibre starts')
        )
        l.addWidget(al)
        l.addSpacing(25)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        for text, name in [(_('&Start server'),
                            'start_server'), (_('St&op server'), 'stop_server'),
                           (_('&Test server'),
                            'test_server'), (_('Show server &logs'), 'show_logs')]:
            b = QPushButton(text)
            b.clicked.connect(getattr(self, name).emit)
            setattr(self, name + '_button', b)
            if name == 'show_logs':
                h.addStretch(10)
            h.addWidget(b)
        self.ip_info = QLabel(self)
        self.update_ip_info()
        from calibre.gui2.ui import get_gui
        get_gui().iactions['Connect Share'].share_conn_menu.server_state_changed_signal.connect(self.update_ip_info)
        l.addSpacing(10)
        l.addWidget(self.ip_info)
        l.addStretch(10)

    def update_ip_info(self):
        from calibre.gui2.ui import get_gui
        t = get_gui().iactions['Connect Share'].share_conn_menu.ip_text
        t = t.strip().strip('[]')
        self.ip_info.setText(_('Content server listening at: %s') % t)

    def genesis(self):
        opts = server_config()
        self.opt_auth.setChecked(opts.auth)
        self.opt_auth.stateChanged.connect(self.auth_changed)
        self.opt_port.setValue(opts.port)
        self.change_auth_desc()
        self.update_button_state()

    def change_auth_desc(self):
        self.auth_desc.setText(
            _('Remember to create some user accounts in the "User accounts" tab')
            if self.opt_auth.isChecked() else _(
                'Requiring a username/password prevents unauthorized people from'
                ' accessing your calibre library. It is also needed for some features'
                ' such as making any changes to the library as well as'
                ' last read position/annotation syncing.'
            )
        )

    def auth_changed(self):
        self.changed_signal.emit()
        self.change_auth_desc()

    def restore_defaults(self):
        self.opt_auth.setChecked(options['auth'].default)
        self.opt_port.setValue(options['port'].default)

    def update_button_state(self):
        from calibre.gui2.ui import get_gui
        gui = get_gui()
        is_running = gui.content_server is not None and gui.content_server.is_running
        self.ip_info.setVisible(is_running)
        self.update_ip_info()
        self.start_server_button.setEnabled(not is_running)
        self.stop_server_button.setEnabled(is_running)
        self.test_server_button.setEnabled(is_running)

    @property
    def settings(self):
        return {'auth': self.opt_auth.isChecked(), 'port': self.opt_port.value()}


# }}}

# Users {{{


class NewUser(QDialog):

    def __init__(self, user_data, parent=None, username=None):
        QDialog.__init__(self, parent)
        self.user_data = user_data
        self.setWindowTitle(
            _('Change password for {}').format(username)
            if username else _('Add new user')
        )
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(l.AllNonFixedFieldsGrow)
        self.uw = u = QLineEdit(self)
        l.addRow(_('&Username:'), u)
        if username:
            u.setText(username)
            u.setReadOnly(True)
        l.addRow(QLabel(_('Set the password for this user')))
        self.p1, self.p2 = p1, p2 = QLineEdit(self), QLineEdit(self)
        l.addRow(_('&Password:'), p1), l.addRow(_('&Repeat password:'), p2)
        for p in p1, p2:
            p.setEchoMode(QLineEdit.PasswordEchoOnEdit)
            p.setMinimumWidth(300)
            if username:
                p.setText(user_data[username]['pw'])
        self.showp = sp = QCheckBox(_('&Show password'))
        sp.stateChanged.connect(self.show_password)
        l.addRow(sp)
        self.bb = bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        l.addRow(bb)
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        (self.uw if not username else self.p1).setFocus(Qt.OtherFocusReason)

    def show_password(self):
        for p in self.p1, self.p2:
            p.setEchoMode(
                QLineEdit.Normal
                if self.showp.isChecked() else QLineEdit.PasswordEchoOnEdit
            )

    @property
    def username(self):
        return self.uw.text().strip()

    @property
    def password(self):
        return self.p1.text()

    def accept(self):
        if not self.uw.isReadOnly():
            un = self.username
            if not un:
                return error_dialog(
                    self,
                    _('Empty username'),
                    _('You must enter a username'),
                    show=True
                )
            if un in self.user_data:
                return error_dialog(
                    self,
                    _('Username already exists'),
                    _(
                        'A user with the username {} already exists. Please choose a different username.'
                    ).format(un),
                    show=True
                )
            err = validate_username(un)
            if err:
                return error_dialog(self, _('Username is not valid'), err, show=True)
        p1, p2 = self.password, self.p2.text()
        if p1 != p2:
            return error_dialog(
                self,
                _('Password do not match'),
                _('The two passwords you entered do not match!'),
                show=True
            )
        if not p1:
            return error_dialog(
                self,
                _('Empty password'),
                _('You must enter a password for this user'),
                show=True
            )
        err = validate_password(p1)
        if err:
            return error_dialog(self, _('Invalid password'), err, show=True)
        return QDialog.accept(self)


class Library(QWidget):

    restriction_changed = pyqtSignal(object, object)

    def __init__(self, name, is_checked=False, path='', restriction='', parent=None, is_first=False, enable_on_checked=True):
        QWidget.__init__(self, parent)
        self.name = name
        self.enable_on_checked = enable_on_checked
        self.l = l = QVBoxLayout(self)
        l.setSizeConstraint(l.SetMinAndMaxSize)
        if not is_first:
            self.border = b = QFrame(self)
            b.setFrameStyle(b.HLine)
            l.addWidget(b)
        self.cw = cw = QCheckBox(name.replace('&', '&&'))
        cw.setStyleSheet('QCheckBox { font-weight: bold }')
        cw.setChecked(is_checked)
        cw.stateChanged.connect(self.state_changed)
        if path:
            cw.setToolTip(path)
        l.addWidget(cw)
        self.la = la = QLabel(_('Further &restrict access to books in this library that match:'))
        l.addWidget(la)
        self.rw = rw = QLineEdit(self)
        rw.setPlaceholderText(_('A search expression'))
        rw.setToolTip(textwrap.fill(_(
            'A search expression. If specified, access will be further restricted'
            ' to only those books that match this expression. For example:'
            ' tags:"=Share"')))
        rw.setText(restriction or '')
        rw.textChanged.connect(self.on_rchange)
        la.setBuddy(rw)
        l.addWidget(rw)
        self.state_changed()

    def state_changed(self):
        c = self.cw.isChecked()
        w = (self.enable_on_checked and c) or (not self.enable_on_checked and not c)
        for x in (self.la, self.rw):
            x.setEnabled(bool(w))

    def on_rchange(self):
        self.restriction_changed.emit(self.name, self.restriction)

    @property
    def is_checked(self):
        return self.cw.isChecked()

    @property
    def restriction(self):
        return self.rw.text().strip()


class ChangeRestriction(QDialog):

    def __init__(self, username, restriction, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Change library access permissions for {}').format(username))
        self.username = username
        self._items = []
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(l.AllNonFixedFieldsGrow)

        self.libraries = t = QWidget(self)
        t.setObjectName('libraries')
        t.l = QVBoxLayout(self.libraries)
        self.atype = a = QComboBox(self)
        a.addItems([_('All libraries'), _('Only the specified libraries'), _('All except the specified libraries')])
        self.library_restrictions = restriction['library_restrictions'].copy()
        if restriction['allowed_library_names']:
            a.setCurrentIndex(1)
            self.items = restriction['allowed_library_names']
        elif restriction['blocked_library_names']:
            a.setCurrentIndex(2)
            self.items = restriction['blocked_library_names']
        else:
            a.setCurrentIndex(0)
        a.currentIndexChanged.connect(self.atype_changed)
        l.addRow(_('Allow access to:'), a)

        self.msg = la = QLabel(self)
        la.setWordWrap(True)
        l.addRow(la)
        self.la = la = QLabel(_('Specify the libraries below:'))
        la.setWordWrap(True)
        self.sa = sa = QScrollArea(self)
        sa.setWidget(t), sa.setWidgetResizable(True)
        l.addRow(la), l.addRow(sa)
        self.atype_changed()

        self.bb = bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        l.addWidget(bb)
        self.items = self.items

    def sizeHint(self):
        return QSize(800, 600)

    def __iter__(self):
        return iter(self._items)

    @property
    def items(self):
        return frozenset(item.name for item in self if item.is_checked)

    def clear(self):
        for c in self:
            self.libraries.l.removeWidget(c)
            c.setParent(None)
            c.restriction_changed.disconnect()
            sip.delete(c)
        self._items = []

    @items.setter
    def items(self, val):
        self.clear()
        checked_libraries = frozenset(val)
        library_paths = load_gui_libraries(gprefs)
        gui_libraries = {os.path.basename(l):l for l in library_paths}
        lchecked_libraries = {l.lower() for l in checked_libraries}
        seen = set()
        items = []
        for x in checked_libraries | set(gui_libraries):
            xl = x.lower()
            if xl not in seen:
                seen.add(xl)
                items.append((x, xl in lchecked_libraries))
        items.sort(key=lambda x: primary_sort_key(x[0]))
        enable_on_checked = self.atype.currentIndex() == 1
        for i, (l, checked) in enumerate(items):
            l = Library(
                l, checked, path=gui_libraries.get(l, ''),
                restriction=self.library_restrictions.get(l.lower(), ''),
                parent=self.libraries, is_first=i == 0,
                enable_on_checked=enable_on_checked
            )
            l.restriction_changed.connect(self.restriction_changed)
            self.libraries.l.addWidget(l)
            self._items.append(l)

    def restriction_changed(self, name, val):
        name = name.lower()
        self.library_restrictions[name] = val

    @property
    def restriction(self):
        ans = {'allowed_library_names': frozenset(), 'blocked_library_names': frozenset(), 'library_restrictions': {}}
        if self.atype.currentIndex() != 0:
            k = ['allowed_library_names', 'blocked_library_names'][self.atype.currentIndex() - 1]
            ans[k] = self.items
            ans['library_restrictions'] = self.library_restrictions
        return ans

    def accept(self):
        if self.atype.currentIndex() != 0 and not self.items:
            return error_dialog(self, _('No libraries specified'), _(
                'You have not specified any libraries'), show=True)
        return QDialog.accept(self)

    def atype_changed(self):
        ci = self.atype.currentIndex()
        sheet = ''
        if ci == 0:
            m = _('<b>{} is allowed access to all libraries')
            self.libraries.setEnabled(False), self.la.setEnabled(False)
        else:
            if ci == 1:
                m = _('{} is allowed access only to the libraries whose names'
                      ' <b>match</b> one of the names specified below.')
            else:
                m = _('{} is allowed access to all libraries, <b>except</b> those'
                      ' whose names match one of the names specified below.')
                sheet += 'QWidget#libraries { background-color: #FAE7B5}'
            self.libraries.setEnabled(True), self.la.setEnabled(True)
            self.items = self.items
        self.msg.setText(m.format(self.username))
        self.libraries.setStyleSheet(sheet)


class User(QWidget):

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.username_label = la = QLabel('')
        l.addWidget(la)
        self.cpb = b = QPushButton(_('Change &password'))
        l.addWidget(b)
        b.clicked.connect(self.change_password)
        self.ro_text = _('Allow {} to make &changes (i.e. grant write access)?')
        self.rw = rw = QCheckBox(self)
        rw.setToolTip(
            _(
                'If enabled, allows the user to make changes to the library.'
                ' Adding books/deleting books/editing metadata, etc.'
            )
        )
        rw.stateChanged.connect(self.readonly_changed)
        l.addWidget(rw)
        self.access_label = la = QLabel(self)
        l.addWidget(la), la.setWordWrap(True)
        self.restrict_button = b = QPushButton(self)
        b.clicked.connect(self.change_restriction)
        l.addWidget(b)

        self.show_user()

    def change_password(self):
        d = NewUser(self.user_data, self, self.username)
        if d.exec_() == d.Accepted:
            self.user_data[self.username]['pw'] = d.password
            self.changed_signal.emit()

    def readonly_changed(self):
        self.user_data[self.username]['readonly'] = not self.rw.isChecked()
        self.changed_signal.emit()

    def update_restriction(self):
        username, user_data = self.username, self.user_data
        r = user_data[username]['restriction']
        if r['allowed_library_names']:
            m = _(
                '{} is currently only allowed to access the libraries named: {}'
            ).format(username, ', '.join(r['allowed_library_names']))
            b = _('Change the allowed libraries')
        elif r['blocked_library_names']:
            m = _(
                '{} is currently not allowed to access the libraries named: {}'
            ).format(username, ', '.join(r['blocked_library_names']))
            b = _('Change the blocked libraries')
        else:
            m = _('{} is currently allowed access to all libraries')
            b = _('Restrict the &libraries {} can access'.format(self.username))
        self.restrict_button.setText(b),
        self.access_label.setText(m.format(username))

    def show_user(self, username=None, user_data=None):
        self.username, self.user_data = username, user_data
        self.cpb.setVisible(username is not None)
        self.username_label.setText(('<h2>' + username) if username else '')
        if username:
            self.rw.setText(self.ro_text.format(username))
            self.rw.setVisible(True)
            self.rw.blockSignals(True), self.rw.setChecked(
                not user_data[username]['readonly']
            ), self.rw.blockSignals(False)
            self.access_label.setVisible(True)
            self.restrict_button.setVisible(True)
            self.update_restriction()
        else:
            self.rw.setVisible(False)
            self.access_label.setVisible(False)
            self.restrict_button.setVisible(False)

    def change_restriction(self):
        d = ChangeRestriction(
            self.username,
            self.user_data[self.username]['restriction'].copy(),
            parent=self
        )
        if d.exec_() == d.Accepted:
            self.user_data[self.username]['restriction'] = d.restriction
            self.update_restriction()
            self.changed_signal.emit()

    def sizeHint(self):
        ans = QWidget.sizeHint(self)
        ans.setWidth(400)
        return ans


class Users(QWidget):

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QHBoxLayout(self)
        self.lp = lp = QVBoxLayout()
        l.addLayout(lp)

        self.h = h = QHBoxLayout()
        lp.addLayout(h)
        self.add_button = b = QPushButton(QIcon(I('plus.png')), _('&Add user'), self)
        b.clicked.connect(self.add_user)
        h.addWidget(b)
        self.remove_button = b = QPushButton(
            QIcon(I('minus.png')), _('&Remove user'), self
        )
        b.clicked.connect(self.remove_user)
        h.addStretch(2), h.addWidget(b)

        self.user_list = w = QListWidget(self)
        w.setSpacing(1)
        w.doubleClicked.connect(self.current_user_activated)
        w.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        lp.addWidget(w)

        self.user_display = u = User(self)
        u.changed_signal.connect(self.changed_signal.emit)
        l.addWidget(u)

    def genesis(self):
        self.user_data = UserManager().user_data
        self.user_list.addItems(sorted(self.user_data, key=primary_sort_key))
        self.user_list.setCurrentRow(0)
        self.user_list.currentItemChanged.connect(self.current_item_changed)
        self.current_item_changed()

    def current_user_activated(self):
        self.user_display.change_password()

    def current_item_changed(self):
        item = self.user_list.currentItem()
        if item is None:
            username = None
        else:
            username = item.text()
        if username not in self.user_data:
            username = None
        self.display_user_data(username)

    def add_user(self):
        d = NewUser(self.user_data, parent=self)
        if d.exec_() == d.Accepted:
            un, pw = d.username, d.password
            self.user_data[un] = create_user_data(pw)
            self.user_list.insertItem(0, un)
            self.user_list.setCurrentRow(0)
            self.display_user_data(un)
            self.changed_signal.emit()

    def remove_user(self):
        u = self.user_list.currentItem()
        if u is not None:
            self.user_list.takeItem(self.user_list.row(u))
            un = u.text()
            self.user_data.pop(un, None)
            self.changed_signal.emit()
            self.current_item_changed()

    def display_user_data(self, username=None):
        self.user_display.show_user(username, self.user_data)


# }}}


class CustomList(QWidget):  # {{{

    changed_signal = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.default_template = default_custom_list_template()
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(l.AllNonFixedFieldsGrow)
        self.la = la = QLabel('<p>' + _(
            'Here you can create a template to control what data is shown when'
            ' using the <i>Custom list</i> mode for the book list'))
        la.setWordWrap(True)
        l.addRow(la)
        self.thumbnail = t = QCheckBox(_('Show a cover &thumbnail'))
        self.thumbnail_height = th = QSpinBox(self)
        th.setSuffix(' px'), th.setRange(60, 600)
        self.entry_height = eh = QLineEdit(self)
        l.addRow(t), l.addRow(_('Thumbnail &height:'), th)
        l.addRow(_('Entry &height:'), eh)
        t.stateChanged.connect(self.changed_signal)
        th.valueChanged.connect(self.changed_signal)
        eh.textChanged.connect(self.changed_signal)
        eh.setToolTip(textwrap.fill(_(
            'The height for each entry. The special value "auto" causes a height to be calculated'
            ' based on the number of lines in the template. Otherwise, use a CSS length, such as'
            ' 100px or 15ex')))
        t.stateChanged.connect(self.thumbnail_state_changed)
        th.setVisible(False)

        self.comments_fields = cf = QLineEdit(self)
        l.addRow(_('&Long text fields:'), cf)
        cf.setToolTip(textwrap.fill(_(
            'A comma separated list of fields that will be added at the bottom of every entry.'
            ' These fields are interpreted as containing HTML, not plain text.')))
        cf.textChanged.connect(self.changed_signal)

        self.la1 = la = QLabel('<p>' + _(
            'The template below will be interpreted as HTML and all {{fields}} will be replaced'
            ' by the actual metadata, if available. You can use {0} as a separator'
            ' to split a line into multiple columns.').format('|||'))
        la.setWordWrap(True)
        l.addRow(la)
        self.template = t = QPlainTextEdit(self)
        l.addRow(t)
        t.textChanged.connect(self.changed_signal)
        self.imex = bb = QDialogButtonBox(self)
        b = bb.addButton(_('&Import template'), bb.ActionRole)
        b.clicked.connect(self.import_template)
        b = bb.addButton(_('E&xport template'), bb.ActionRole)
        b.clicked.connect(self.export_template)
        l.addRow(bb)

    def import_template(self):
        paths = choose_files(self, 'custom-list-template', _('Choose template file'),
            filters=[(_('Template files'), ['json'])], all_files=False, select_only_single_file=True)
        if paths:
            with lopen(paths[0], 'rb') as f:
                raw = f.read()
            self.current_template = self.deserialize(raw)

    def export_template(self):
        path = choose_save_file(
            self, 'custom-list-template', _('Choose template file'),
            filters=[(_('Template files'), ['json'])], initial_filename='custom-list-template.json')
        if path:
            raw = self.serialize(self.current_template)
            with lopen(path, 'wb') as f:
                f.write(raw)

    def thumbnail_state_changed(self):
        is_enabled = bool(self.thumbnail.isChecked())
        for w, x in [(self.thumbnail_height, True), (self.entry_height, False)]:
            w.setVisible(is_enabled is x)
            self.layout().labelForField(w).setVisible(is_enabled is x)

    def genesis(self):
        self.current_template = custom_list_template() or self.default_template

    @property
    def current_template(self):
        return {
            'thumbnail': self.thumbnail.isChecked(),
            'thumbnail_height': self.thumbnail_height.value(),
            'height': self.entry_height.text().strip() or 'auto',
            'comments_fields': [x.strip() for x in self.comments_fields.text().split(',') if x.strip()],
            'lines': [x.strip() for x in self.template.toPlainText().splitlines()]
        }

    @current_template.setter
    def current_template(self, template):
        self.thumbnail.setChecked(bool(template.get('thumbnail')))
        try:
            th = int(template['thumbnail_height'])
        except Exception:
            th = self.default_template['thumbnail_height']
        self.thumbnail_height.setValue(th)
        self.entry_height.setText(template.get('height') or 'auto')
        self.comments_fields.setText(', '.join(template.get('comments_fields') or ()))
        self.template.setPlainText('\n'.join(template.get('lines') or ()))

    def serialize(self, template):
        return json.dumps(template, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=True)

    def deserialize(self, raw):
        return json.loads(raw)

    def restore_defaults(self):
        self.current_template = self.default_template

    def commit(self):
        template = self.current_template
        if template == self.default_template:
            try:
                os.remove(custom_list_template.path)
            except EnvironmentError as err:
                if err.errno != errno.ENOENT:
                    raise
        else:
            raw = self.serialize(template)
            with lopen(custom_list_template.path, 'wb') as f:
                f.write(raw)
        return True

# }}}


class ConfigWidget(ConfigWidgetBase):

    def __init__(self, *args, **kw):
        ConfigWidgetBase.__init__(self, *args, **kw)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.tabs_widget = t = QTabWidget(self)
        l.addWidget(t)
        self.main_tab = m = MainTab(self)
        t.addTab(m, _('&Main'))
        m.start_server.connect(self.start_server)
        m.stop_server.connect(self.stop_server)
        m.test_server.connect(self.test_server)
        m.show_logs.connect(self.view_server_logs)
        self.opt_autolaunch_server = m.opt_autolaunch_server
        self.users_tab = ua = Users(self)
        t.addTab(ua, _('&User accounts'))
        self.advanced_tab = a = AdvancedTab(self)
        sa = QScrollArea(self)
        sa.setWidget(a), sa.setWidgetResizable(True)
        t.addTab(sa, _('&Advanced'))
        self.custom_list_tab = clt = CustomList(self)
        sa = QScrollArea(self)
        sa.setWidget(clt), sa.setWidgetResizable(True)
        t.addTab(sa, _('Book &list template'))
        for tab in self.tabs:
            if hasattr(tab, 'changed_signal'):
                tab.changed_signal.connect(self.changed_signal.emit)

    @property
    def tabs(self):

        def w(x):
            if isinstance(x, QScrollArea):
                x = x.widget()
            return x

        return (
            w(self.tabs_widget.widget(i)) for i in range(self.tabs_widget.count())
        )

    @property
    def server(self):
        return self.gui.content_server

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
        if not self.save_changes():
            return
        self.setCursor(Qt.BusyCursor)
        try:
            self.gui.start_content_server(check_started=False)
            while (not self.server.is_running and self.server.exception is None):
                time.sleep(0.1)
            if self.server.exception is not None:
                error_dialog(
                    self,
                    _('Failed to start content server'),
                    as_unicode(self.gui.content_server.exception)
                ).exec_()
                self.gui.content_server = None
                return
            self.main_tab.update_button_state()
        finally:
            self.unsetCursor()

    def stop_server(self):
        self.server.stop()
        self.stopping_msg = info_dialog(
            self,
            _('Stopping'),
            _('Stopping server, this could take up to a minute, please wait...'),
            show_copy_button=False
        )
        QTimer.singleShot(500, self.check_exited)
        self.stopping_msg.exec_()

    def check_exited(self):
        if getattr(self.server, 'is_running', False):
            QTimer.singleShot(20, self.check_exited)
            return

        self.gui.content_server = None
        self.main_tab.update_button_state()
        self.stopping_msg.accept()

    def test_server(self):
        prefix = self.advanced_tab.get('url_prefix') or ''
        protocol = 'https' if self.advanced_tab.has_ssl else 'http'
        lo = self.advanced_tab.get('listen_on') or '0.0.0.0'
        lo = {'0.0.0.0': '127.0.0.1', '::':'::1'}.get(lo)
        url = '{protocol}://{interface}:{port}{prefix}'.format(
            protocol=protocol, interface=lo,
            port=self.main_tab.opt_port.value(), prefix=prefix)
        open_url(QUrl(url))

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
            el.setPlainText(
                lopen(log_error_file, 'rb').read().decode('utf8', 'replace')
            )
        except EnvironmentError:
            el.setPlainText(_('No error log found'))
        layout.addWidget(QLabel(_('Access log:')))
        al = QPlainTextEdit(d)
        layout.addWidget(al)
        try:
            al.setPlainText(
                lopen(log_access_file, 'rb').read().decode('utf8', 'replace')
            )
        except EnvironmentError:
            al.setPlainText(_('No access log found'))
        loc = QLabel(_('The server log files are in: {}').format(os.path.dirname(log_error_file)))
        loc.setWordWrap(True)
        layout.addWidget(loc)
        bx = QDialogButtonBox(QDialogButtonBox.Ok)
        layout.addWidget(bx)
        bx.accepted.connect(d.accept)
        d.show()

    def save_changes(self):
        settings = {}
        for tab in self.tabs:
            settings.update(getattr(tab, 'settings', {}))
        users = self.users_tab.user_data
        if settings['auth']:
            if not users:
                error_dialog(
                    self,
                    _('No users specified'),
                    _(
                        'You have turned on the setting to require passwords to access'
                        ' the content server, but you have not created any user accounts.'
                        ' Create at least one user account in the "User accounts" tab to proceed.'
                    ),
                    show=True
                )
                self.tabs_widget.setCurrentWidget(self.users_tab)
                return False
        if not self.custom_list_tab.commit():
            return False
        ConfigWidgetBase.commit(self)
        change_settings(**settings)
        UserManager().user_data = users
        return True

    def commit(self):
        if not self.save_changes():
            raise AbortCommit()
        warning_dialog(
            self,
            _('Restart needed'),
            _('You need to restart the server for changes to'
              ' take effect'),
            show=True
        )
        return False

    def refresh_gui(self, gui):
        if self.server:
            self.server.user_manager.refresh()
            self.server.ctx.custom_list_template = custom_list_template()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Sharing', 'Server')
