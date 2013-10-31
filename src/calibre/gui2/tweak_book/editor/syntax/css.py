#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter

class State(object):

    NORMAL = 0

    def __init__(self, num):
        self.parse  = num & 0b1111
        self.blocks = num >> 4

    @property
    def value(self):
        return ((self.parse & 0b1111) | (max(0, self.blocks) << 4))


def normal(state, text, i, formats):
    ' The normal state (outside everything) '
    return [(len(text), None)]

state_map = {
    State.NORMAL:normal,
}

class CSSHighlighter(SyntaxHighlighter):

    state_map = state_map
    state_class = State

    def __init__(self, parent):
        SyntaxHighlighter.__init__(self, parent)

    def create_formats(self):
        # t = self.theme
        self.formats = {
        }

if __name__ == '__main__':
    from calibre.gui2.tweak_book.editor.text import launch_editor
    launch_editor('''\
@charset "utf-8";
/* A demonstration css sheet */
''', path_is_raw=True, syntax='css')

