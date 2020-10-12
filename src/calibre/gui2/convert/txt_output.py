# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.txt_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.config import OPTIONS


class PluginWidget(Widget, Ui_Form):

    TITLE = _('TXT output')
    HELP = _('Options specific to')+' TXT '+_('output')
    COMMIT_NAME = 'txt_output'
    ICON = I('mimetypes/txt.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['output']['txt'])
        self.db, self.book_id = db, book_id
        for x in get_option('newline').option.choices:
            self.opt_newline.addItem(x)
        for x in get_option('txt_output_formatting').option.choices:
            self.opt_txt_output_formatting.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)

    def break_cycles(self):
        Widget.break_cycles(self)
