# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>


from qt.core import QDialog

from calibre.gui2.store.stores.mobileread.cache_progress_dialog_ui import Ui_Dialog


class CacheProgressDialog(QDialog, Ui_Dialog):
    def __init__(self, parent=None, total=None) -> None:
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.completed = 0
        self.canceled = False

        self.progress.setValue(0)
        self.progress.setMinimum(0)
        self.progress.setMaximum(total or 0)

    def exec(self) -> int:
        self.completed = 0
        self.canceled = False
        return QDialog.exec(self)

    exec_ = exec

    def open(self) -> None:
        self.completed = 0
        self.canceled = False
        QDialog.open(self)

    def reject(self) -> None:
        self.canceled = True
        QDialog.reject(self)

    def update_progress(self) -> None:
        """
        completed is an int from 0 to total representing the number
        records that have bee completed.
        """
        self.set_progress(self.completed + 1)

    def set_message(self, msg) -> None:
        self.message.setText(msg)

    def set_details(self, msg) -> None:
        self.details.setText(msg)

    def set_progress(self, completed) -> None:
        """
        completed is an int from 0 to total representing the number
        records that have bee completed.
        """
        self.completed = completed
        self.progress.setValue(self.completed)

    def set_total(self, total) -> None:
        self.progress.setMaximum(total)
