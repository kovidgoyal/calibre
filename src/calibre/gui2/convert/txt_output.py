# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.txt_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.txt.newlines import TxtNewlines
from calibre.gui2.widgets import BasicComboModel

newline_model = None

class PluginWidget(Widget, Ui_Form):

    TITLE = _('TXT Output')
    HELP = _('Options specific to')+' TXT '+_('output')
    COMMIT_NAME = 'txt_output'
    ICON = I('mimetypes/txt.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
        ['newline', 'max_line_length', 'force_max_line_length',
        'inline_toc', 'markdown_format', 'keep_links', 'keep_image_references',
        'output_encoding'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)

        default = self.opt_newline.currentText()

        global newline_model
        if newline_model is None:
            newline_model = BasicComboModel(TxtNewlines.NEWLINE_TYPES.keys())
        self.newline_model = newline_model
        self.opt_newline.setModel(self.newline_model)

        default_index = self.opt_newline.findText(default)
        system_index = self.opt_newline.findText('system')
        self.opt_newline.setCurrentIndex(default_index if default_index != -1 else system_index if system_index != -1 else 0)
