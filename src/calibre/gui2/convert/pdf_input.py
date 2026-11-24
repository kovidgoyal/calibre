# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING, cast

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import QDoubleSpinBox, Widget
from calibre.gui2.convert.pdf_input_ui import Ui_Form
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption, OptionWidget


class PluginWidget(Widget, Ui_Form):
    TITLE = _('PDF input')
    HELP = _('Options specific to') + ' PDF ' + _('input')
    COMMIT_NAME = 'pdf_input'
    ICON = 'mimetypes/pdf.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['input']['pdf'])
        self.db, self.book_id = db, book_id
        from calibre.ebooks.conversion.plugins.pdf_input import ENGINES

        self.opt_pdf_engine.addItems(ENGINES)
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_pdf_engine.currentIndexChanged.connect(self.update_engine_opts)
        self.update_engine_opts()

    def set_value_handler(self, g: OptionWidget, val: object) -> bool:
        if val is None and isinstance(g, QDoubleSpinBox):
            g.setValue(0.0)
            return True
        if g is self.opt_pdf_engine:
            idx = g.findText(cast('str', val))
            if idx > -1:
                g.setCurrentIndex(idx)
        return False

    def update_engine_opts(self) -> None:
        enabled = self.opt_pdf_engine.currentText() == 'calibre'
        self.opt_pdf_footer_skip.setEnabled(enabled)
        self.opt_pdf_header_skip.setEnabled(enabled)
        self.opt_pdf_header_regex.setEnabled(enabled)
        self.opt_pdf_footer_regex.setEnabled(enabled)
