# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals


__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QDialog

from calibre.gui2.store.stores.mobileread.cache_progress_dialog_ui import Ui_Dialog


class CacheProgressDialog(QDialog, Ui_Dialog):

    def __init__(self, parent=None, total=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.completed = 0
        self.canceled = False

        self.progress.setValue(0)
        self.progress.setMinimum(0)
        self.progress.setMaximum(total if total else 0)

    def exec_(self):
        self.completed = 0
        self.canceled = False
        QDialog.exec_(self)

    def open(self):
        self.completed = 0
        self.canceled = False
        QDialog.open(self)

    def reject(self):
        self.canceled = True
        QDialog.reject(self)

    def update_progress(self):
        '''
        completed is an int from 0 to total representing the number
        records that have bee completed.
        '''
        self.set_progress(self.completed + 1)

    def set_message(self, msg):
        self.message.setText(msg)

    def set_details(self, msg):
        self.details.setText(msg)

    def set_progress(self, completed):
        '''
        completed is an int from 0 to total representing the number
        records that have bee completed.
        '''
        self.completed = completed
        self.progress.setValue(self.completed)

    def set_total(self, total):
        self.progress.setMaximum(total)
