#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget, option_choices
from calibre.gui2.convert.comic_input_ui import Ui_Form
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption


class PluginWidget(Widget, Ui_Form):
    TITLE = _('Comic input')
    HELP = _('Options specific to') + ' comic ' + _('input')
    COMMIT_NAME = 'comic_input'
    ICON = 'mimetypes/png.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['input']['comic'])
        self.db, self.book_id = db, book_id
        for x in option_choices(get_option, 'output_format'):
            self.opt_output_format.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_no_process.toggle()
        self.opt_no_process.toggle()
