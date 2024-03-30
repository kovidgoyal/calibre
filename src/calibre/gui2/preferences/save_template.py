#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import QWidget, pyqtSignal

from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences.save_template_ui import Ui_Form
from calibre.library.save_to_disk import FORMAT_ARG_DESCS, preprocess_template
from calibre.utils.formatter import validation_formatter


class SaveTemplate(QWidget, Ui_Form):

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        Ui_Form.__init__(self)
        self.setupUi(self)
        self.orig_help_text = self.help_label.text()

    def initialize(self, name, default, help, field_metadata):
        variables = sorted(FORMAT_ARG_DESCS.keys())
        if name == 'send_to_device':
            self.help_label.setText(self.orig_help_text + ' ' + _(
                'This setting can be overridden for <b>individual devices</b>,'
                ' by clicking the device icon and choosing "Configure this device".'))
        rows = []
        for var in variables:
            rows.append('<tr><td>%s</td><td>&nbsp;</td><td>%s</td></tr>'%
                    (var, FORMAT_ARG_DESCS[var]))
        rows.append('<tr><td>%s&nbsp;</td><td>&nbsp;</td><td>%s</td></tr>'%(
            _('Any custom field'),
            _('The lookup name of any custom field (these names begin with "#").')))
        table = '<table>%s</table>'%('\n'.join(rows))
        self.template_variables.setText(table)

        self.field_metadata = field_metadata
        self.opt_template.initialize(name+'_template_history',
                default, help)
        self.opt_template.editTextChanged.connect(self.changed)
        self.opt_template.currentIndexChanged.connect(self.changed)
        self.option_name = name
        self.open_editor.clicked.connect(self.do_open_editor)

    def do_open_editor(self):
        # Try to get selected books
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db
        view = get_gui().library_view
        mi = tuple(map(db.new_api.get_proxy_metadata, view.get_selected_ids()[:10]))
        if not mi:
            error_dialog(self, _('Must select books'),
                         _('One or more books must be selected so the template '
                           'editor can show the template results'), show=True)
            return
        t = TemplateDialog(self, self.opt_template.text(), fm=self.field_metadata, mi=mi)
        t.setWindowTitle(_('Edit template'))
        if t.exec():
            self.opt_template.set_value(t.rule[1])

    def changed(self, *args):
        self.changed_signal.emit()

    def validate(self):
        '''
        Do a syntax check on the format string. Doing a semantic check
        (verifying that the fields exist) is not useful in the presence of
        custom fields, because they may or may not exist.
        '''
        tmpl = preprocess_template(self.opt_template.text())
        # Allow PTM or GPM templates without checking
        if tmpl.startswith(('program:', 'python:')):
            return True
        try:
            t = validation_formatter.validate(tmpl)
            if t.find(validation_formatter._validation_string) < 0:
                return question_dialog(self, _('Constant template'),
                    _('The template contains no {fields}, so all '
                      'books will have the same name. Is this OK?'))
        except Exception as err:
            error_dialog(self, _('Invalid template'),
                    '<p>'+_('The template %s is invalid:')%tmpl +
                    '<br>'+str(err), show=True)
            return False
        return True

    def set_value(self, val):
        self.opt_template.set_value(val)

    def save_settings(self, config, name):
        val = str(self.opt_template.text())
        config.set(name, val)
        self.opt_template.save_history(self.option_name+'_template_history')
