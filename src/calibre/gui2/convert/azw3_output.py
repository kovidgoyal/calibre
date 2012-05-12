#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.azw3_output_ui import Ui_Form
from calibre.gui2.convert import Widget

font_family_model = None

class PluginWidget(Widget, Ui_Form):

    TITLE = _('AZW3 Output')
    HELP = _('Options specific to')+' AZW3 '+_('output')
    COMMIT_NAME = 'azw3_output'
    ICON = I('mimetypes/mobi.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['prefer_author_sort', 'toc_title',
                    'mobi_toc_at_start',
                'dont_compress', 'no_inline_toc', 'share_not_sync',
                ]
                )
        self.db, self.book_id = db, book_id

        self.initialize_options(get_option, get_help, db, book_id)


