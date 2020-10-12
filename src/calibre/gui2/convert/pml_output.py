# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.pmlz_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.config import OPTIONS

format_model = None


class PluginWidget(Widget, Ui_Form):

    TITLE = _('PMLZ output')
    HELP = _('Options specific to')+' PMLZ '+_('output')
    COMMIT_NAME = 'pmlz_output'
    ICON = I('mimetypes/unknown.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['output']['pml'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
