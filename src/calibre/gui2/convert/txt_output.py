# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import Qt

from calibre.gui2.convert.txt_output_ui import Ui_Form
from calibre.gui2.convert import Widget

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
        'txt_output_encoding'])
        self.db, self.book_id = db, book_id        
        for x in get_option('newline').option.choices:
            self.opt_newline.addItem(x)        
        self.initialize_options(get_option, get_help, db, book_id)

        self.opt_markdown_format.stateChanged.connect(self.enable_markdown_format)
        self.enable_markdown_format(self.opt_markdown_format.checkState())

    def break_cycles(self):
        Widget.break_cycles(self)
        
        try:
            self.opt_markdown_format.stateChanged.disconnect()
        except:
            pass
        
    def enable_markdown_format(self, state):
        if state == Qt.Checked:
            state = True
        else:
            state = False
        self.opt_keep_links.setEnabled(state)
        self.opt_keep_image_references.setEnabled(state)
        