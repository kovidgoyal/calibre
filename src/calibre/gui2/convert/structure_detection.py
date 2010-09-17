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
    ICON  = I('chapters.png')
    HELP  = _('Fine tune the detection of chapter headings and '
            'other document structure.')
    COMMIT_NAME = 'structure_detection'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['chapter', 'chapter_mark',
                'remove_first_image',
                'insert_metadata', 'page_breaks_before',
                'preprocess_html', 'remove_header', 'header_regex',
                'remove_footer', 'footer_regex','html_unwrap_factor']
                )
        self.opt_html_unwrap_factor.setEnabled(False)
        self.huf_label.setEnabled(False)
        self.db, self.book_id = db, book_id
        for x in ('pagebreak', 'rule', 'both', 'none'):
            self.opt_chapter_mark.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_chapter.set_msg(_('Detect chapters at (XPath expression):'))
        self.opt_page_breaks_before.set_msg(_('Insert page breaks before '
            '(XPath expression):'))
        self.opt_header_regex.set_msg(_('Header regular expression:'))
        self.opt_header_regex.set_book_id(book_id)
        self.opt_header_regex.set_db(db)
        self.opt_footer_regex.set_msg(_('Footer regular expression:'))
        self.opt_footer_regex.set_book_id(book_id)
        self.opt_footer_regex.set_db(db)

    def break_cycles(self):
        Widget.break_cycles(self)
        self.opt_header_regex.break_cycles()
        self.opt_footer_regex.break_cycles()

    def pre_commit_check(self):
        for x in ('header_regex', 'footer_regex'):
            x = getattr(self, 'opt_'+x)
            try:
                pat = unicode(x.regex)
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

    def set_value_handler(self, g, val):
        if val is None and g is self.opt_html_unwrap_factor:
            g.setValue(0.0)
            return True
