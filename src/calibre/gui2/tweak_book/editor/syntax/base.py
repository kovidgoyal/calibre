#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import (QSyntaxHighlighter, QApplication, QCursor, Qt)

from ..themes import highlight_to_char_format

class SyntaxHighlighter(QSyntaxHighlighter):

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
            self.do_highlight(state, unicode(text))
        except:
            import traceback
            traceback.print_exc()

    def do_highlight(self, state, text):
        state = self.state_class(state)

        i = 0
        while i < len(text):
            fmt = self.state_map[state.parse](state, text, i, self.formats)
            for num, f in fmt:
                if f is not None:
                    self.setFormat(i, num, f)
                i += num

        self.setCurrentBlockState(state.value)


