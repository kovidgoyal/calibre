# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from calibre.gui2.convert.heuristics_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2 import error_dialog

class HeuristicsWidget(Widget, Ui_Form):

    TITLE = _('Heuristics')
    HELP  = _('')
    COMMIT_NAME = 'heuristics'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['enable_heuristics', 'markup_chapter_headings',
                 'italicize_common_cases', 'fix_indents',
                 'html_unwrap_factor', 'unwrap_lines',
                 'delete_blank_paragraphs', 'format_scene_breaks',
                 'dehyphenate',
                 'sr1_search', 'sr1_replace',
                 'sr2_search', 'sr2_replace',
                 'sr3_search', 'sr3_replace']
                )
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_sr1_search.set_msg(_('Search regular expression 1:'))
        self.opt_sr1_replace.set_msg(_('Replace regular expression 1:'))
        self.opt_sr2_search.set_msg(_('Search regular expression 2:'))
        self.opt_sr2_replace.set_msg(_('Replace regular expression 2:'))
        self.opt_sr3_search.set_msg(_('Search regular expression 3:'))
        self.opt_sr3_replace.set_msg(_('Replace regular expression 3:'))

    def break_cycles(self):
        Widget.break_cycles(self)
        self.opt_sr1_search.break_cycles()
        self.opt_sr1_replace.break_cycles()
        self.opt_sr2_search.break_cycles()
        self.opt_sr2_replace.break_cycles()
        self.opt_sr3_search.break_cycles()
        self.opt_sr3_replace.break_cycles()

    def pre_commit_check(self):
        for x in ('sr1-search', 'sr1-replace', 'sr2-search', 'sr2-replace', 'sr3-search', 'sr3-replace',):
            x = getattr(self, 'opt_'+x)
            try:
                pat = unicode(x.regex)
                re.compile(pat)
            except Exception, err:
                error_dialog(self, _('Invalid regular expression'),
                             _('Invalid regular expression: %s')%err).exec_()
                return False
            
    def set_value_handler(self, g, val):
        if val is None and g is self.opt_html_unwrap_factor:
            g.setValue(0.0)
            return True
