#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re

from calibre.gui2.convert.structure_detection_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2 import error_dialog

class StructureDetectionWidget(Widget, Ui_Form):

    TITLE = _('Structure\nDetection')
    ICON  = I('chapters.svg')
    HELP  = _('Fine tune the detection of chapter headings and '
            'other document structure.')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, 'structure_detection',
                ['chapter', 'chapter_mark',
                'remove_first_image',
                'insert_metadata', 'page_breaks_before',
                'preprocess_html', 'remove_header', 'header_regex',
                'remove_footer', 'footer_regex']
                )
        self.db, self.book_id = db, book_id
        for x in ('pagebreak', 'rule', 'both', 'none'):
            self.opt_chapter_mark.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_chapter.set_msg(_('Detect chapters at (XPath expression):'))
        self.opt_page_breaks_before.set_msg(_('Insert page breaks before '
            '(XPath expression):'))
    def pre_commit_check(self):
        for x in ('header_regex', 'footer_regex'):
            x = getattr(self, 'opt_'+x)
            try:
                pat = unicode(x.text())
                re.compile(pat)
            except Exception, err:
                error_dialog(self, _('Invalid regular expression'),
                             _('Invalid regular expression: %s')%err).exec_()
                return False
        for x in ('chapter', 'page_breaks_before'):
            x = getattr(self, 'opt_'+x)
            if not x.check():
                error_dialog(self, _('Invalid XPath'),
                _('The XPath expression %s is invalid.')%x.text).exec_()
                return False
        return True
