__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from qt.core import (QDialog, QDialogButtonBox, QVBoxLayout)

from calibre.gui2.store.config.chooser.chooser_widget import StoreChooserWidget


class StoreChooserDialog(QDialog):

    def __init__(self, parent):
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
