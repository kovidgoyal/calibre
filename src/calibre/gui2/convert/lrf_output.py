#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget
from calibre.gui2.convert.lrf_output_ui import Ui_Form
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption

font_family_model = None


class PluginWidget(Widget, Ui_Form):
    TITLE = _('LRF output')
    HELP = _('Options specific to') + ' LRF ' + _('output')
    COMMIT_NAME = 'lrf_output'
    ICON = 'mimetypes/lrf.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['output']['lrf'])
        self.db, self.book_id = db, book_id

        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_header.toggle(), self.opt_header.toggle()
        self.opt_render_tables_as_images.toggle()
        self.opt_render_tables_as_images.toggle()
