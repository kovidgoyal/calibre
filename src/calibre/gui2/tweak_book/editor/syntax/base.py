#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import (QSyntaxHighlighter, QApplication, QCursor, Qt)

from ..themes import highlight_to_char_format

class SimpleState(object):

    def __init__(self, value):
        self.parse = value

    @property
    def value(self):
        return self.parse

def run_loop(state, state_map, set_format, formats, text):
    i = 0
    while i < len(text):
        fmt = state_map[state.parse](state, text, i, formats)
        for num, f in fmt:
            if f is not None:
                set_format(i, num, f)
            i += num

class SyntaxHighlighter(QSyntaxHighlighter):

    state_class = SimpleState
    state_map = {0:lambda state, text, i, formats:[(len(text), None)]}
    formats = {}

    def rehighlight(self):
        self.outlineexplorer_data = {}
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QSyntaxHighlighter.rehighlight(self)
        QApplication.restoreOverrideCursor()

    def apply_theme(self, theme):
        self.theme = {k:highlight_to_char_format(v) for k, v in theme.iteritems()}
        self.create_formats()
        self.rehighlight()

    def create_formats(self):
        pass

    def highlightBlock(self, text):
        try:
            state = self.previousBlockState()
            if state == -1:
                state = 0
            state = self.state_class(state)
            run_loop(state, self.state_map, self.setFormat, self.formats, unicode(text))
            self.setCurrentBlockState(state.value)
        except:
            import traceback
            traceback.print_exc()

