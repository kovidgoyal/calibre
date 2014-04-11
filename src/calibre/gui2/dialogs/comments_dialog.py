#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt5.Qt import Qt, QDialog, QDialogButtonBox

from calibre.gui2 import gprefs
from calibre.gui2.dialogs.comments_dialog_ui import Ui_CommentsDialog
from calibre.library.comments import comments_to_html

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
        self.buttonBox.button(QDialogButtonBox.Ok).setText(_('&OK'))
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(_('&Cancel'))

        if column_name:
            self.setWindowTitle(_('Edit "{0}"').format(column_name))

        geom = gprefs.get('comments_dialog_geom', None)
        if geom is not None:
            self.restoreGeometry(geom)

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

