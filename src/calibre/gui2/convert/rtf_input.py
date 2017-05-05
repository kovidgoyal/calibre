#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.gui2.convert.rtf_input_ui import Ui_Form
from calibre.gui2.convert import Widget


class PluginWidget(Widget, Ui_Form):

    TITLE = _('RTF input')
    HELP = _('Options specific to')+' RTF '+_('input')
    COMMIT_NAME = 'rtf_input'
    ICON = I('mimetypes/rtf.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
            ['ignore_wmf', ])
        self.initialize_options(get_option, get_help, db, book_id)
