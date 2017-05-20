#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, re

from PyQt5.Qt import QAbstractTableModel, QFont, Qt


from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
        AbortCommit
from calibre.gui2.preferences.email_ui import Ui_Form
from calibre.utils.config import ConfigProxy
from calibre.utils.icu import numeric_sort_key
from calibre.gui2 import gprefs
from calibre.utils.smtp import config as smtp_prefs


class EmailAccounts(QAbstractTableModel):  # {{{

    def __init__(self, accounts, subjects, aliases={}, tags={}):
        QAbstractTableModel.__init__(self)
        self.accounts = accounts
        self.subjects = subjects
        self.aliases = aliases
        self.tags = tags
        self.sorted_on = (0, True)
        self.account_order = self.accounts.keys()
        self.do_sort()
        self.headers  = map(unicode, [_('Email'), _('Formats'), _('Subject'),
            _('Auto send'), _('Alias'), _('Auto send only tags')])
        self.default_font = QFont()
        self.default_font.setBold(True)
        self.default_font = (self.default_font)
        self.tooltips =[None] + list(map(unicode, map(textwrap.fill,
            [_('Formats to email. The first matching format will be sent.'),
             _('Subject of the email to use when sending. When left blank '
               'the title will be used for the subject. Also, the same '
               'templates used for "Save to disk" such as {title} and '
               '{author_sort} can be used here.'),
             '<p>'+_('If checked, downloaded news will be automatically '
                     'mailed to this email address '
                     '(provided it is in one of the listed formats and has not been filtered by tags).'),
             _('Friendly name to use for this email address'),
             _('If specified, only news with one of these tags will be sent to'
               ' this email address. All news downloads have their title as a'
               ' tag, so you can use this to easily control which news downloads'
               ' are sent to this email address.')
             ])))

    def do_sort(self):
        col = self.sorted_on[0]
        if col == 0:
            def key(account_key):
                return numeric_sort_key(account_key)
        elif col == 1:
            def key(account_key):
                return numeric_sort_key(self.accounts[account_key][0] or '')
        elif col == 2:
            def key(account_key):
                return numeric_sort_key(self.subjects.get(account_key) or '')
        elif col == 3:
            def key(account_key):
                return numeric_sort_key(type(u'')(self.accounts[account_key][0]) or '')
        elif col == 4:
            def key(account_key):
                return numeric_sort_key(self.aliases.get(account_key) or '')
        elif col == 5:
            def key(account_key):
                return numeric_sort_key(self.tags.get(account_key) or '')
        self.account_order.sort(key=key, reverse=not self.sorted_on[1])

    def sort(self, column, order=Qt.AscendingOrder):
        nsort = (column, order == Qt.AscendingOrder)
        if nsort != self.sorted_on:
            self.sorted_on = nsort
            self.beginResetModel()
            try:
                self.do_sort()
            finally:
                self.endResetModel()

    def rowCount(self, *args):
        return len(self.account_order)

    def columnCount(self, *args):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

    def data(self, index, role):
        row, col = index.row(), index.column()
        if row < 0 or row >= self.rowCount():
            return None
        account = self.account_order[row]
        if account not in self.accounts:
            return None
        if role == Qt.UserRole:
            return (account, self.accounts[account])
        if role == Qt.ToolTipRole:
            return self.tooltips[col]
        if role in [Qt.DisplayRole, Qt.EditRole]:
            if col == 0:
                return (account)
            if col ==  1:
                return ', '.join(x.strip() for x in (self.accounts[account][0] or '').split(','))
            if col == 2:
                return (self.subjects.get(account, ''))
            if col == 4:
                return (self.aliases.get(account, ''))
            if col == 5:
                return (self.tags.get(account, ''))
        if role == Qt.FontRole and self.accounts[account][2]:
            return self.default_font
        if role == Qt.CheckStateRole and col == 3:
            return (Qt.Checked if self.accounts[account][1] else Qt.Unchecked)
        return None

    def flags(self, index):
        if index.column() == 3:
            return QAbstractTableModel.flags(self, index)|Qt.ItemIsUserCheckable
        else:
            return QAbstractTableModel.flags(self, index)|Qt.ItemIsEditable

    def setData(self, index, value, role):
        if not index.isValid():
            return False
        row, col = index.row(), index.column()
        account = self.account_order[row]
        if col == 3:
            self.accounts[account][1] ^= True
        elif col == 2:
            self.subjects[account] = unicode(value or '')
        elif col == 4:
            self.aliases.pop(account, None)
            aval = unicode(value or '').strip()
            if aval:
                self.aliases[account] = aval
        elif col == 5:
            self.tags.pop(account, None)
            aval = unicode(value or '').strip()
            if aval:
                self.tags[account] = aval
        elif col == 1:
            self.accounts[account][0] = re.sub(',+', ',', re.sub(r'\s+', ',', unicode(value or '').upper()))
        elif col == 0:
            na = unicode(value or '')
            from email.utils import parseaddr
            addr = parseaddr(na)[-1]
            if not addr:
                return False
            self.accounts[na] = self.accounts.pop(account)
            self.account_order[row] = na
            if '@kindle.com' in addr:
                self.accounts[na][0] = 'AZW, MOBI, TPZ, PRC, AZW1'

        self.dataChanged.emit(
                self.index(index.row(), 0), self.index(index.row(), 3))
        return True

    def make_default(self, index):
        if index.isValid():
            self.beginResetModel()
            row = index.row()
            for x in self.accounts.values():
                x[2] = False
            self.accounts[self.account_order[row]][2] = True
            self.endResetModel()

    def add(self):
        x = _('new email address')
        y = x
        c = 0
        while y in self.accounts:
            c += 1
            y = x + str(c)
        auto_send = len(self.accounts) < 1
        self.beginResetModel()
        self.accounts[y] = ['MOBI, EPUB', auto_send,
                                                len(self.account_order) == 0]
        self.account_order = self.accounts.keys()
        self.do_sort()
        self.endResetModel()
        return self.index(self.account_order.index(y), 0)

    def remove(self, index):
        if index.isValid():
            row = index.row()
            account = self.account_order[row]
            self.accounts.pop(account)
            self.account_order = sorted(self.accounts.keys())
            has_default = False
            for account in self.account_order:
                if self.accounts[account][2]:
                    has_default = True
                    break
            if not has_default and self.account_order:
                self.accounts[self.account_order[0]][2] = True

            self.beginResetModel()
            self.endResetModel()

