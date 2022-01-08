#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.gui2.convert.debug_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2 import error_dialog, choose_dir
from calibre.ebooks.conversion.config import OPTIONS


class DebugWidget(Widget, Ui_Form):

    TITLE = _('Debug')
    ICON  = 'debug.png'
    HELP  = _('Debug the conversion process.')
    COMMIT_NAME = 'debug'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['pipe']['debug'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
        self.button_debug_dir.clicked.connect(self.set_debug_dir)

    def set_debug_dir(self):
        x = choose_dir(self, 'conversion debug dir', _('Choose debug folder'))
        if x:
            self.opt_debug_pipeline.setText(x)

    def pre_commit_check(self):
        try:
            x = str(self.opt_debug_pipeline.text()).strip()
            if not x:
                return True
            x = os.path.abspath(x)
            if x:
                if not os.path.exists(x):
                    os.makedirs(x)
                test = os.path.join(x, 'test')
                open(test, 'wb').close()
                os.remove(test)
        except:
            import traceback
            det_msg = traceback.format_exc()
            error_dialog(self, _('Invalid debug folder'),
                    _('Failed to create debug folder')+': '+ str(self.opt_debug_pipeline.text()),
                        det_msg=det_msg, show=True)
            return False
        return True
