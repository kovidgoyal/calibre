# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget, option_choices
from calibre.gui2.convert.fb2_output_ui import Ui_Form
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption

format_model = None


class PluginWidget(Widget, Ui_Form):
    TITLE = _('FB2 output')
    HELP = _('Options specific to') + ' FB2 ' + _('output')
    COMMIT_NAME = 'fb2_output'
    ICON = 'mimetypes/fb2.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['output']['fb2'])
        self.db, self.book_id = db, book_id
        for x in ('toc', 'files', 'nothing'):
            self.opt_sectionize.addItem(x)
        for x in option_choices(get_option, 'fb2_genre'):
            self.opt_fb2_genre.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)
