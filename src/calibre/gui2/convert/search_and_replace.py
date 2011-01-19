# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from calibre.gui2.convert.search_and_replace_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2 import error_dialog

class SearchAndReplaceWidget(Widget, Ui_Form):

    TITLE = _(u'Search\u00a0&\nReplace')
    HELP  = _('Modify the document text and structure using user defined patterns.')
    COMMIT_NAME = 'search_and_replace'
    ICON = I('search.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['sr1_search', 'sr1_replace',
                 'sr2_search', 'sr2_replace',
                 'sr3_search', 'sr3_replace']
                )
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_sr1_search.set_msg(_('&Search Regular Expression'))
        self.opt_sr1_search.set_book_id(book_id)
        self.opt_sr1_search.set_db(db)
        self.opt_sr2_search.set_msg(_('&Search Regular Expression'))
        self.opt_sr2_search.set_book_id(book_id)
        self.opt_sr2_search.set_db(db)
        self.opt_sr3_search.set_msg(_('&Search Regular Expression'))
        self.opt_sr3_search.set_book_id(book_id)
        self.opt_sr3_search.set_db(db)

    def break_cycles(self):
        Widget.break_cycles(self)

        self.opt_sr1_search.break_cycles()
        self.opt_sr2_search.break_cycles()
        self.opt_sr3_search.break_cycles()

    def pre_commit_check(self):
        for x in ('sr1_search', 'sr2_search', 'sr3_search'):
            x = getattr(self, 'opt_'+x)
            try:
                pat = unicode(x.regex)
                re.compile(pat)
            except Exception, err:
                error_dialog(self, _('Invalid regular expression'),
                             _('Invalid regular expression: %s')%err, show=True)
                return False
        return True
