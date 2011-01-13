#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback

from calibre.gui2 import error_dialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.template_functions_ui import Ui_Form
from calibre.utils.config import prefs
from calibre.utils.formatter_functions import formatter_functions, compile_user_function


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.db = gui.library_view.model().db
        self.current_plugboards = self.db.prefs.get('plugboards',{})

    def initialize(self):
        self.funcs = formatter_functions.get_functions()
        self.builtins = formatter_functions.get_builtins()

        self.build_function_names_box()
        self.function_name.currentIndexChanged[str].connect(self.function_index_changed)
        self.function_name.editTextChanged.connect(self.function_name_edited)
        self.create_button.clicked.connect(self.create_button_clicked)
        self.delete_button.clicked.connect(self.delete_button_clicked)
        self.create_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_button_clicked)
        self.program.setTabStopWidth(20)

    def clear_button_clicked(self):
        self.build_function_names_box()
        self.program.clear()
        self.documentation.clear()
        self.argument_count.clear()
        self.create_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def build_function_names_box(self, scroll_to='', set_to=''):
        self.function_name.blockSignals(True)
        func_names = sorted(self.funcs)
        self.function_name.clear()
        self.function_name.addItem('')
        self.function_name.addItems(func_names)
        self.function_name.setCurrentIndex(0)
        if set_to:
            self.function_name.setEditText(set_to)
            self.create_button.setEnabled(True)
        self.function_name.blockSignals(False)
        if scroll_to:
            idx = self.function_name.findText(scroll_to)
            if idx >= 0:
                self.function_name.setCurrentIndex(idx)
                if scroll_to not in self.builtins:
                    self.delete_button.setEnabled(True)

    def delete_button_clicked(self):
        name = unicode(self.function_name.currentText())
        if name in self.builtins:
            error_dialog(self.gui, _('Template functions'),
                         _('You cannot delete a built-in function'), show=True)
        if name in self.funcs:
            del self.funcs[name]
            self.changed_signal.emit()
            self.create_button.setEnabled(True)
            self.delete_button.setEnabled(False)
            self.build_function_names_box(set_to=name)
        else:
            error_dialog(self.gui, _('Template functions'),
                         _('Function not defined'), show=True)

    def create_button_clicked(self):
        self.changed_signal.emit()
        name = unicode(self.function_name.currentText())
        if name in self.funcs:
            error_dialog(self.gui, _('Template functions'),
                         _('Name already used'), show=True)
            return
        if self.argument_count.value() == 0:
            error_dialog(self.gui, _('Template functions'),
                         _('Argument count must be -1 or greater than zero'),
                         show=True)
            return
        try:
            prog = unicode(self.program.toPlainText())
            cls = compile_user_function(name, unicode(self.documentation.toPlainText()),
                                        self.argument_count.value(), prog)
            self.funcs[name] = cls
            self.build_function_names_box(scroll_to=name)
        except:
            error_dialog(self.gui, _('Template functions'),
                         _('Exception while compiling function'), show=True,
                         det_msg=traceback.format_exc())

    def function_name_edited(self, txt):
        self.documentation.setReadOnly(False)
        self.argument_count.setReadOnly(False)
        self.create_button.setEnabled(True)

    def function_index_changed(self, txt):
        txt = unicode(txt)
        self.create_button.setEnabled(False)
        if not txt:
            self.argument_count.clear()
            self.documentation.clear()
            self.documentation.setReadOnly(False)
            self.argument_count.setReadOnly(False)
            return
        func = self.funcs[txt]
        self.argument_count.setValue(func.arg_count)
        self.documentation.setText(func.doc)
        if txt in self.builtins:
            self.documentation.setReadOnly(True)
            self.argument_count.setReadOnly(True)
            self.program.clear()
            self.delete_button.setEnabled(False)
        else:
            self.program.setPlainText(func.program_text)
            self.delete_button.setEnabled(True)

    def refresh_gui(self, gui):
        pass

    def commit(self):
        formatter_functions.reset_to_builtins()
        pref_value = []
        for f in self.funcs:
            if f in self.builtins:
                continue
            func = self.funcs[f]
            formatter_functions.register_function(func)
            pref_value.append((func.name, func.doc, func.arg_count, func.program_text))
        self.db.prefs.set('user_template_functions', pref_value)


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Advanced', 'TemplateFunctions')

