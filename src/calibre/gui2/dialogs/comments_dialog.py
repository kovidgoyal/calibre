#!/usr/bin/env python


__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from qt.core import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit, QSize, Qt,
    QVBoxLayout, pyqtSignal,
)

from calibre.gui2 import Application, gprefs
from calibre.gui2.comments_editor import Editor
from calibre.gui2.widgets2 import Dialog
from calibre.library.comments import comments_to_html


class CommentsDialog(QDialog):

    def __init__(self, parent, text, column_name=None):
        QDialog.__init__(self, parent)
        self.setObjectName("CommentsDialog")
        self.setWindowTitle(_("Edit comments"))
        self.verticalLayout = l = QVBoxLayout(self)
        self.textbox = tb = Editor(self)
        self.buttonBox = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(tb)
        l.addWidget(bb)
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.textbox.html = comments_to_html(text) if text else ''
        self.textbox.wyswyg_dirtied()
        # self.textbox.setTabChangesFocus(True)

        if column_name:
            self.setWindowTitle(_('Edit "{0}"').format(column_name))
        self.restore_geometry(gprefs, 'comments_dialog_geom')

    def sizeHint(self):
        return QSize(650, 600)

    def accept(self):
        self.save_geometry(gprefs, 'comments_dialog_geom')
        QDialog.accept(self)

    def reject(self):
        self.save_geometry(gprefs, 'comments_dialog_geom')
        QDialog.reject(self)

    def closeEvent(self, ev):
        self.save_geometry(gprefs, 'comments_dialog_geom')
        return QDialog.closeEvent(self, ev)


class PlainTextEdit(QPlainTextEdit):
    ctrl_enter_pushed = pyqtSignal()

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Return:
            event.accept()
            self.ctrl_enter_pushed.emit()
        else:
            super().keyPressEvent(event)


class PlainTextDialog(Dialog):

    def __init__(self, parent, text, column_name=None):
        title = _('Edit "{0}"').format(column_name) if column_name else _('Edit text')
        Dialog.__init__(self, title, 'edit-plain-text-dialog', parent=parent)
        self.text = text

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self._text = PlainTextEdit(self)
        self._text.ctrl_enter_pushed.connect(self.ctrl_enter_pushed)
        l.addWidget(self._text)
        hl = QHBoxLayout()
        hl.addWidget(QLabel(_('Press Ctrl+Enter to accept or Esc to cancel')))
        hl.addWidget(self.bb)
        l.addLayout(hl)

    def ctrl_enter_pushed(self):
        self.accept()

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
    d.exec()
    del d
    del app
