# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from qt.core import QDialog

from calibre.gui2.dialogs.conversion_error_ui import Ui_ConversionErrorDialog

if TYPE_CHECKING:
    from qt.core import QWidget


class ConversionErrorDialog(QDialog, Ui_ConversionErrorDialog):
    def __init__(self, window: QWidget | None, title: str, html: str, show: bool = False) -> None:
        QDialog.__init__(self, window)
        Ui_ConversionErrorDialog.__init__(self)
        self.setupUi(self)
        self.setWindowTitle(title)
        self.set_message(html)
        if show:
            self.show()

    def set_message(self, html: str) -> None:
        self.text.setHtml(f'<html><body>{html}</body></html')
