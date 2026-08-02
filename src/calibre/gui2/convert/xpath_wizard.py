#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

from qt.core import QComboBox, QDialog, QDialogButtonBox, QGridLayout, QIcon, QLabel, QSizePolicy, Qt, QToolButton, QVBoxLayout, QWidget

from calibre.gui2.convert.xpath_wizard_ui import Ui_Form
from calibre.gui2.widgets import HistoryLineEdit
from calibre.utils.localization import _, localize_user_manual_link


class WizardWidget(QWidget, Ui_Form):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        try:
            self.example_label.setText(self.example_label.text() % localize_user_manual_link('https://manual.calibre-ebook.com/xpath.html'))
        except TypeError:
            pass

    @property
    def xpath(self):
        tag = str(self.tag.currentText()).strip()
        if tag != '*':
            tag = 'h:' + tag
        attr, val = map(str, (self.attribute.text(), self.value.text()))
        attr, val = attr.strip(), val.strip()
        q = ''
        if attr:
            if val:
                q = f'[re:test(@{attr}, "{val}", "i")]'
            else:
                q = f'[@{attr}]'
        elif val:
            q = f'[re:test(., "{val}", "i")]'
        expr = '//' + tag + q
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
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
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
        self.g = g = QGridLayout(self)
        g.setContentsMargins(0, 0, 0, 0)
        self.button = b = QToolButton(self)
        b.setIcon(QIcon.ic('wizard.png'))
        b.setToolTip(_('Use a wizard to generate the XPath expression'))
        b.clicked.connect(self.wizard)
        p = b.sizePolicy()
        p.setVerticalPolicy(QSizePolicy.Policy.Minimum)
        b.setSizePolicy(p)
        self.edit = e = HistoryLineEdit(self)
        e.setMinimumWidth(350)
        e.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        e.setMinimumContentsLength(30)
        self.msg = QLabel('')
        if show_msg:
            g.addWidget(self.msg, 0, 0, 1, 2)
            g.addWidget(e, 1, 0)
            g.addWidget(b, 1, 1)
            self.msg.setBuddy(e)
        else:
            self.msg.setVisible(False)
            g.addWidget(e, 0, 0)
            g.addWidget(b, 0, 1)
        if object_name:
            self.setObjectName(object_name)

    def setPlaceholderText(self, val):
        self.edit.setPlaceholderText(val)

    def wizard(self):
        wiz = Wizard(self)
        if wiz.exec() == QDialog.DialogCode.Accepted:
            self.edit.setText(wiz.xpath)

    def setObjectName(self, name):
        QWidget.setObjectName(self, name)
        if hasattr(self, 'edit'):
            self.edit.initialize('xpath_edit_' + str(self.objectName()))

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
        except Exception:
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
