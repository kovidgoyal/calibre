#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import Qt

from calibre.gui2.convert.lrf_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2.widgets import FontFamilyModel

font_family_model = None

class PluginWidget(Widget, Ui_Form):

    TITLE = _('LRF Output')
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
        global font_family_model
        if font_family_model is None:
            font_family_model = FontFamilyModel()
        self.font_family_model = font_family_model
        self.opt_serif_family.setModel(self.font_family_model)
        self.opt_sans_family.setModel(self.font_family_model)
        self.opt_mono_family.setModel(self.font_family_model)

        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_header.toggle(), self.opt_header.toggle()
        self.opt_render_tables_as_images.toggle()
        self.opt_render_tables_as_images.toggle()


    def set_value_handler(self, g, val):
        if unicode(g.objectName()) in ('opt_serif_family',
                'opt_sans_family', 'opt_mono_family'):
            idx = -1
            if val:
                idx = g.findText(val, Qt.MatchFixedString)
            if idx < 0:
                idx = 0
            g.setCurrentIndex(idx)
            return True
        return False
