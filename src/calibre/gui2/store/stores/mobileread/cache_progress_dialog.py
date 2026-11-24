# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>


from typing import TYPE_CHECKING

from qt.core import QDialog

from calibre.gui2.store.stores.mobileread.cache_progress_dialog_ui import Ui_Dialog

if TYPE_CHECKING:
    from qt.core import QWidget


class CacheProgressDialog(QDialog, Ui_Dialog):
    def __init__(self, parent: QWidget | None = None, total: int | None = None) -> None:
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

    def set_message(self, msg: str) -> None:
        self.message.setText(msg)

    def set_details(self, msg: str) -> None:
        self.details.setText(msg)

    def set_progress(self, completed: int) -> None:
        """
        completed is an int from 0 to total representing the number
        records that have bee completed.
        """
        self.completed = completed
        self.progress.setValue(self.completed)

    def set_total(self, total: int) -> None:
        self.progress.setMaximum(total)