# }}}


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    supports_restoring_to_defaults = False

    def genesis(self, gui):
        self.gui = gui
        self.proxy = ConfigProxy(smtp_prefs())
        r = self.register
        r('add_comments_to_email', gprefs)

        self.send_email_widget.initialize(self.preferred_to_address)
        self.send_email_widget.changed_signal.connect(self.changed_signal.emit)
        opts = self.send_email_widget.smtp_opts
        self._email_accounts = EmailAccounts(opts.accounts, opts.subjects,
                opts.aliases, opts.tags)
        self._email_accounts.dataChanged.connect(lambda x,y:
                self.changed_signal.emit())
        self.email_view.setModel(self._email_accounts)
        self.email_view.sortByColumn(0, Qt.AscendingOrder)
        self.email_view.setSortingEnabled(True)

        self.email_add.clicked.connect(self.add_email_account)
        self.email_make_default.clicked.connect(self.make_default)
        self.email_view.resizeColumnsToContents()
        self.email_remove.clicked.connect(self.remove_email_account)

    def preferred_to_address(self):
        if self._email_accounts.account_order:
            return self._email_accounts.account_order[0]

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        # Initializing all done in genesis

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        # No defaults to restore to

    def commit(self):
        if self.email_view.state() == self.email_view.EditingState:
            # Ensure that the cell being edited is committed by switching focus
            # to some other widget, which automatically closes the open editor
            self.send_email_widget.setFocus(Qt.OtherFocusReason)
        to_set = bool(self._email_accounts.accounts)
        if not self.send_email_widget.set_email_settings(to_set):
            raise AbortCommit('abort')
        self.proxy['accounts'] =  self._email_accounts.accounts
        self.proxy['subjects'] = self._email_accounts.subjects
        self.proxy['aliases'] = self._email_accounts.aliases
        self.proxy['tags'] = self._email_accounts.tags

        return ConfigWidgetBase.commit(self)

    def make_default(self, *args):
        self._email_accounts.make_default(self.email_view.currentIndex())
        self.changed_signal.emit()

    def add_email_account(self, *args):
        index = self._email_accounts.add()
        self.email_view.setCurrentIndex(index)
        self.email_view.resizeColumnsToContents()
        self.email_view.edit(index)
        self.changed_signal.emit()

    def remove_email_account(self, *args):
        idx = self.email_view.currentIndex()
        self._email_accounts.remove(idx)
        self.changed_signal.emit()

    def refresh_gui(self, gui):
        from calibre.gui2.email import gui_sendmail
        gui_sendmail.calculate_rate_limit()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Sharing', 'Email')
