#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.comic_input_ui import Ui_Form
from calibre.gui2.convert import Widget


class PluginWidget(Widget, Ui_Form):

    TITLE = _('Comic input')
    HELP = _('Options specific to')+' comic '+_('input')
    COMMIT_NAME = 'comic_input'
    ICON = I('mimetypes/png.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['colors', 'dont_normalize', 'keep_aspect_ratio', 'right2left',
                    'despeckle', 'no_sort', 'no_process', 'landscape',
                    'dont_sharpen', 'disable_trim', 'wide', 'output_format',
                    'dont_grayscale', 'comic_image_size',
                    'dont_add_comic_pages_to_toc']
                )
        self.db, self.book_id = db, book_id
        for x in get_option('output_format').option.choices:
            self.opt_output_format.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_no_process.toggle()
        self.opt_no_process.toggle()
