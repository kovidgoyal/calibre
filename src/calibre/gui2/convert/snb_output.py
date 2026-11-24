# License: GPLv3 Copyright: 2010, Li Fanxi <lifanxi@freemindworld.com>

from typing import TYPE_CHECKING

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget
from calibre.gui2.convert.snb_output_ui import Ui_Form
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption

newline_model = None


class PluginWidget(Widget, Ui_Form):
    TITLE = _('SNB output')
    HELP = _('Options specific to') + ' SNB ' + _('output')
    COMMIT_NAME = 'snb_output'
    ICON = 'mimetypes/snb.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['output']['snb'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
