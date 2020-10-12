# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.fb2_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.config import OPTIONS

format_model = None


class PluginWidget(Widget, Ui_Form):

    TITLE = _('FB2 output')
    HELP = _('Options specific to')+' FB2 '+_('output')
    COMMIT_NAME = 'fb2_output'
    ICON = I('mimetypes/fb2.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['output']['fb2'])
        self.db, self.book_id = db, book_id
        for x in ('toc', 'files', 'nothing'):
            self.opt_sectionize.addItem(x)
        for x in get_option('fb2_genre').option.choices:
            self.opt_fb2_genre.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)
