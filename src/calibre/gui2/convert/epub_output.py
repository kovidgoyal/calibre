#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.epub_output_ui import Ui_Form
from calibre.gui2.convert import Widget

class PluginWidget(Widget, Ui_Form):

    TITLE = _('EPUB Output')
    HELP  = _('Options specific to')+' EPUB '+_('output')
    COMMIT_NAME = 'epub_output'
    ICON = I('mimetypes/epub.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['dont_split_on_page_breaks', 'flow_size',
                    'no_default_epub_cover', 'no_svg_cover',
                 'epub_inline_toc', 'epub_toc_at_end', 'toc_title',
                    'preserve_cover_aspect_ratio', 'epub_flatten']
                )
        for i in range(2):
            self.opt_no_svg_cover.toggle()
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)

