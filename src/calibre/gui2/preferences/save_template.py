#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import QWidget, pyqtSignal

from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences.save_template_ui import Ui_Form
from calibre.library.save_to_disk import FORMAT_ARG_DESCS, Formatter, get_component_metadata, preprocess_template
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
        help_text = self.orig_help_text
        if name == 'send_to_device':
            help_text = help_text + ' ' + _(
                'This setting can be overridden for <b>individual devices</b>,'
                ' by clicking the device icon and choosing "Configure this device".')
        self.help_label.setText(help_text + ' ' +
            _('<b>Title and series</b> will have articles moved to the end unless '
              'you change the tweak "{}"').format('save_template_title_series_sorting'))
        rows = []
        for var in variables:
            rows.append(f'<tr><td>{var}</td><td>&nbsp;</td><td>{FORMAT_ARG_DESCS[var]}</td></tr>')
        rows.append('<tr><td>{}&nbsp;</td><td>&nbsp;</td><td>{}</td></tr>'.format(
            _('Any custom field'),
            _('The lookup name of any custom field (these names begin with "#").')))
        table = '<table>{}</table>'.format('\n'.join(rows))
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
        mi = tuple(map(db.new_api.get_metadata, view.get_selected_ids()[:10]))
        if not mi:
            error_dialog(self, _('Must select books'),
                         _('One or more books must be selected so the template '
                           'editor can show the template results'), show=True)
            return
        from calibre.library.save_to_disk import config
        opts = config().parse()
        if self.option_name == 'save_to_disk':
            timefmt = opts.timefmt
        elif self.option_name == 'send_to_device':
            timefmt = opts.send_timefmt

        template = self.opt_template.text()
        fmt_args = [get_component_metadata(template, one, one.get('id'), timefmt=timefmt) for one in mi]
        t = TemplateDialog(self, template, fm=self.field_metadata, kwargs=fmt_args, mi=mi, formatter=Formatter)
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
            if not t or t == tmpl:
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
