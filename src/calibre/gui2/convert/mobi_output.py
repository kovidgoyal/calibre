#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.mobi_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.config import OPTIONS

font_family_model = None


class PluginWidget(Widget, Ui_Form):

    TITLE = _('MOBI output')
    HELP = _('Options specific to')+' MOBI '+_('output')
    COMMIT_NAME = 'mobi_output'
    ICON = I('mimetypes/mobi.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['output']['mobi'])
        self.db, self.book_id = db, book_id

        self.opt_mobi_file_type.addItems(['old', 'both', 'new'])

        self.initialize_options(get_option, get_help, db, book_id)
