#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.epub_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.config import OPTIONS


class PluginWidget(Widget, Ui_Form):

    TITLE = _('EPUB output')
    HELP  = _('Options specific to')+' EPUB '+_('output')
    COMMIT_NAME = 'epub_output'
    ICON = 'mimetypes/epub.png'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['output']['epub'])
        for i in range(2):
            self.opt_no_svg_cover.toggle()
        ev = get_option('epub_version')
        self.opt_epub_version.addItems(list(ev.option.choices))
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
