#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>

import copy
import json
import traceback

from qt.core import QDialog, QDialogButtonBox

from calibre.gui2 import choose_files, choose_save_file, error_dialog, gprefs, question_dialog, warning_dialog
from calibre.gui2.dialogs.ff_doc_editor import FFDocEditor
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences import AbortInitialize, ConfigWidgetBase, test_widget
from calibre.gui2.preferences.template_functions_ui import Ui_Form
from calibre.gui2.widgets import PythonHighlighter
from calibre.utils.formatter_functions import (
    StoredObjectType,
    compile_user_function,
    compile_user_template_functions,
    formatter_functions,
    function_object_type,
    function_pref_name,
    load_user_template_functions,
)
from calibre.utils.resources import get_path as P
from polyglot.builtins import iteritems


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
        &rarr; returning a Unicode string</code></p>
        <p>The parameters of the evaluate function are:
        <ul>
        <li><b>formatter</b>: the instance of the formatter being used to
        evaluate the current template. You can use this to do recursive
        template evaluation.</li>
        <li><b>kwargs</b>: a dictionary of metadata. Field values are in this
        dictionary.</li>
        <li><b>mi</b>: a <i>Metadata</i> instance. Used to get field information.
        This parameter can be None in some cases, such as when evaluating
        non-book templates.</li>
        <li><b>locals</b>: the local variables assigned to by the current
        template program.</li>
        <li><b>your parameters</b>: you must supply one or more formal
        parameters. The number must match the arg count box, unless arg count is
        -1 (variable number or arguments), in which case the last argument must
        be *args. Note that when a function is called in basic template
        mode at least one argument is always passed. It is
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
        self.textBrowser.adjustSize()
        self.show_hide_help_button.clicked.connect(self.show_hide_help)
        self.textBrowser_showing = not gprefs.get('template_functions_prefs_tf_show_help', True)
        self.textBrowser_height = self.textBrowser.height()
        self.show_hide_help()

        help_text = _('''
        <p>
        Here you can create, edit (replace), and delete stored templates used
        in template processing. You use a stored template in another template as
        if it were a template function, for example 'some_name(arg1, arg2...)'.</p>

        <p>Stored templates must use General Program Mode or Python Template
        Mode -- they must begin with the text '{0}' or '{1}'. You retrieve
        arguments passed to a GPM stored template using the '{2}()' template
        function, as in '{2}(var1, var2, ...)'. The passed arguments are copied
        to the named variables. Arguments passed to a Python template are in the
        '{2}' attribute (a list) of the '{3}' parameter. Arguments are always
        strings.</p>

        <p>For example, this stored GPM template checks if any items are in a
        list, returning '1' if any are found and '' if not.</p>
        <p>
        Template name: items_in_list<br>
        Template contents:<pre>
        program:
            arguments(lst='No list argument given', items='');
            r = '';
            for l in items:
                if str_in_list(lst, ',', l, '1', '') then
                    r = '1';
                    break
                fi
            rof;
            r</pre>
        You call the stored template like this:<pre>
        program: items_in_list($#genre, 'comics, foo')</pre>
        See the template language tutorial for more information.</p>
        </p>
        ''')
        self.st_textBrowser.setHtml(help_text.format('program:', 'python:', 'arguments', 'context'))
        self.st_textBrowser.adjustSize()
        self.st_show_hide_help_button.clicked.connect(self.st_show_hide_help)
        self.st_textBrowser_height = self.st_textBrowser.height()
        self.st_textBrowser_showing = not gprefs.get('template_functions_prefs_st_show_help', True)
        self.st_show_hide_help()

    def st_show_hide_help(self):
        gprefs['template_functions_prefs_st_show_help'] = not self.st_textBrowser_showing
        if self.st_textBrowser_showing:
            self.st_textBrowser.setMaximumHeight(self.st_show_hide_help_button.height())
            self.st_textBrowser_showing = False
            self.st_show_hide_help_button.setText(_('Show help'))
        else:
            self.st_textBrowser.setMaximumHeight(self.st_textBrowser_height)
            self.st_textBrowser_showing = True
            self.st_show_hide_help_button.setText(_('Hide help'))

    def show_hide_help(self):
        gprefs['template_functions_prefs_tf_show_help'] = not self.textBrowser_showing
        if self.textBrowser_showing:
            self.textBrowser.setMaximumHeight(self.show_hide_help_button.height())
            self.textBrowser_showing = False
            self.show_hide_help_button.setText(_('Show help'))
        else:
            self.textBrowser.setMaximumHeight(self.textBrowser_height)
            self.textBrowser_showing = True
            self.show_hide_help_button.setText(_('Hide help'))

    def initialize(self):
        try:
            self.builtin_source_dict = json.loads(P('template-functions.json', data=True,
                allow_user_override=False).decode('utf-8'))
        except:
            traceback.print_exc()
            self.builtin_source_dict = {}

        self.funcs = {k:v for k,v in formatter_functions().get_functions().items()
                                if v.object_type is StoredObjectType.PythonFunction}

        self.builtins = formatter_functions().get_builtins_and_aliases()

        self.st_funcs = {}
        try:
            for v in self.db.prefs.get('user_template_functions', []):
                if function_object_type(v) is not StoredObjectType.PythonFunction:
                    self.st_funcs.update({function_pref_name(v):compile_user_function(*v)})
        except:
            if question_dialog(self, _('Template functions'),
                    _('The template functions saved in the library are corrupt. '
                      "Do you want to delete them? Answering 'Yes' will delete all "
                      "the functions."), det_msg=traceback.format_exc(),
                               show_copy_button=True):
                self.db.prefs['user_template_functions'] = []
            raise AbortInitialize()

        self.show_only_user_defined.setChecked(True)
        self.show_only_user_defined.stateChanged.connect(self.show_only_user_defined_changed)
        self.build_function_names_box()
        self.function_name.currentIndexChanged.connect(self.function_index_changed)
        self.function_name.editTextChanged.connect(self.function_name_edited)
        self.argument_count.valueChanged.connect(self.enable_replace_button)
        self.documentation.textChanged.connect(self.enable_replace_button)
        self.program.textChanged.connect(self.enable_replace_button)
        self.create_button.clicked.connect(self.create_button_clicked)
        self.delete_button.clicked.connect(self.delete_button_clicked)
        self.doc_edit_button.clicked.connect(self.doc_edit_button_clicked)
        self.create_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.replace_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_button_clicked)
        self.replace_button.clicked.connect(self.replace_button_clicked)
        self.program.setTabStopDistance(20)
        self.highlighter = PythonHighlighter(self.program.document())

        self.te_textbox = self.template_editor.textbox
        self.te_name = self.template_editor.template_name
        self.st_build_function_names_box()
        self.te_name.currentIndexChanged.connect(self.st_function_index_changed)
        self.te_name.editTextChanged.connect(self.st_template_name_edited)
        self.st_create_button.clicked.connect(self.st_create_button_clicked)
        self.st_delete_button.clicked.connect(self.st_delete_button_clicked)
        self.st_import_button.clicked.connect(self.st_import_button_clicked)
        self.st_export_button.clicked.connect(self.st_export_button_clicked)
        self.st_create_button.setEnabled(False)
        self.st_delete_button.setEnabled(False)
        self.st_replace_button.setEnabled(False)
        self.st_test_template_button.setEnabled(False)
        self.st_doc_edit_button.setEnabled(False)
        self.st_clear_button.clicked.connect(self.st_clear_button_clicked)
        self.st_test_template_button.clicked.connect(self.st_test_template)
        self.st_replace_button.clicked.connect(self.st_replace_button_clicked)
        self.st_doc_edit_button.clicked.connect(self.st_doc_edit_button_clicked)

        self.st_current_program_name = ''
        self.st_current_program_text = ''
        self.st_previous_text = ''
        self.st_first_time = False

        # Attempt to properly align the buttons with the template edit widget
        self.st_button_layout.insertSpacing(0, 70)
        self.st_button_layout.insertSpacing(self.st_button_layout.indexOf(self.st_doc_edit_button), 60)
        self.st_button_layout.insertSpacing(self.st_button_layout.indexOf(self.st_test_template_button), 50)
        self.template_editor.new_doc.setFixedHeight(50)

        # get field metadata and selected books
        view = self.gui.current_view()
        rows = view.selectionModel().selectedRows()
        self.mi = []
        if rows:
            db = view.model().db
            self.fm = db.field_metadata
            for row in rows:
                if row.isValid():
                    self.mi.append(db.new_api.get_proxy_metadata(db.data.index_to_id(row.row())))

            self.template_editor.set_mi(self.mi, self.fm)

    # Python function tab

    def show_only_user_defined_changed(self, state):
        self.build_function_names_box()

    def enable_replace_button(self):
        self.replace_button.setEnabled(self.delete_button.isEnabled())

    def doc_edit_button_clicked(self):
        d = FFDocEditor(can_copy_back=True, parent=self)
        d.set_document_text(self.documentation.toPlainText())
        if d.exec() == QDialog.DialogCode.Accepted:
            self.documentation.setPlainText(d.document_text())

    def clear_button_clicked(self):
        self.build_function_names_box()
        self.program.clear()
        self.documentation.clear()
        self.argument_count.clear()
        self.create_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def function_type_string(self, name):
        if name in self.builtins:
            return ' -- ' + _('Built-in function')
        else:
            return ' -- ' + _('User function')

    def build_function_names_box(self, scroll_to=''):
        self.function_name.blockSignals(True)
        if self.show_only_user_defined.isChecked():
            func_names = sorted([k for k in self.funcs if k not in self.builtins])
        else:
            func_names = sorted(self.funcs)
        self.function_name.clear()
        self.function_name.addItem('')
        scroll_to_index = 0
        for idx,n in enumerate(func_names):
            self.function_name.addItem(n + self.function_type_string(n))
            self.function_name.setItemData(idx+1, n)
            if scroll_to and n == scroll_to:
                scroll_to_index = idx+1
        self.function_name.setCurrentIndex(0)
        self.function_name.blockSignals(False)
        if scroll_to_index:
            self.function_name.setCurrentIndex(scroll_to_index)
            if scroll_to not in self.builtins:
                self.delete_button.setEnabled(True)

    def delete_button_clicked(self):
        name = str(self.function_name.itemData(self.function_name.currentIndex()))
        if name in self.builtins:
            error_dialog(self.gui, _('Template functions'),
                         _('You cannot delete a built-in function'), show=True)
        if name in self.funcs:
            del self.funcs[name]
            self.changed_signal.emit()
            self.create_button.setEnabled(True)
            self.delete_button.setEnabled(False)
            self.build_function_names_box()
            self.program.setReadOnly(False)
        else:
            error_dialog(self.gui, _('Template functions'),
                         _('Function not defined'), show=True)

    def check_errors_before_save(self, name, for_replace=False):
        # Returns True if there is an error
        if not name:
            error_dialog(self.gui, _('Template functions'),
                         _('Name cannot be empty'), show=True)
            return True
        if not for_replace and name in self.funcs:
            error_dialog(self.gui, _('Template functions'),
                         _('Name %s already used')%(name,), show=True)
            return True
        if name in {function_pref_name(v) for v in
                        self.db.prefs.get('user_template_functions', [])
                        if function_object_type(v) is not StoredObjectType.PythonFunction}:
            error_dialog(self.gui, _('Template functions'),
                         _('The name {} is already used for stored template').format(name), show=True)
            return True
        if self.argument_count.value() == 0:
            if not question_dialog(self.gui, _('Template functions'),
                         _('Setting argument count to zero means that this '
                           'function cannot be used in single function mode. '
                           'Is this OK?'),
                         det_msg='',
                         show_copy_button=False,
                         default_yes=False,
                         skip_dialog_name='template_functions_zero_args_warning',
                         skip_dialog_msg='Ask this question again',
                         yes_text=_('Save the function'),
                         no_text=_('Cancel the save')):
                print('cancelled')
                return True
        try:
            prog = str(self.program.toPlainText())
            compile_user_function(name, str(self.documentation.toPlainText()),
                                        self.argument_count.value(), prog)
        except:
            error_dialog(self.gui, _('Template functions'),
                         _('Exception while compiling function'), show=True,
                         det_msg=traceback.format_exc())
            return True
        return False

    def create_button_clicked(self, use_name=None, need_error_checks=True):
        name = use_name if use_name else str(self.function_name.currentText())
        name = name.split(' -- ')[0]
        if need_error_checks and self.check_errors_before_save(name, for_replace=False):
            return
        self.changed_signal.emit()
        try:
            prog = str(self.program.toPlainText())
            cls = compile_user_function(name, str(self.documentation.toPlainText()),
                                        self.argument_count.value(), prog)
            self.funcs[name] = cls
            self.build_function_names_box(scroll_to=name)
        except:
            error_dialog(self.gui, _('Template functions'),
                         _('Exception while compiling function'), show=True,
                         det_msg=traceback.format_exc())

    def function_name_edited(self, txt):
        txt = txt.split(' -- ')[0]
        if txt not in self.funcs:
            self.function_name.blockSignals(True)
            self.function_name.setEditText(txt)
            self.function_name.blockSignals(False)
        self.documentation.setReadOnly(False)
        self.argument_count.setReadOnly(False)
        self.create_button.setEnabled(True)
        self.replace_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.program.setReadOnly(False)

    def function_index_changed(self, idx):
        txt = self.function_name.itemData(idx)
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
        name = str(self.function_name.itemData(self.function_name.currentIndex()))
        if self.check_errors_before_save(name, for_replace=True):
            return
        self.delete_button_clicked()
        self.create_button_clicked(use_name=name, need_error_checks=False)

    def refresh_gui(self, gui):
        pass

    # Stored template tab

    def st_test_template(self):
        if self.mi:
            self.st_replace_button_clicked()
            all_funcs = copy.copy(formatter_functions().get_functions())
            for n,f in self.st_funcs.items():
                all_funcs[n] = f
            t = TemplateDialog(self.gui, self.st_previous_text,
                   mi=self.mi, fm=self.fm, text_is_placeholder=self.st_first_time,
                   all_functions=all_funcs)
            t.setWindowTitle(_('Template tester'))
            if t.exec() == QDialog.DialogCode.Accepted:
                self.st_previous_text = t.rule[1]
                self.st_first_time = False
        else:
            error_dialog(self.gui, _('Template functions'),
                         _('Cannot "test" when no books are selected'), show=True)

    def st_clear_button_clicked(self):
        self.st_build_function_names_box()
        self.te_textbox.clear()
        self.template_editor.new_doc.clear()
        self.st_create_button.setEnabled(False)
        self.st_delete_button.setEnabled(False)
        self.st_doc_edit_button.setEnabled(False)
        self.st_replace_button.setEnabled(False)
        self.st_current_program_name = ''

    def st_build_function_names_box(self, scroll_to=''):
        self.te_name.blockSignals(True)
        func_names = sorted(self.st_funcs)
        self.te_name.setMinimumContentsLength(40)
        self.te_name.clear()
        self.te_name.addItem('')
        self.te_name.addItems(func_names)
        self.te_name.setCurrentIndex(0)
        self.te_name.blockSignals(False)
        if scroll_to:
            idx = self.te_name.findText(scroll_to)
            if idx >= 0:
                self.te_name.setCurrentIndex(idx)

    def st_import_button_clicked(self):
        if self.st_replace_button.isEnabled():
            error_dialog(self, _('Import stored template'),
                         _('You are currently editing a stored template. Save or clear it'), show=True)
            return
        filename = choose_files(self, 'st_import_export_stored_template',
                _('Import template from file'),
                filters=[(_('Saved stored template'), ['txt'])],
                select_only_single_file=True)
        if filename:
            self.st_clear_button_clicked()
            try:
                with open(filename[0]) as f:
                    fields = json.load(f)
                    name = fields['name']
                    if name in self.st_funcs:
                        if not question_dialog(self, _('Import stored template'),
                                               _('A template with the name "{}" already exists. '
                                                 'Do you want to overwrite it?').format(name),
                                               show_copy_button=False):
                            return
                self.te_name.setCurrentText(name)
                self.te_textbox.setPlainText(fields['template'])
                self.template_editor.new_doc.setPlainText(fields['doc'])
            except Exception as err:
                traceback.print_exc()
                error_dialog(self, _('Import template'),
                             _('<p>Could not import the template. Error:<br>%s')%err, show=True)

    def st_export_button_clicked(self):
        if not self.te_name.currentText() or not self.te_textbox.toPlainText():
            error_dialog(self, _('Export stored template'),
                         _('No template has been selected for export'), show_copy_button=False, show=True)
            return
        filename = choose_save_file(self, 'st_import_export_stored_template',
                _('Export template to file'),
                filters=[(_('Saved stored template'), ['txt'])],
                initial_filename=self.te_name.currentText())
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump({'name': self.te_name.currentText(),
                               'template': self.te_textbox.toPlainText(),
                               'doc': self.template_editor.new_doc.toPlainText()},
                               f, indent=1)
            except Exception as err:
                traceback.print_exc()
                error_dialog(self, _('Export template'),
                             _('<p>Could not export the template. Error:<br>%s')%err, show=True)

    def st_delete_button_clicked(self):
        name = str(self.te_name.currentText())
        if name in self.st_funcs:
            del self.st_funcs[name]
            self.changed_signal.emit()
            self.st_create_button.setEnabled(True)
            self.st_delete_button.setEnabled(False)
            self.st_doc_edit_button.setEnabled(False)
            self.st_build_function_names_box()
            self.te_textbox.setReadOnly(False)
            self.st_current_program_name = ''
        else:
            error_dialog(self.gui, _('Stored templates'),
                         _('Function not defined'), show=True)

    def st_create_button_clicked(self, use_name=None):
        self.changed_signal.emit()
        name = use_name if use_name else str(self.te_name.currentText())
        for k,v in formatter_functions().get_functions().items():
            if k == name and v.object_type is StoredObjectType.PythonFunction:
                error_dialog(self.gui, _('Stored templates'),
                         _('The name {} is already used by a template function').format(name), show=True)
        try:
            prog = str(self.te_textbox.toPlainText())
            if not prog.startswith(('program:', 'python:')):
                error_dialog(self.gui, _('Stored templates'),
                     _("The stored template must begin with '{0}' or '{1}'").format('program:', 'python:'), show=True)

            cls = compile_user_function(name, str(self.template_editor.new_doc.toPlainText()),
                                        0, prog)
            self.st_funcs[name] = cls
            self.st_build_function_names_box(scroll_to=name)
        except:
            error_dialog(self.gui, _('Stored templates'),
                         _('Exception while storing template'), show=True,
                         det_msg=traceback.format_exc())

    def st_template_name_edited(self, txt):
        b = txt in self.st_funcs
        self.st_create_button.setEnabled(not b)
        self.st_replace_button.setEnabled(b)
        self.st_delete_button.setEnabled(b)
        self.st_test_template_button.setEnabled(b)
        self.te_textbox.setReadOnly(False)
        self.st_doc_edit_button.setEnabled(True)

    def st_function_index_changed(self, idx):
        txt = self.te_name.currentText()
        if self.st_current_program_name:
            if self.st_current_program_text != self.te_textbox.toPlainText():
                box = warning_dialog(self.gui, _('Template functions'),
                         _('Changes to the current template will be lost. OK?'), det_msg='',
                         show=False, show_copy_button=False)
                box.bb.setStandardButtons(box.bb.standardButtons() |
                                          QDialogButtonBox.StandardButton.Cancel)
                box.det_msg_toggle.setVisible(False)
                if not box.exec():
                    self.te_name.blockSignals(True)
                    dex = self.te_name.findText(self.st_current_program_name)
                    self.te_name.setCurrentIndex(dex)
                    self.te_name.blockSignals(False)
                    return
        self.st_create_button.setEnabled(False)
        self.st_current_program_name = txt
        if not txt:
            self.te_textbox.clear()
            self.template_editor.new_doc.clear()
            return
        func = self.st_funcs[txt]
        self.st_current_program_text = func.program_text
        self.template_editor.new_doc.setPlainText(func.doc)
        self.te_textbox.setPlainText(func.program_text)
        self.st_template_name_edited(txt)

    def st_replace_button_clicked(self):
        name = str(self.te_name.currentText())
        self.st_current_program_text = self.te_textbox.toPlainText()
        self.st_delete_button_clicked()
        self.st_create_button_clicked(use_name=name)

    def st_doc_edit_button_clicked(self):
        d = FFDocEditor(can_copy_back=True, parent=self)
        d.set_document_text(self.template_editor.new_doc.toPlainText())
        if d.exec() == QDialog.DialogCode.Accepted:
            self.template_editor.new_doc.setPlainText(d.document_text())

    def commit(self):
        pref_value = []
        for name, cls in iteritems(self.funcs):
            if name not in self.builtins:
                pref_value.append(cls.to_pref())
        for v in self.st_funcs.values():
            pref_value.append(v.to_pref())
        self.db.new_api.set_pref('user_template_functions', pref_value)
        funcs = compile_user_template_functions(pref_value)
        self.db.new_api.set_user_template_functions(funcs)
        self.gui.library_view.model().refresh()
        self.gui.library_view.model().research()
        load_user_template_functions(self.db.library_id, [], funcs)
        return False


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.ui import get_gui
    from calibre.library import db
    app = Application([])
    app.current_db = db()
    get_gui.ans = app
    test_widget('Advanced', 'TemplateFunctions')
    del app
