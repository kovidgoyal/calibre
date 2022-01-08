#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.toc_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2 import error_dialog
from calibre.utils.localization import localize_user_manual_link
from calibre.ebooks.conversion.config import OPTIONS


class TOCWidget(Widget, Ui_Form):

    TITLE = _('Table of\nContents')
    ICON  = 'toc.png'
    HELP  = _('Control the creation/conversion of the Table of Contents.')
    COMMIT_NAME = 'toc'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['pipe']['toc'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_level1_toc.set_msg(_('Level &1 TOC (XPath expression):'))
        self.opt_level2_toc.set_msg(_('Level &2 TOC (XPath expression):'))
        self.opt_level3_toc.set_msg(_('Level &3 TOC (XPath expression):'))
        try:
            self.help_label.setText(self.help_label.text() % localize_user_manual_link(
                'https://manual.calibre-ebook.com/conversion.html#table-of-contents'))
        except TypeError:
            pass  # link already localized

    def pre_commit_check(self):
        for x in ('level1', 'level2', 'level3'):
            x = getattr(self, 'opt_'+x+'_toc')
            if not x.check():
                error_dialog(self, _('Invalid XPath'),
                _('The XPath expression %s is invalid.')%x.text).exec()
                return False
        return True
