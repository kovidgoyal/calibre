

__license__   = 'GPL v3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'

from PyQt5.Qt import QDialog, QTreeWidgetItem, QIcon, QModelIndex

from calibre.gui2 import file_icon_provider
from calibre.gui2.dialogs.choose_format_device_ui import Ui_ChooseFormatDeviceDialog
from polyglot.builtins import unicode_type


class ChooseFormatDeviceDialog(QDialog, Ui_ChooseFormatDeviceDialog):

    def __init__(self, window, msg, formats):
        '''
        formats is a list of tuples: [(format, exists, convertible)].
            format: Lower case format identifier. E.G. mobi
            exists: String representing the number of books that
                    exist in the format.
            convertible: True if the format is a convertible format.
        formats should be ordered in the device's preferred format ordering.
        '''
        QDialog.__init__(self, window)
        Ui_ChooseFormatDeviceDialog.__init__(self)
        self.setupUi(self)
        self.formats.activated[QModelIndex].connect(self.activated_slot)

        self.msg.setText(msg)
        for i, (format, exists, convertible) in enumerate(formats):
            t_item = QTreeWidgetItem()
            t_item.setIcon(0, file_icon_provider().icon_from_ext(format.lower()))
            t_item.setText(0, format.upper())
            t_item.setText(1, exists)
            if convertible:
                t_item.setIcon(2, QIcon(I('ok.png')))
            self.formats.addTopLevelItem(t_item)
            if i == 0:
                self.formats.setCurrentItem(t_item)
                t_item.setSelected(True)
        self.formats.resizeColumnToContents(2)
        self.formats.resizeColumnToContents(1)
        self.formats.resizeColumnToContents(0)
        self.formats.header().resizeSection(0, self.formats.header().sectionSize(0) * 2)
        self._format = None

    def activated_slot(self, *args):
        self.accept()

    def format(self):
        return self._format

    def accept(self):
        self._format = unicode_type(self.formats.currentItem().text(0))
        return QDialog.accept(self)
