# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from qt.core import QDialog, QDialogButtonBox, QVBoxLayout

from calibre.gui2.store.config.chooser.chooser_widget import StoreChooserWidget
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QWidget


class StoreChooserDialog(QDialog):
    def __init__(self, parent: QWidget | None) -> None:
        QDialog.__init__(self, parent)

        self.setWindowTitle(_('Choose stores'))

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        v = QVBoxLayout(self)
        self.config_widget = StoreChooserWidget()
        v.addWidget(self.config_widget)
        v.addWidget(button_box)

        self.resize(800, 600)
