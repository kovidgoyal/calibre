# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.pdf_output_ui import Ui_Form
from calibre.gui2.convert import Widget

paper_size_model = None
orientation_model = None

class PluginWidget(Widget, Ui_Form):

    TITLE = _('PDF Output')
    HELP = _('Options specific to')+' PDF '+_('output')
    COMMIT_NAME = 'pdf_output'
    ICON = I('mimetypes/pdf.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, ['paper_size', 'custom_size',
            'orientation', 'preserve_cover_aspect_ratio', 'pdf_serif_family',
            'pdf_sans_family', 'pdf_mono_family', 'pdf_standard_font',
            'pdf_default_font_size', 'pdf_mono_font_size'])
        self.db, self.book_id = db, book_id

        for x in get_option('paper_size').option.choices:
            self.opt_paper_size.addItem(x)
        for x in get_option('orientation').option.choices:
            self.opt_orientation.addItem(x)
        for x in get_option('pdf_standard_font').option.choices:
            self.opt_pdf_standard_font.addItem(x)

        self.initialize_options(get_option, get_help, db, book_id)

