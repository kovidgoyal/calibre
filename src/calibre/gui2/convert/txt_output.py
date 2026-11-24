# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget, option_choices
from calibre.gui2.convert.txt_output_ui import Ui_Form
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption


class PluginWidget(Widget, Ui_Form):
    TITLE = _('TXT output')
    HELP = _('Options specific to') + ' TXT ' + _('output')
    COMMIT_NAME = 'txt_output'
    ICON = 'mimetypes/txt.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['output']['txt'])
        self.db, self.book_id = db, book_id
        for x in option_choices(get_option, 'newline'):
            self.opt_newline.addItem(x)
        for x in option_choices(get_option, 'txt_output_formatting'):
            self.opt_txt_output_formatting.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)
        if self.COMMIT_NAME != 'txt_output':
            self.image_note_label.setText(
                _(
                    'Note that for images to be preserved, the formatting option above must be markdown or textile'
                    ' and also enable the setting to not remove image references.'
                )
            )

    def break_cycles(self) -> None:
        Widget.break_cycles(self)
