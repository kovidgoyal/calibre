__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.fb2_input_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.config import OPTIONS


class PluginWidget(Widget, Ui_Form):

    TITLE = _('FB2 input')
    HELP = _('Options specific to')+' FB2 '+_('input')
    COMMIT_NAME = 'fb2_input'
    ICON = 'mimetypes/fb2.png'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['input']['fb2'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
