# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QFormLayout, QComboBox, QCheckBox, QLineEdit, QDoubleSpinBox, QSizePolicy

from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.config import OPTIONS

paper_size_model = None
orientation_model = None


class PluginWidget(Widget):

    TITLE = _('DOCX output')
    HELP = _('Options specific to')+' DOCX '+_('output')
    COMMIT_NAME = 'docx_output'
    ICON = I('mimetypes/docx.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['output']['docx'])
        for x in get_option('docx_page_size').option.choices:
            self.opt_docx_page_size.addItem(x)

        self.initialize_options(get_option, get_help, db, book_id)
        self.layout().setFieldGrowthPolicy(self.layout().ExpandingFieldsGrow)

    def setupUi(self, *a):
        self.l = l = QFormLayout(self)
        self.opt_docx_page_size = QComboBox(self)
        l.addRow(_('Paper si&ze:'), self.opt_docx_page_size)
        self.opt_docx_custom_page_size = w = QLineEdit(self)
        w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        l.addRow(_('&Custom size:'), w)
        for i, text in enumerate((_('Page &left margin'), _('Page &top margin'), _('Page &right margin'), _('Page &bottom margin'))):
            m = 'left top right bottom'.split()[i]
            w = QDoubleSpinBox(self)
            w.setRange(-100, 500), w.setSuffix(' pt'), w.setDecimals(1)
            setattr(self, 'opt_docx_page_margin_' + m, w)
            l.addRow(text + ':', w)
        self.opt_docx_no_toc = QCheckBox(_('Do not insert the &Table of Contents as a page at the start of the document'))
        l.addRow(self.opt_docx_no_toc)
        self.opt_docx_no_cover = QCheckBox(_('Do not insert &cover as image at start of document'))
        l.addRow(self.opt_docx_no_cover)
        self.opt_preserve_cover_aspect_ratio = QCheckBox(_('Preserve the aspect ratio of the image inserted as cover'))
        l.addRow(self.opt_preserve_cover_aspect_ratio)
