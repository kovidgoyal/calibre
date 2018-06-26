# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.pdf_input_ui import Ui_Form
from calibre.gui2.convert import Widget, QDoubleSpinBox
from calibre.ebooks.conversion.config import OPTIONS


class PluginWidget(Widget, Ui_Form):

    TITLE = _('PDF input')
    HELP = _('Options specific to')+' PDF '+_('input')
    COMMIT_NAME = 'pdf_input'
    ICON = I('mimetypes/pdf.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['input']['pdf'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)

    def set_value_handler(self, g, val):
        if val is None and isinstance(g, QDoubleSpinBox):
            g.setValue(0.0)
            return True
