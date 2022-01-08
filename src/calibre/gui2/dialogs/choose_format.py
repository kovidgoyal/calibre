__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from qt.core import (
    QDialog, QListWidgetItem, QModelIndex, QIcon, QLabel, QVBoxLayout, QSize,
    QDialogButtonBox, QListWidget, QHBoxLayout, QPushButton, QMenu)

from calibre.gui2 import file_icon_provider


class ChooseFormatDialog(QDialog):

    def __init__(self, window, msg, formats, show_open_with=False):
        QDialog.__init__(self, window)
        self.resize(507, 377)
        self.setWindowIcon(QIcon.ic("mimetypes/unknown.png"))
        self.setWindowTitle(_('Choose format'))
        self.l = l = QVBoxLayout(self)
        self.msg = QLabel(msg)
        l.addWidget(self.msg)
        self.formats = QListWidget(self)
        self.formats.setIconSize(QSize(64, 64))
        self.formats.activated[QModelIndex].connect(self.activated_slot)
        l.addWidget(self.formats)
        self.h = h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)
        if show_open_with:
            self.owb = QPushButton(_('&Open with...'), self)
            self.formats.currentRowChanged.connect(self.update_open_with_button)
            h.addWidget(self.owb)
            self.own = QMenu(self.owb.text())
            self.owb.setMenu(self.own)
            self.own.aboutToShow.connect(self.populate_open_with)
        self.buttonBox = bb = QDialogButtonBox(self)
        bb.setStandardButtons(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        h.addStretch(10), h.addWidget(self.buttonBox)

        formats = list(formats)
        for format in formats:
            self.formats.addItem(QListWidgetItem(file_icon_provider().icon_from_ext(format.lower()),
                                                 format.upper()))
        self._formats = formats
        self.formats.setCurrentRow(0)
        self._format = self.open_with_format = None
        if show_open_with:
            self.populate_open_with()
            self.update_open_with_button()

    def populate_open_with(self):
        from calibre.gui2.open_with import populate_menu, edit_programs
        menu = self.own
        menu.clear()
        fmt = self._formats[self.formats.currentRow()]

        def connect_action(ac, entry):
            connect_lambda(ac.triggered, self, lambda self: self.open_with(entry))

        populate_menu(menu, connect_action, fmt)
        if len(menu.actions()) == 0:
            menu.addAction(_('Open %s with...') % fmt.upper(), self.choose_open_with)
        else:
            menu.addSeparator()
            menu.addAction(_('Add other application for %s files...') % fmt.upper(), self.choose_open_with)
            menu.addAction(_('Edit "Open with" applications...'), partial(edit_programs, fmt, self))

    def update_open_with_button(self):
        fmt = self._formats[self.formats.currentRow()]
        self.owb.setText(_('Open %s with...') % fmt)

    def open_with(self, entry):
        self.open_with_format = (self._formats[self.formats.currentRow()], entry)
        self.accept()

    def choose_open_with(self):
        from calibre.gui2.open_with import choose_program
        fmt = self._formats[self.formats.currentRow()]
        entry = choose_program(fmt, self)
        if entry is not None:
            self.open_with(entry)

    def book_converted(self, book_id, fmt):
        fmt = fmt.upper()
        if fmt not in self._formats:
            self._formats.append(fmt)
            self.formats.addItem(QListWidgetItem(
                file_icon_provider().icon_from_ext(fmt.lower()), fmt.upper()))

    def activated_slot(self, *args):
        self.accept()

    def format(self):
        return self._format

    def accept(self):
        self._format = self._formats[self.formats.currentRow()]
        return QDialog.accept(self)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = ChooseFormatDialog(None, 'Testing choose format', ['epub', 'mobi', 'docx'], show_open_with=True)
    d.exec()
    print(d._format)
    del app
