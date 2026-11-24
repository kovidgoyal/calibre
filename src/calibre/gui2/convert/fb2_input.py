# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget
from calibre.gui2.convert.fb2_input_ui import Ui_Form
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption


class PluginWidget(Widget, Ui_Form):
    TITLE = _('FB2 input')
    HELP = _('Options specific to') + ' FB2 ' + _('input')
    COMMIT_NAME = 'fb2_input'
    ICON = 'mimetypes/fb2.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['input']['fb2'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
