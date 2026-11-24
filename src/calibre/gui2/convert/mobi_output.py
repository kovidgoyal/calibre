#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget
from calibre.gui2.convert.mobi_output_ui import Ui_Form
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption

font_family_model = None


class PluginWidget(Widget, Ui_Form):
    TITLE = _('MOBI output')
    HELP = _('Options specific to') + ' MOBI ' + _('output')
    COMMIT_NAME = 'mobi_output'
    ICON = 'mimetypes/mobi.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['output']['mobi'])
        self.db, self.book_id = db, book_id

        self.opt_mobi_file_type.addItems(['old', 'both', 'new'])

        self.initialize_options(get_option, get_help, db, book_id)
