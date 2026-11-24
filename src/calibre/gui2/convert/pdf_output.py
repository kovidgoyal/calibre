# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from qt.core import QCheckBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QVBoxLayout

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget, option_choices
from calibre.gui2.convert.pdf_output_ui import Ui_Form
from calibre.utils.localization import _, localize_user_manual_link

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption

paper_size_model = None
orientation_model = None


class PluginWidget(Widget, Ui_Form):
    TITLE = _('PDF output')
    HELP = _('Options specific to') + ' PDF ' + _('output')
    COMMIT_NAME = 'pdf_output'
    ICON = 'mimetypes/pdf.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['output']['pdf'])
        self.db, self.book_id = db, book_id
        try:
            self.hf_label.setText(self.hf_label.text() % localize_user_manual_link('https://manual.calibre-ebook.com/conversion.html#converting-to-pdf'))
        except TypeError:
            pass  # link already localized

        self.opt_paper_size.initialize(option_choices(get_option, 'paper_size'))
        for x in option_choices(get_option, 'unit'):
            self.opt_unit.addItem(x)
        for x in option_choices(get_option, 'pdf_standard_font'):
            self.opt_pdf_standard_font.addItem(x)

        self.initialize_options(get_option, get_help, db, book_id)
        lay = self.layout()
        assert isinstance(lay, QFormLayout)
        lay.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        tbl = self.template_box.layout()
        assert isinstance(tbl, QFormLayout)
        tbl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.profile_size_toggled()

    def profile_size_toggled(self) -> None:
        enabled = not self.opt_use_profile_size.isChecked()
        self.opt_paper_size.setEnabled(enabled)
        self.opt_custom_size.setEnabled(enabled)
        self.opt_unit.setEnabled(enabled)

    def setupUi(self, Form: QWidget) -> None:
        Ui_Form.setupUi(self, Form)
        v = QVBoxLayout(self.page_margins_box)
        self.opt_pdf_use_document_margins = c = QCheckBox(_('Use page margins from the &document being converted'))
        v.addWidget(c)
        h = QHBoxLayout()
        l = QFormLayout()
        r = QFormLayout()
        h.addLayout(l), h.addLayout(r)
        v.addLayout(h)

        def margin(which: str) -> QDoubleSpinBox:
            w = QDoubleSpinBox(self)
            w.setRange(-100, 500), w.setSuffix(' pt'), w.setDecimals(1)
            setattr(self, 'opt_pdf_page_margin_' + which, w)
            return w

        l.addRow(_('&Left:'), margin('left'))
        l.addRow(_('&Right:'), margin('right'))
        r.addRow(_('&Top:'), margin('top'))
        r.addRow(_('&Bottom:'), margin('bottom'))
        self.opt_use_profile_size.toggled.connect(self.profile_size_toggled)
