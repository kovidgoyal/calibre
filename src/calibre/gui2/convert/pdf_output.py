__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


from qt.core import QHBoxLayout, QFormLayout, QDoubleSpinBox, QCheckBox, QVBoxLayout

from calibre.gui2.convert.pdf_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.utils.localization import localize_user_manual_link
from calibre.ebooks.conversion.config import OPTIONS

paper_size_model = None
orientation_model = None


class PluginWidget(Widget, Ui_Form):

    TITLE = _('PDF output')
    HELP = _('Options specific to')+' PDF '+_('output')
    COMMIT_NAME = 'pdf_output'
    ICON = 'mimetypes/pdf.png'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['output']['pdf'])
        self.db, self.book_id = db, book_id
        try:
            self.hf_label.setText(self.hf_label.text() % localize_user_manual_link(
                'https://manual.calibre-ebook.com/conversion.html#converting-to-pdf'))
        except TypeError:
            pass  # link already localized

        self.opt_paper_size.initialize(get_option('paper_size').option.choices)
        for x in get_option('unit').option.choices:
            self.opt_unit.addItem(x)
        for x in get_option('pdf_standard_font').option.choices:
            self.opt_pdf_standard_font.addItem(x)

        self.initialize_options(get_option, get_help, db, book_id)
        self.layout().setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.template_box.layout().setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.profile_size_toggled()

    def profile_size_toggled(self):
        enabled = not self.opt_use_profile_size.isChecked()
        self.opt_paper_size.setEnabled(enabled)
        self.opt_custom_size.setEnabled(enabled)
        self.opt_unit.setEnabled(enabled)

    def setupUi(self, *a):
        Ui_Form.setupUi(self, *a)
        v = self.page_margins_box.v = QVBoxLayout(self.page_margins_box)
        self.opt_pdf_use_document_margins = c = QCheckBox(_('Use page margins from the &document being converted'))
        v.addWidget(c)
        h = self.page_margins_box.h = QHBoxLayout()
        l = self.page_margins_box.l = QFormLayout()
        r = self.page_margins_box.r = QFormLayout()
        h.addLayout(l), h.addLayout(r)
        v.addLayout(h)

        def margin(which):
            w = QDoubleSpinBox(self)
            w.setRange(-100, 500), w.setSuffix(' pt'), w.setDecimals(1)
            setattr(self, 'opt_pdf_page_margin_' + which, w)
            return w

        l.addRow(_('&Left:'), margin('left'))
        l.addRow(_('&Right:'), margin('right'))
        r.addRow(_('&Top:'), margin('top'))
        r.addRow(_('&Bottom:'), margin('bottom'))
        self.opt_use_profile_size.toggled.connect(self.profile_size_toggled)
