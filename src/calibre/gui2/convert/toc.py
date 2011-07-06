#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.toc_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2 import error_dialog

class TOCWidget(Widget, Ui_Form):

    TITLE = _('Table of\nContents')
    ICON  = I('series.png')
    HELP  = _('Control the creation/conversion of the Table of Contents.')
    COMMIT_NAME = 'toc'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['level1_toc', 'level2_toc', 'level3_toc',
                'toc_threshold', 'max_toc_links', 'no_chapters_in_toc',
                'use_auto_toc', 'toc_filter', 'duplicate_links_in_toc',
                ]
                )
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_level1_toc.set_msg(_('Level &1 TOC (XPath expression):'))
        self.opt_level2_toc.set_msg(_('Level &2 TOC (XPath expression):'))
        self.opt_level3_toc.set_msg(_('Level &3 TOC (XPath expression):'))


    def pre_commit_check(self):
        for x in ('level1', 'level2', 'level3'):
            x = getattr(self, 'opt_'+x+'_toc')
            if not x.check():
                error_dialog(self, _('Invalid XPath'),
                _('The XPath expression %s is invalid.')%x.text).exec_()
                return False
        return True
