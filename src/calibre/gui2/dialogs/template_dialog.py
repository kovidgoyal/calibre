#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

import json

from PyQt4.Qt import Qt, QDialog, QDialogButtonBox
from calibre.gui2.dialogs.template_dialog_ui import Ui_TemplateDialog
from calibre.utils.formatter_functions import formatter_functions

class TemplateDialog(QDialog, Ui_TemplateDialog):

    def __init__(self, parent, text):
        QDialog.__init__(self, parent)
        Ui_TemplateDialog.__init__(self)
        self.setupUi(self)
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.textbox.setTabStopWidth(10)
        self.source_code.setTabStopWidth(10)
        self.documentation.setReadOnly(True)
        self.source_code.setReadOnly(True)

        if text is not None:
            self.textbox.setPlainText(text)
        self.buttonBox.button(QDialogButtonBox.Ok).setText(_('&OK'))
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(_('&Cancel'))

        try:
            with open(P('template-functions.json'), 'rb') as f:
                self.builtin_source_dict = json.load(f, encoding='utf-8')
        except:
            self.builtin_source_dict = {}

        self.funcs = formatter_functions.get_functions()
        self.builtins = formatter_functions.get_builtins()

        func_names = sorted(self.funcs)
        self.function.clear()
        self.function.addItem('')
        self.function.addItems(func_names)
        self.function.setCurrentIndex(0)
        self.function.currentIndexChanged[str].connect(self.function_changed)

    def function_changed(self, toWhat):
        name = unicode(toWhat)
        self.source_code.clear()
        self.documentation.clear()
        if name in self.funcs:
            self.documentation.setPlainText(self.funcs[name].doc)
            if name in self.builtins:
                if name in self.builtin_source_dict:
                    self.source_code.setPlainText(self.builtin_source_dict[name])
            else:
                self.source_code.setPlainText(self.funcs[name].program_text)

