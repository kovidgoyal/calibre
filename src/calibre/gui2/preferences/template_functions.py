#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback

from calibre.gui2 import error_dialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.template_functions_ui import Ui_Form
from calibre.utils.formatter_functions import formatter_functions, compile_user_function


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.db = gui.library_view.model().db
        self.current_plugboards = self.db.prefs.get('plugboards',{})
        help_text = _('''
        <p>Here you can add and remove functions used in template processing. A
        template function is written in python. It takes information from the
        book, processes it in some way, then returns a string result. Functions
        defined here are usable in templates in the same way that builtin
        functions are usable. The function must be named evaluate, and must
        have the signature shown below.</p>
        <p><code>evaluate(self, formatter, kwargs, mi, locals, your_arguments)
        &rarr; returning a unicode string</code></p>
        <p>The arguments to evaluate are:
        <ul>
        <li><b>formatter:</b> the instance of the formatter being used to
        evaluate the current template. You can use this to do recursive
        template evaluation.</li>
        <li><b>kwargs:</b> a dictionary of metadata. Field values are in this
        dictionary. mi: a Metadata instance. Used to get field information.
        This parameter can be None in some cases, such as when evaluating
        non-book templates.</li>
        <li><b>locals:</b> the local variables assigned to by the current
        template program.</li>
        <li><b>Your_arguments</b> must be one or more parameter (number
        matching the arg count box), or the value *args for a variable number
        of arguments. These are values passed into the function. One argument
        is required, and is usually the value of the field being operated upon.
        Note that when writing in basic template mode, the user does not
        provide this first argument. Instead it is the value of the field the
        function is operating upon.</li>
        </ul></p>
        <p>
        The following example function looks for various values in the tags
        metadata field, returning those values that appear in tags.
        <pre>
        def evaluate(self, formatter, kwargs, mi, locals, val):
            awards=['allbooks', 'PBook', 'ggff']
            return ', '.join([t for t in kwargs.get('tags') if t in awards])
        </pre>
        </p>
        ''')
        self.textBrowser.setHtml(help_text)

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

