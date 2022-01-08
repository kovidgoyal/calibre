#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import (
    QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QIcon, QLabel, QSize, Qt,
    QToolButton, QVBoxLayout, QWidget
)

from calibre.gui2.convert.xpath_wizard_ui import Ui_Form
from calibre.gui2.widgets import HistoryLineEdit
from calibre.utils.localization import localize_user_manual_link


class WizardWidget(QWidget, Ui_Form):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        try:
            self.example_label.setText(self.example_label.text() % localize_user_manual_link(
                'https://manual.calibre-ebook.com/xpath.html'))
        except TypeError:
            pass

    @property
    def xpath(self):
        tag = str(self.tag.currentText()).strip()
        if tag != '*':
            tag = 'h:'+tag
        attr, val = map(str, (self.attribute.text(), self.value.text()))
        attr, val = attr.strip(), val.strip()
        q = ''
        if attr:
            if val:
                q = '[re:test(@%s, "%s", "i")]'%(attr, val)
            else:
                q = '[@%s]'%attr
        elif val:
            q = '[re:test(., "%s", "i")]'%(val)
        expr = '//'+tag + q
        return expr


class Wizard(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.resize(440, 480)
        self.verticalLayout = QVBoxLayout(self)
        self.widget = WizardWidget(self)
        self.verticalLayout.addWidget(self.widget)
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
        self.verticalLayout.addWidget(self.buttonBox)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.setWindowModality(Qt.WindowModality.WindowModal)

    @property
    def xpath(self):
        return self.widget.xpath


class XPathEdit(QWidget):

    def __init__(self, parent=None, object_name='', show_msg=True):
        QWidget.__init__(self, parent)
        self.h = h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.l = l = QVBoxLayout()
        h.addLayout(l)
        self.button = b = QToolButton(self)
        b.setIcon(QIcon.ic('wizard.png'))
        b.setToolTip(_('Use a wizard to generate the XPath expression'))
        b.clicked.connect(self.wizard)
        h.addWidget(b)
        self.edit = e = HistoryLineEdit(self)
        e.setMinimumWidth(350)
        e.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        e.setMinimumContentsLength(30)
        self.msg = QLabel('')
        l.addWidget(self.msg)
        l.addWidget(self.edit)
        if object_name:
            self.setObjectName(object_name)
        if show_msg:
            b.setIconSize(QSize(40, 40))
            self.msg.setBuddy(self.edit)
        else:
            self.msg.setVisible(False)
            l.setContentsMargins(0, 0, 0, 0)

    def setPlaceholderText(self, val):
        self.edit.setPlaceholderText(val)

    def wizard(self):
        wiz = Wizard(self)
        if wiz.exec() == QDialog.DialogCode.Accepted:
            self.edit.setText(wiz.xpath)

    def setObjectName(self, *args):
        QWidget.setObjectName(self, *args)
        if hasattr(self, 'edit'):
            self.edit.initialize('xpath_edit_'+str(self.objectName()))

    def set_msg(self, msg):
        self.msg.setText(msg)

    @property
    def text(self):
        return str(self.edit.text())

    @text.setter
    def text(self, val):
        self.edit.setText(str(val))
    value = text

    @property
    def xpath(self):
        return self.text

    def check(self):
        from calibre.ebooks.oeb.base import XPath
        try:
            if self.text.strip():
                XPath(self.text)
        except:
            import traceback
            traceback.print_exc()
            return False
        return True


if __name__ == '__main__':
    from qt.core import QApplication
    app = QApplication([])
    w = XPathEdit()
    w.setObjectName('test')
    w.show()
    app.exec()
    print(w.xpath)
