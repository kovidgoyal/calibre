#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.gui2.convert.docx_input_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.config import OPTIONS


class PluginWidget(Widget, Ui_Form):

    TITLE = _('DOCX input')
    HELP = _('Options specific to')+' DOCX '+_('input')
    COMMIT_NAME = 'docx_input'
    ICON = 'mimetypes/docx.png'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['input']['docx'])
        self.initialize_options(get_option, get_help, db, book_id)
