# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from PyQt4.Qt import SIGNAL

from calibre.gui2.convert.pdf_input_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2 import qstring_to_unicode, error_dialog

class PluginWidget(Widget, Ui_Form):

    TITLE = _('PDF Input')
    HELP = _('Options specific to')+' PDF '+_('input')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, 'pdf_input',
            ['no_images', 'unwrap_factor', 'remove_header', 'header_regex',
            'remove_footer', 'footer_regex'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)

        self.opt_header_regex.setEnabled(self.opt_remove_header.isChecked())
        self.opt_footer_regex.setEnabled(self.opt_remove_footer.isChecked())

        self.connect(self.opt_remove_header, SIGNAL('stateChanged(int)'), self.header_regex_state)
        self.connect(self.opt_remove_footer, SIGNAL('stateChanged(int)'), self.footer_regex_state)

    def header_regex_state(self, state):
        self.opt_header_regex.setEnabled(state)

    def footer_regex_state(self, state):
        self.opt_footer_regex.setEnabled(state)

    def pre_commit_check(self):
        for x in ('header_regex', 'footer_regex'):
            x = getattr(self, 'opt_'+x)
            try:
                pat = qstring_to_unicode(x.text())
                re.compile(pat)
            except Exception, err:
                error_dialog(self, _('Invalid regular expression'),
                             _('Invalid regular expression: %s')%err).exec_()
                return False
        return True
