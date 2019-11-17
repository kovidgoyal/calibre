#!/usr/bin/env python


__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt5.Qt import Qt, QDialog, QDialogButtonBox, QVBoxLayout, QPlainTextEdit, QSize, QApplication

from calibre.gui2 import gprefs, Application
from calibre.gui2.dialogs.comments_dialog_ui import Ui_CommentsDialog
from calibre.library.comments import comments_to_html
from calibre.gui2.widgets2 import Dialog


class CommentsDialog(QDialog, Ui_CommentsDialog):

    def __init__(self, parent, text, column_name=None):
        QDialog.__init__(self, parent)
        Ui_CommentsDialog.__init__(self)
        self.setupUi(self)
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.textbox.html = comments_to_html(text) if text else ''
        self.textbox.wyswyg_dirtied()
        # self.textbox.setTabChangesFocus(True)
        self.buttonBox.button(QDialogButtonBox.Ok).setText(_('O&K'))
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(_('&Cancel'))

        if column_name:
            self.setWindowTitle(_('Edit "{0}"').format(column_name))

        geom = gprefs.get('comments_dialog_geom', None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)

    def save_geometry(self):
        gprefs.set('comments_dialog_geom', bytearray(self.saveGeometry()))

    def accept(self):
        self.save_geometry()
        QDialog.accept(self)

    def reject(self):
        self.save_geometry()
        QDialog.reject(self)

    def closeEvent(self, ev):
        self.save_geometry()
        return QDialog.closeEvent(self, ev)


class PlainTextDialog(Dialog):

    def __init__(self, parent, text, column_name=None):
        title = _('Edit "{0}"').format(column_name) if column_name else _('Edit text')
        Dialog.__init__(self, title, 'edit-plain-text-dialog', parent=parent)
        self.text = text

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self._text = QPlainTextEdit(self)
        l.addWidget(self._text)
        l.addWidget(self.bb)

    @property
    def text(self):
        return self._text.toPlainText()

    @text.setter
    def text(self, val):
        self._text.setPlainText(val or '')

    def sizeHint(self):
        return QSize(600, 400)


if __name__ == '__main__':
    app = Application([])
    d = CommentsDialog(None, 'testing', 'Comments')
    d.exec_()
    del d
    del app
