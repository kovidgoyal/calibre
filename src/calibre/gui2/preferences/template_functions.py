#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json, traceback

from PyQt5.Qt import QDialogButtonBox

from calibre.gui2 import error_dialog, warning_dialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.template_functions_ui import Ui_Form
from calibre.gui2.widgets import PythonHighlighter
from calibre.utils.formatter_functions import (formatter_functions,
                        compile_user_function, load_user_template_functions)


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.db = gui.library_view.model().db

        help_text = _('''
        <p>Here you can add and remove functions used in template processing. A
        template function is written in Python. It takes information from the
        book, processes it in some way, then returns a string result. Functions
        defined here are usable in templates in the same way that builtin
        functions are usable. The function must be named <b>evaluate</b>, and
        must have the signature shown below.</p>
        <p><code>evaluate(self, formatter, kwargs, mi, locals, your parameters)
        &rarr; returning a unicode string</code></p>
        <p>The parameters of the evaluate function are:
        <ul>
        <li><b>formatter</b>: the instance of the formatter being used to
        evaluate the current template. You can use this to do recursive
        template evaluation.</li>
        <li><b>kwargs</b>: a dictionary of metadata. Field values are in this
        dictionary.
        <li><b>mi</b>: a Metadata instance. Used to get field information.
        This parameter can be None in some cases, such as when evaluating
        non-book templates.</li>
        <li><b>locals</b>: the local variables assigned to by the current
        template program.</li>
        <li><b>your parameters</b>: You must supply one or more formal
        parameters. The number must match the arg count box, unless arg count is
        -1 (variable number or arguments), in which case the last argument must
        be *args. At least one argument is required, and is usually the value of
        the field being operated upon. Note that when writing in basic template
        mode, the user does not provide this first argument. Instead it is
        supplied by the formatter.</li>
        </ul></p>
        <p>
        The following example function checks the value of the field. If the
        field is not empty, the field's value is returned, otherwise the value
        EMPTY is returned.
        <pre>
        name: my_ifempty
        arg count: 1
        doc: my_ifempty(val) -- return val if it is not empty, otherwise the string 'EMPTY'
        program code:
        def evaluate(self, formatter, kwargs, mi, locals, val):
            if val:
                return val
            else:
                return 'EMPTY'</pre>
        This function can be called in any of the three template program modes:
        <ul>
        <li>single-function mode: {tags:my_ifempty()}</li>
        <li>template program mode: {tags:'my_ifempty($)'}</li>
        <li>general program mode: program: my_ifempty(field('tags'))</li>
        </p>
        ''')
        self.textBrowser.setHtml(help_text)

    def initialize(self):
        try:
            self.builtin_source_dict = json.loads(P('template-functions.json', data=True,
                allow_user_override=False).decode('utf-8'))
        except:
            traceback.print_exc()
            self.builtin_source_dict = {}

        self.funcs = formatter_functions().get_functions()
        self.builtins = formatter_functions().get_builtins_and_aliases()

        self.build_function_names_box()
        self.function_name.currentIndexChanged[str].connect(self.function_index_changed)
        self.function_name.editTextChanged.connect(self.function_name_edited)
        self.argument_count.valueChanged.connect(self.enable_replace_button)
        self.documentation.textChanged.connect(self.enable_replace_button)
        self.program.textChanged.connect(self.enable_replace_button)
        self.create_button.clicked.connect(self.create_button_clicked)
        self.delete_button.clicked.connect(self.delete_button_clicked)
        self.create_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.replace_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_button_clicked)
        self.replace_button.clicked.connect(self.replace_button_clicked)
        self.program.setTabStopWidth(20)
        self.highlighter = PythonHighlighter(self.program.document())

    def enable_replace_button(self):
        self.replace_button.setEnabled(self.delete_button.isEnabled())

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
            self.program.setReadOnly(False)
        else:
            error_dialog(self.gui, _('Template functions'),
                         _('Function not defined'), show=True)

    def create_button_clicked(self):
        self.changed_signal.emit()
        name = unicode(self.function_name.currentText())
        if name in self.funcs:
            error_dialog(self.gui, _('Template functions'),
                         _('Name %s already used')%(name,), show=True)
            return
        if self.argument_count.value() == 0:
            box = warning_dialog(self.gui, _('Template functions'),
                         _('Argument count should be -1 or greater than zero. '
                           'Setting it to zero means that this function cannot '
                           'be used in single function mode.'), det_msg='',
                         show=False)
            box.bb.setStandardButtons(box.bb.standardButtons() | QDialogButtonBox.Cancel)
            box.det_msg_toggle.setVisible(False)
            if not box.exec_():
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
        self.replace_button.setEnabled(False)
        self.program.setReadOnly(False)

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
            if hasattr(func, 'program_text') and func.program_text:
                self.program.setPlainText(func.program_text)
            elif txt in self.builtin_source_dict:
                self.program.setPlainText(self.builtin_source_dict[txt])
            else:
                self.program.setPlainText(_('function source code not available'))
            self.documentation.setReadOnly(True)
            self.argument_count.setReadOnly(True)
            self.program.setReadOnly(True)
            self.delete_button.setEnabled(False)
        else:
            self.program.setPlainText(func.program_text)
            self.delete_button.setEnabled(True)
            self.program.setReadOnly(False)
        self.replace_button.setEnabled(False)

    def replace_button_clicked(self):
        self.delete_button_clicked()
        self.create_button_clicked()

    def refresh_gui(self, gui):
        pass

    def commit(self):
        # formatter_functions().reset_to_builtins()
        pref_value = []
        for name, cls in self.funcs.iteritems():
            if name not in self.builtins:
                pref_value.append((cls.name, cls.doc, cls.arg_count, cls.program_text))
        self.db.new_api.set_pref('user_template_functions', pref_value)
        load_user_template_functions(self.db.library_id, pref_value)
        return False


if __name__ == '__main__':
    from PyQt5.Qt import QApplication
    app = QApplication([])
    test_widget('Advanced', 'TemplateFunctions')
