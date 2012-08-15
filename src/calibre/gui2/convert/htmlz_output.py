# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.htmlz_output_ui import Ui_Form
from calibre.gui2.convert import Widget

format_model = None

class PluginWidget(Widget, Ui_Form):

    TITLE = _('HTMLZ Output')
    HELP = _('Options specific to')+' HTMLZ '+_('output')
    COMMIT_NAME = 'htmlz_output'
    ICON = I('mimetypes/html.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, ['htmlz_css_type', 'htmlz_class_style',
            'htmlz_title_filename'])
        self.db, self.book_id = db, book_id
        for x in get_option('htmlz_css_type').option.choices:
            self.opt_htmlz_css_type.addItem(x)
        for x in get_option('htmlz_class_style').option.choices:
            self.opt_htmlz_class_style.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)
