__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import QDoubleSpinBox, Widget
from calibre.gui2.convert.pdf_input_ui import Ui_Form


class PluginWidget(Widget, Ui_Form):

    TITLE = _('PDF input')
    HELP = _('Options specific to')+' PDF '+_('input')
    COMMIT_NAME = 'pdf_input'
    ICON = 'mimetypes/pdf.png'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['input']['pdf'])
        self.db, self.book_id = db, book_id
        from calibre.ebooks.conversion.plugins.pdf_input import ENGINES
        self.opt_pdf_engine.addItems(ENGINES)
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_pdf_engine.currentIndexChanged.connect(self.update_engine_opts)
        self.update_engine_opts()

    def set_value_handler(self, g, val):
        if val is None and isinstance(g, QDoubleSpinBox):
            g.setValue(0.0)
            return True
        if g is self.opt_pdf_engine:
            idx = g.findText(val)
            if idx > -1:
                g.setCurrentIndex(idx)

    def update_engine_opts(self):
        enabled = self.opt_pdf_engine.currentText() == 'calibre'
        self.opt_pdf_footer_skip.setEnabled(enabled)
        self.opt_pdf_header_skip.setEnabled(enabled)
        self.opt_pdf_header_regex.setEnabled(enabled)
        self.opt_pdf_footer_regex.setEnabled(enabled)
