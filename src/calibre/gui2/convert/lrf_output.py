#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.lrf_output_ui import Ui_Form
from calibre.gui2.convert import Widget

font_family_model = None


class PluginWidget(Widget, Ui_Form):

    TITLE = _('LRF output')
    HELP = _('Options specific to')+' LRF '+_('output')
    COMMIT_NAME = 'lrf_output'
    ICON = I('mimetypes/lrf.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['wordspace', 'header', 'header_format',
                'minimum_indent', 'serif_family',
                'render_tables_as_images', 'sans_family', 'mono_family',
                'text_size_multiplier_for_rendered_tables', 'autorotation',
                'header_separation', 'minimum_indent']
                )
        self.db, self.book_id = db, book_id

        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_header.toggle(), self.opt_header.toggle()
        self.opt_render_tables_as_images.toggle()
        self.opt_render_tables_as_images.toggle()
