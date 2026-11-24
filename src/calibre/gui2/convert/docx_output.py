# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from qt.core import QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLineEdit, QSizePolicy, QWidget

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget, option_choices
from calibre.utils.localization import _

if TYPE_CHECKING:
    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption, OptionWidget

paper_size_model = None
orientation_model = None


class PluginWidget(Widget):
    TITLE = _('DOCX output')
    HELP = _('Options specific to') + ' DOCX ' + _('output')
    COMMIT_NAME = 'docx_output'
    ICON = 'mimetypes/docx.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['output']['docx'])
        for x in option_choices(get_option, 'docx_page_size'):
            self.opt_docx_page_size.addItem(x)
        for x, text in (('footnotes', _('Footnotes')), ('endnotes', _('Endnotes')), ('links', _('Hyperlinks to the notes text'))):
            self.opt_docx_notes.addItem(text, x)

        self.initialize_options(get_option, get_help, db, book_id)
        lay = self.layout()
        assert isinstance(lay, QFormLayout)
        lay.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

    def get_value_handler(self, g: OptionWidget) -> object:
        if g is self.opt_docx_notes:
            return str(self.opt_docx_notes.currentData() or 'footnotes')
        return Widget.get_value_handler(self, g)

    def set_value_handler(self, g: OptionWidget, val: object) -> bool:
        if g is self.opt_docx_notes:
            idx = self.opt_docx_notes.findData(val or 'footnotes')
            self.opt_docx_notes.setCurrentIndex(max(0, idx))
            return True
        return Widget.set_value_handler(self, g, val)

    def setupUi(self, *a: object) -> None:
        self.l = l = QFormLayout(self)
        self.opt_docx_page_size = QComboBox(self)
        l.addRow(_('Paper si&ze:'), self.opt_docx_page_size)
        self.opt_docx_custom_page_size = w = QLineEdit(self)
        w.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        l.addRow(_('&Custom size:'), w)
        for i, text in enumerate((
            _('Page &left margin'),
            _('Page &top margin'),
            _('Page &right margin'),
            _('Page &bottom margin'),
        )):
            m = 'left top right bottom'.split()[i]
            w = QDoubleSpinBox(self)
            w.setRange(-100, 500), w.setSuffix(' pt'), w.setDecimals(1)
            setattr(self, 'opt_docx_page_margin_' + m, w)
            l.addRow(text + ':', w)
        self.opt_docx_notes = QComboBox(self)
        l.addRow(_('Output foot/end&notes as:'), self.opt_docx_notes)
        self.opt_docx_no_toc = QCheckBox(_('Do not insert the &Table of Contents as a page at the start of the document'))
        l.addRow(self.opt_docx_no_toc)
        self.opt_docx_no_cover = QCheckBox(_('Do not insert &cover as image at start of document'))
        l.addRow(self.opt_docx_no_cover)
        self.opt_preserve_cover_aspect_ratio = QCheckBox(_('Preserve the aspect ratio of the image inserted as cover'))
        l.addRow(self.opt_preserve_cover_aspect_ratio)
