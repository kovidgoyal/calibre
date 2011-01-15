# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import Qt

from calibre.gui2.convert.heuristics_ui import Ui_Form
from calibre.gui2.convert import Widget

class HeuristicsWidget(Widget, Ui_Form):

    TITLE = _('Heuristics')
    HELP  = _('Modify the document text and structure using common patterns.')
    COMMIT_NAME = 'heuristics'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['enable_heuristics', 'markup_chapter_headings',
                 'italicize_common_cases', 'fix_indents',
                 'html_unwrap_factor', 'unwrap_lines',
                 'delete_blank_paragraphs', 'format_scene_breaks',
                 'dehyphenate']
                )
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
        
        self.opt_enable_heuristics.stateChanged.connect(self.enable_heuristics)
        self.opt_unwrap_lines.stateChanged.connect(self.enable_unwrap)
        
        self.enable_heuristics(self.opt_enable_heuristics.checkState())

    def break_cycles(self):
        Widget.break_cycles(self)
        
        self.opt_enable_heuristics.stateChanged.disconnect()
        self.opt_unwrap_lines.stateChanged.disconnect()
        
    def set_value_handler(self, g, val):
        if val is None and g is self.opt_html_unwrap_factor:
            g.setValue(0.0)
            return True

    def enable_heuristics(self, state):
        if state == Qt.Checked:
            state = True
        else:
            state = False
        self.opt_markup_chapter_headings.setEnabled(state)
        self.opt_italicize_common_cases.setEnabled(state)
        self.opt_fix_indents.setEnabled(state)
        self.opt_delete_blank_paragraphs.setEnabled(state)
        self.opt_format_scene_breaks.setEnabled(state)
        self.opt_dehyphenate.setEnabled(state)
        
        self.opt_unwrap_lines.setEnabled(state)
        if state and self.opt_unwrap_lines.checkState() == Qt.Checked:
            self.opt_html_unwrap_factor.setEnabled(True)
        else:
            self.opt_html_unwrap_factor.setEnabled(False)

    def enable_unwrap(self, state):
        if state == Qt.Checked:
            state = True
        else:
            state = False
        self.opt_html_unwrap_factor.setEnabled(state)
