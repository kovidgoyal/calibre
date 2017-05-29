#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.structure_detection_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2 import error_dialog


class StructureDetectionWidget(Widget, Ui_Form):

    TITLE = _('Structure\ndetection')
    ICON  = I('chapters.png')
    HELP  = _('Fine tune the detection of chapter headings and '
            'other document structure.')
    COMMIT_NAME = 'structure_detection'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['chapter', 'chapter_mark', 'start_reading_at',
                'remove_first_image', 'remove_fake_margins',
                'insert_metadata', 'page_breaks_before']
                )
        self.db, self.book_id = db, book_id
        for x in ('pagebreak', 'rule', 'both', 'none'):
            self.opt_chapter_mark.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_chapter.set_msg(_('Detect &chapters at (XPath expression):'))
        self.opt_page_breaks_before.set_msg(_('Insert &page breaks before '
            '(XPath expression):'))
        self.opt_start_reading_at.set_msg(
                _('Start &reading at (XPath expression):'))

    def break_cycles(self):
        Widget.break_cycles(self)

    def pre_commit_check(self):
        for x in ('chapter', 'page_breaks_before', 'start_reading_at'):
            x = getattr(self, 'opt_'+x)
            if not x.check():
                error_dialog(self, _('Invalid XPath'),
                _('The XPath expression %s is invalid.')%x.text).exec_()
                return False
        return True
