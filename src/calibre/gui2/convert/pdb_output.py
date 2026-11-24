# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget, option_choices
from calibre.gui2.convert.pdb_output_ui import Ui_Form
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption

format_model = None


class PluginWidget(Widget, Ui_Form):
    TITLE = _('PDB output')
    HELP = _('Options specific to') + ' PDB ' + _('output')
    COMMIT_NAME = 'pdb_output'
    ICON = 'mimetypes/unknown.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['output']['pdb'])
        self.db, self.book_id = db, book_id

        for x in option_choices(get_option, 'format'):
            self.opt_format.addItem(x)

        self.initialize_options(get_option, get_help, db, book_id)
