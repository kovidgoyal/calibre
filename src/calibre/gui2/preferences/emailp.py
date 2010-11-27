#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QAbstractTableModel, QVariant, QFont, Qt


from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
        AbortCommit
from calibre.gui2.preferences.email_ui import Ui_Form
from calibre.utils.config import ConfigProxy
from calibre.gui2 import NONE
from calibre.utils.smtp import config as smtp_prefs

class EmailAccounts(QAbstractTableModel): # {{{

    def __init__(self, accounts):
        QAbstractTableModel.__init__(self)
        self.accounts = accounts
        self.account_order = sorted(self.accounts.keys())
        self.headers  = map(QVariant, [_('Email'), _('Formats'), _('Auto send')])
        self.default_font = QFont()
        self.default_font.setBold(True)
        self.default_font = QVariant(self.default_font)
        self.tooltips =[NONE] + map(QVariant,
            [_('Formats to email. The first matching format will be sent.'),
             '<p>'+_('If checked, downloaded news will be automatically '
                     'mailed <br>to this email address '
                     '(provided it is in one of the listed formats).')])

    def rowCount(self, *args):
        return len(self.account_order)

    def columnCount(self, *args):
        return 3

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return NONE

    def data(self, index, role):
        row, col = index.row(), index.column()
        if row < 0 or row >= self.rowCount():
            return NONE
        account = self.account_order[row]
        if role == Qt.UserRole:
            return (account, self.accounts[account])
        if role == Qt.ToolTipRole:
            return self.tooltips[col]
        if role in [Qt.DisplayRole, Qt.EditRole]:
            if col == 0:
                return QVariant(account)
            if col ==  1:
                return QVariant(self.accounts[account][0])
        if role == Qt.FontRole and self.accounts[account][2]:
            return self.default_font
        if role == Qt.CheckStateRole and col == 2:
            return QVariant(Qt.Checked if self.accounts[account][1] else Qt.Unchecked)
        return NONE

    def flags(self, index):
        if index.column() == 2:
            return QAbstractTableModel.flags(self, index)|Qt.ItemIsUserCheckable
        else:
            return QAbstractTableModel.flags(self, index)|Qt.ItemIsEditable

    def setData(self, index, value, role):
        if not index.isValid():
            return False
        row, col = index.row(), index.column()
        account = self.account_order[row]
        if col == 2:
            self.accounts[account][1] ^= True
        elif col == 1:
            self.accounts[account][0] = unicode(value.toString()).upper()
        else:
            na = unicode(value.toString())
            from email.utils import parseaddr
            addr = parseaddr(na)[-1]
            if not addr:
                return False
            self.accounts[na] = self.accounts.pop(account)
            self.account_order[row] = na
            if '@kindle.com' in addr:
                self.accounts[na][0] = 'AZW, MOBI, TPZ, PRC, AZW1'

        self.dataChanged.emit(
                self.index(index.row(), 0), self.index(index.row(), 2))
        return True

    def make_default(self, index):
        if index.isValid():
            row = index.row()
            for x in self.accounts.values():
                x[2] = False
            self.accounts[self.account_order[row]][2] = True
            self.reset()

    def add(self):
        x = _('new email address')
        y = x
        c = 0
        while y in self.accounts:
            c += 1
            y = x + str(c)
        auto_send = len(self.accounts) < 1
        self.accounts[y] = ['MOBI, EPUB', auto_send,
                                                len(self.account_order) == 0]
        self.account_order = sorted(self.accounts.keys())
        self.reset()
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

            self.reset()

# }}}

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    supports_restoring_to_defaults = False

    def genesis(self, gui):
        self.gui = gui
        self.proxy = ConfigProxy(smtp_prefs())

        self.send_email_widget.initialize(self.preferred_to_address)
        self.send_email_widget.changed_signal.connect(self.changed_signal.emit)
        opts = self.send_email_widget.smtp_opts
        self._email_accounts = EmailAccounts(opts.accounts)
        self._email_accounts.dataChanged.connect(lambda x,y:
                self.changed_signal.emit())
        self.email_view.setModel(self._email_accounts)

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
        to_set = bool(self._email_accounts.accounts)
        if not self.send_email_widget.set_email_settings(to_set):
            raise AbortCommit('abort')
        self.proxy['accounts'] =  self._email_accounts.accounts

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
        gui.emailer.calculate_rate_limit()


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Sharing', 'Email')

