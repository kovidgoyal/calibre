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

def run_loop(state, state_map, formats, text):
    i = 0
    while i < len(text):
        fmt = state_map[state.parse](state, text, i, formats)
        for num, f in fmt:
            yield i, num, f
            i += num

class SyntaxHighlighter(QSyntaxHighlighter):

    state_map = {0:lambda state, text, i, formats:[(len(text), None)]}
    create_formats_func = lambda highlighter: {}

    def __init__(self, *args, **kwargs):
        QSyntaxHighlighter.__init__(self, *args, **kwargs)

    def create_state(self, num):
        return SimpleState(max(0, num))

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
        self.formats = self.create_formats_func()

    def highlightBlock(self, text):
        try:
            state = self.previousBlockState()
            self.setCurrentBlockUserData(None)  # Ensure that any stale user data is discarded
            state = self.create_state(state)
            state.get_user_data, state.set_user_data = self.currentBlockUserData, self.setCurrentBlockUserData
            for i, num, fmt in run_loop(state, self.state_map, self.formats, unicode(text)):
                if fmt is not None:
                    self.setFormat(i, num, fmt)
            self.setCurrentBlockState(state.value)
        except:
            import traceback
            traceback.print_exc()
        finally:
            # Disabled as it causes crashes
            pass  # QApplication.processEvents()  # Try to keep the editor responsive to user input

