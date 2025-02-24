#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.ebooks.conversion.config import OPTIONS
from calibre.gui2.convert import Widget
from calibre.gui2.convert.kepub_output_ui import Ui_Form


class PluginWidget(Widget, Ui_Form):

    TITLE = _('KEPUB output')
    HELP  = _('Options specific to')+' KEPUB '+_('output')
    COMMIT_NAME = 'kepub_output'
    ICON = 'mimetypes/epub.png'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['output']['kepub'])
        for i in range(2):
            self.opt_kepub_affect_hyphenation.toggle()
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
