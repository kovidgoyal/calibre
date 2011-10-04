# coding: utf-8

__license__   = 'GPL v3'
__copyright__ = '2011, Anthon van der Neut <A.van.der.Neut@ruamel.eu>'


from calibre.gui2.convert.djvu_input_ui import Ui_Form
from calibre.gui2.convert import Widget, QDoubleSpinBox

class PluginWidget(Widget, Ui_Form):

    TITLE = _('DJVU Input')
    HELP = _('Options specific to')+' DJVU '+_('input')
    COMMIT_NAME = 'djvu_input'
    ICON = I('mimetypes/djvu.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
            ['use_djvutxt', ])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)

