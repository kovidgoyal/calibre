#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys
from functools import partial

from PyQt4.Qt import (QSplitter, QApplication)

from calibre.gui2.tweak_book.editor.text import PlainTextEdit
from calibre.utils.diff import get_sequence_matcher

class TextBrowser(PlainTextEdit):

    def __init__(self, parent=None):
        PlainTextEdit.__init__(self, parent)
        self.setReadOnly(True)
        self.setLineWrapMode(self.NoWrap)

class DiffView(QSplitter):

    def __init__(self, parent=None):
        QSplitter.__init__(self, parent)

        self.left, self.right = TextBrowser(self), TextBrowser(self)
        self.addWidget(self.left), self.addWidget(self.right)

    def __call__(self, left_text, right_text, context=None, syntax=None):
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()
        self.context = context

        self.left_insert = partial(self.do_insert, self.left.textCursor(), left_lines)
        self.right_insert = partial(self.do_insert, self.right.textCursor(), right_lines)
        self.cruncher = get_sequence_matcher()(None, left_lines, right_lines)
        self.do_layout(context)

    def refresh(self):
        self.do_layout(self.context)

    def do_layout(self, context=None):
        self.left.clear(), self.right.clear()
        opcodes = self.cruncher.get_opcodes() if context is None else self.cruncher.get_grouped_opcodes(context)
        for tag, alo, ahi, blo, bhi in opcodes:
            getattr(self, tag)(alo, ahi, blo, bhi)
        for v in (self.left, self.right):
            c = v.textCursor()
            c.movePosition(c.Start)
            v.setTextCursor(c)

    def do_insert(self, cursor, lines, lo, hi):
        start_block = cursor.blockNumber()
        if lo != hi:
            cursor.insertText('\n'.join(lines[lo:hi]))
            cursor.insertBlock()
        return start_block, cursor.blockNumber()

    def equal(self, alo, ahi, blo, bhi):
        self.left_insert(alo, ahi), self.right_insert(blo, bhi)

    def delete(self, alo, ahi, blo, bhi):
        self.left_insert(alo, ahi)

    def insert(self, alo, ahi, blo, bhi):
        self.right_insert(blo, bhi)

    def replace(self, alo, ahi, blo, bhi):
        self.left_insert(alo, ahi)
        self.right_insert(blo, bhi)

if __name__ == '__main__':
    app = QApplication([])
    raw1 = open(sys.argv[-2], 'rb').read().decode('utf-8')
    raw2 = open(sys.argv[-1], 'rb').read().decode('utf-8')
    w = DiffView()
    w(raw1, raw2)
    w.show()
    app.exec_()

