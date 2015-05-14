# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.docx_output_ui import Ui_Form
from calibre.gui2.convert import Widget

paper_size_model = None
orientation_model = None

class PluginWidget(Widget, Ui_Form):

    TITLE = _('DOCX Output')
    HELP = _('Options specific to')+' DOCX '+_('output')
    COMMIT_NAME = 'docx_output'
    ICON = I('mimetypes/docx.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, [
            'docx_page_size', 'docx_custom_page_size', 'docx_no_cover', 'docx_no_toc',
        ])
        for x in get_option('docx_page_size').option.choices:
            self.opt_docx_page_size.addItem(x)

        self.initialize_options(get_option, get_help, db, book_id)
        self.layout().setFieldGrowthPolicy(self.layout().ExpandingFieldsGrow)
