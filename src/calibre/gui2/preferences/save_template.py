#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget, pyqtSignal

from calibre.gui2 import error_dialog
from calibre.gui2.preferences.save_template_ui import Ui_Form
from calibre.library.save_to_disk import FORMAT_ARG_DESCS, preprocess_template
from calibre.utils.formatter import validation_formatter


class SaveTemplate(QWidget, Ui_Form):

    changed_signal = pyqtSignal()

    def __init__(self, *args):
        QWidget.__init__(self, *args)
        Ui_Form.__init__(self)
        self.setupUi(self)

    def initialize(self, name, default, help):
        variables = sorted(FORMAT_ARG_DESCS.keys())
        rows = []
        for var in variables:
            rows.append(u'<tr><td>%s</td><td>&nbsp;</td><td>%s</td></tr>'%
                    (var, FORMAT_ARG_DESCS[var]))
        rows.append(u'<tr><td>%s&nbsp;</td><td>&nbsp;</td><td>%s</td></tr>'%(
            _('Any custom field'),
            _('The lookup name of any custom field. These names begin with "#")')))
        table = u'<table>%s</table>'%(u'\n'.join(rows))
        self.template_variables.setText(table)

        self.opt_template.initialize(name+'_template_history',
                default, help)
        self.opt_template.editTextChanged.connect(self.changed)
        self.opt_template.currentIndexChanged.connect(self.changed)
        self.option_name = name

    def changed(self, *args):
        self.changed_signal.emit()

    def validate(self):
        '''
        Do a syntax check on the format string. Doing a semantic check
        (verifying that the fields exist) is not useful in the presence of
        custom fields, because they may or may not exist.
        '''
        tmpl = preprocess_template(self.opt_template.text())
        try:
            validation_formatter.validate(tmpl)
        except Exception, err:
            error_dialog(self, _('Invalid template'),
                    '<p>'+_('The template %s is invalid:')%tmpl + \
                    '<br>'+str(err), show=True)
            return False
        return True

    def set_value(self, val):
        self.opt_template.set_value(val)

    def save_settings(self, config, name):
        val = unicode(self.opt_template.text())
        config.set(name, val)
        self.opt_template.save_history(self.option_name+'_template_history')





