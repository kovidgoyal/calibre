#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QDialog, QWidget, Qt, QDialogButtonBox, QVBoxLayout

from calibre.gui2.convert.xpath_wizard_ui import Ui_Form
from calibre.gui2.convert.xexp_edit_ui import Ui_Form as Ui_Edit
from calibre.utils.localization import localize_user_manual_link
from polyglot.builtins import unicode_type, map


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
        tag = unicode_type(self.tag.currentText()).strip()
        if tag != '*':
            tag = 'h:'+tag
        attr, val = map(unicode_type, (self.attribute.text(), self.value.text()))
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
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.verticalLayout.addWidget(self.buttonBox)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.setModal(Qt.WindowModal)

    @property
    def xpath(self):
        return self.widget.xpath


class XPathEdit(QWidget, Ui_Edit):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self.button.clicked.connect(self.wizard)

    def wizard(self):
        wiz = Wizard(self)
        if wiz.exec_() == wiz.Accepted:
            self.edit.setText(wiz.xpath)

    def setObjectName(self, *args):
        QWidget.setObjectName(self, *args)
        if hasattr(self, 'edit'):
            self.edit.initialize('xpath_edit_'+unicode_type(self.objectName()))

    def set_msg(self, msg):
        self.msg.setText(msg)

    @property
    def text(self):
        return unicode_type(self.edit.text())

    @property
    def xpath(self):
        return self.text

    def check(self):
        from calibre.ebooks.oeb.base import XPNSMAP
        from lxml.etree import XPath
        try:
            if self.text.strip():
                XPath(self.text, namespaces=XPNSMAP)
        except:
            import traceback
            traceback.print_exc()
            return False
        return True


if __name__ == '__main__':
    from PyQt5.Qt import QApplication
    app = QApplication([])
    w = XPathEdit()
    w.setObjectName('test')
    w.show()
    app.exec_()
    print(w.xpath)
