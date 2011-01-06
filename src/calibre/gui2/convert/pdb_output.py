# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.pdb_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.pdb import FORMAT_WRITERS
from calibre.gui2.widgets import BasicComboModel

format_model = None

class PluginWidget(Widget, Ui_Form):

    TITLE = _('PDB Output')
    HELP = _('Options specific to')+' PDB '+_('output')
    COMMIT_NAME = 'pdb_output'
    ICON = I('mimetypes/unknown.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, ['format', 'inline_toc', 'pdb_output_encoding'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)

        default = self.opt_format.currentText()

        global format_model
        if format_model is None:
            format_model = BasicComboModel(FORMAT_WRITERS.keys())
        self.format_model = format_model
        self.opt_format.setModel(self.format_model)

        default_index = self.opt_format.findText(default)
        format_index = self.opt_format.findText('doc')
        self.opt_format.setCurrentIndex(default_index if default_index != -1 else format_index if format_index != -1 else 0)

