#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback

from PyQt5.Qt import (Qt, QGridLayout, QLabel, QSpacerItem, QSizePolicy,
                      QComboBox, QTextEdit, QHBoxLayout, QPushButton)

from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.template_line_editor import TemplateLineEditor
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.utils.formatter_functions import (formatter_functions,
                        compile_user_function, compile_user_template_functions,
                        load_user_template_functions, function_pref_is_python,
                        function_pref_name)
from polyglot.builtins import native_string_type, unicode_type


class ConfigWidget(ConfigWidgetBase):

    def genesis(self, gui):
        self.gui = gui
        self.db = gui.library_view.model().db

        help_text = '<p>' + _('''
        Here you can add and remove stored templates used in template processing.
        You use a stored template in another template with the 'call' template
        function, as in 'call(somename, arguments...). Stored templates must use
        General Program Mode -- they must begin with the text 'program:'.
        In the stored template you get the arguments using the 'arguments()'
        template function, as in arguments(var1, var2, ...). The calling arguments
        are copied to the named variables.
        ''') + '</p>'
        l = QGridLayout(self)
        w = QLabel(help_text)
        w.setWordWrap(True)
        l.addWidget(w, 0, 0, 1, 2)

        lab = QLabel(_('&Template'))
        l.addWidget(lab, 1, 0)
        lb = QHBoxLayout()
        self.program = w = TemplateLineEditor(self)
        w.setPlaceholderText(_('The GPM template.'))
        lab.setBuddy(w)
        lb.addWidget(w, stretch=1)
        self.editor_button = b = QPushButton(_('&Open Editor'))
        b.clicked.connect(w.open_editor)
        lb.addWidget(b)
        l.addLayout(lb, 1, 1)

        lab = QLabel(_('&Name'))
        l.addWidget(lab, 2, 0)
        self.function_name = w = QComboBox(self)
        w.setEditable(True)
        lab.setBuddy(w)
        w.setToolTip(_('The name of the function, used in a call statement'))

        l.addWidget(w, 2, 1)

        lab = QLabel(_('&Documentation'))
        l.addWidget(lab, 3, 0, Qt.AlignTop)
        self.documentation = w = QTextEdit(self)
        w.setPlaceholderText(_('A description of the template. Whatever you wish ...'))
        lab.setBuddy(w)
        l.addWidget(w, 3, 1)

        lb = QHBoxLayout()
        lb.addStretch(1)
        self.clear_button = w = QPushButton(_('C&lear'))
        lb.addWidget(w)
        self.delete_button = w = QPushButton(_('&Delete'))
        lb.addWidget(w)
        self.replace_button = w = QPushButton(_('&Replace'))
        lb.addWidget(w)
        self.create_button = w = QPushButton(_('&Create'))
        lb.addWidget(w)
        lb.addStretch(1)
        l.addLayout(lb, 9, 1)

        l.addItem(QSpacerItem(10, 10, vPolicy=QSizePolicy.Expanding), 10, 0, -1, -1)
        self.setLayout(l)


    def initialize(self):
        self.funcs = {}
        for v in self.db.prefs.get('user_template_functions', []):
            if not function_pref_is_python(v):
                self.funcs.update({function_pref_name(v):compile_user_function(*v)})

        self.build_function_names_box()
        self.function_name.currentIndexChanged[native_string_type].connect(self.function_index_changed)
        self.function_name.editTextChanged.connect(self.function_name_edited)
        self.documentation.textChanged.connect(self.enable_replace_button)
        self.program.textChanged.connect(self.enable_replace_button)
        self.create_button.clicked.connect(self.create_button_clicked)
        self.delete_button.clicked.connect(self.delete_button_clicked)
        self.create_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.replace_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_button_clicked)
        self.replace_button.clicked.connect(self.replace_button_clicked)

    def enable_replace_button(self):
        self.replace_button.setEnabled(self.delete_button.isEnabled())

    def clear_button_clicked(self):
        self.build_function_names_box()
        self.program.clear()
        self.documentation.clear()
        self.create_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def build_function_names_box(self, scroll_to=''):
        self.function_name.blockSignals(True)
        func_names = sorted(self.funcs)
        self.function_name.clear()
        self.function_name.addItem('')
        self.function_name.addItems(func_names)
        self.function_name.setCurrentIndex(0)
        self.function_name.blockSignals(False)
        if scroll_to:
            idx = self.function_name.findText(scroll_to)
            if idx >= 0:
                self.function_name.setCurrentIndex(idx)

    def delete_button_clicked(self):
        name = unicode_type(self.function_name.currentText())
        if name in self.funcs:
            del self.funcs[name]
            self.changed_signal.emit()
            self.create_button.setEnabled(True)
            self.delete_button.setEnabled(False)
            self.build_function_names_box()
            self.program.setReadOnly(False)
        else:
            error_dialog(self.gui, _('Stored templates'),
                         _('Function not defined'), show=True)

    def create_button_clicked(self, use_name=None):
        self.changed_signal.emit()
        name = use_name if use_name else unicode_type(self.function_name.currentText())
        for k,v in formatter_functions().get_functions().items():
            if k == name and v.is_python:
                error_dialog(self.gui, _('Stored templates'),
                         _('Name %s is already used for template function')%(name,), show=True)
        try:
            prog = unicode_type(self.program.text())
            if not prog.startswith('program:'):
                error_dialog(self.gui, _('Stored templates'),
                         _('The stored template must begin with "program:"'), show=True)

            cls = compile_user_function(name, unicode_type(self.documentation.toPlainText()),
                                        0, prog)
            self.funcs[name] = cls
            self.build_function_names_box(scroll_to=name)
        except:
            error_dialog(self.gui, _('Stored templates'),
                         _('Exception while storing template'), show=True,
                         det_msg=traceback.format_exc())

    def function_name_edited(self, txt):
        self.documentation.setReadOnly(False)
        self.create_button.setEnabled(True)
        self.replace_button.setEnabled(False)
        self.program.setReadOnly(False)

    def function_index_changed(self, txt):
        txt = unicode_type(txt)
        self.create_button.setEnabled(False)
        if not txt:
            self.program.clear()
            self.documentation.clear()
            self.documentation.setReadOnly(False)
            return
        func = self.funcs[txt]
        self.documentation.setText(func.doc)
        self.program.setText(func.program_text)
        self.delete_button.setEnabled(True)
        self.program.setReadOnly(False)
        self.replace_button.setEnabled(False)

    def replace_button_clicked(self):
        name = unicode_type(self.function_name.currentText())
        self.delete_button_clicked()
        self.create_button_clicked(use_name=name)

    def refresh_gui(self, gui):
        pass

    def commit(self):
        # formatter_functions().reset_to_builtins()
        pref_value = [v for v in self.db.prefs.get('user_template_functions', [])
                      if function_pref_is_python(v)]
        for v in self.funcs.values():
            pref_value.append(v.to_pref())
        self.db.new_api.set_pref('user_template_functions', pref_value)
        funcs = compile_user_template_functions(pref_value)
        self.db.new_api.set_user_template_functions(funcs)
        self.gui.library_view.model().refresh()
        load_user_template_functions(self.db.library_id, [], funcs)
        return False


if __name__ == '__main__':
    from PyQt5.Qt import QApplication
    app = QApplication([])
    test_widget('Advanced', 'StoredTemplates')
