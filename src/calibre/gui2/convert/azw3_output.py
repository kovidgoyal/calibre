#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.azw3_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.config import OPTIONS

font_family_model = None


class PluginWidget(Widget, Ui_Form):

    TITLE = _('AZW3 output')
    HELP = _('Options specific to')+' AZW3 '+_('output')
    COMMIT_NAME = 'azw3_output'
    ICON = I('mimetypes/azw3.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['output']['azw3'])
        self.db, self.book_id = db, book_id

        self.initialize_options(get_option, get_help, db, book_id)
