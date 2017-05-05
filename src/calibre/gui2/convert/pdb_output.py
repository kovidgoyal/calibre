# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.pdb_output_ui import Ui_Form
from calibre.gui2.convert import Widget

format_model = None


class PluginWidget(Widget, Ui_Form):

    TITLE = _('PDB output')
    HELP = _('Options specific to')+' PDB '+_('output')
    COMMIT_NAME = 'pdb_output'
    ICON = I('mimetypes/unknown.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, ['format', 'inline_toc', 'pdb_output_encoding'])
        self.db, self.book_id = db, book_id

        for x in get_option('format').option.choices:
            self.opt_format.addItem(x)

        self.initialize_options(get_option, get_help, db, book_id)
