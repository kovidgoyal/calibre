#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from PyQt5.Qt import Qt

from calibre.gui2.tweak_book.editor.smarts import NullSmarts

def get_text_before_cursor(editor):
    cursor = editor.textCursor()
    cursor.clearSelection()
    cursor.movePosition(cursor.StartOfLine, cursor.KeepAnchor)
    text = cursor.selectedText()
    return cursor, text

def expand_tabs(text):
    return text.replace('\t', ' '*4)

def get_leading_whitespace_on_line(editor, previous=False):
    cursor = editor.textCursor()
    block = cursor.block()
    if previous:
        block = block.previous()
    if block.isValid():
        text = block.text()
        ntext = text.lstrip()
        return expand_tabs(text[:len(text)-len(ntext)])
    return ''

class Smarts(NullSmarts):

    override_tab_stop_width = 4

    def __init__(self, *args, **kwargs):
        NullSmarts.__init__(self, *args, **kwargs)
        c = re.compile
        self.escape_scope_pat = c(r'\s+(continue|break|return|pass)(\s|$)')
        self.dedent_pat = c(r'\s+(else|elif|except)(\(|\s|$)')

    def handle_key_press(self, ev, editor):
        key = ev.key()

        if key == Qt.Key_Tab:
            cursor, text = get_text_before_cursor(editor)
            if not text.lstrip():
                # cursor is preceded by whitespace
                text = expand_tabs(text)
                spclen = len(text) - (len(text) % 4) + 4
                cursor.insertText(' ' * spclen)
                editor.setTextCursor(cursor)
            else:
                cursor = editor.textCursor()
                cursor.insertText(' ' * 4)
                editor.setTextCursor(cursor)
            return True

        elif key == Qt.Key_Backspace:
            cursor, text = get_text_before_cursor(editor)
            if text and not text.lstrip():
                # cursor is preceded by whitespace
                text = expand_tabs(text)
                spclen = max(0, len(text) - (len(text) % 4) - 4)
                cursor.insertText(' ' * spclen)
                editor.setTextCursor(cursor)
                return True

        elif key in (Qt.Key_Enter, Qt.Key_Return):
            ls = get_leading_whitespace_on_line(editor)
            cursor = editor.textCursor()
            line = cursor.block().text()
            if line.rstrip().endswith(':'):
                ls += ' ' * 4
            elif self.escape_scope_pat.match(line) is not None:
                ls = ls[:-4]
            cursor.insertText('\n' + ls)
            editor.setTextCursor(cursor)
            return True

        elif key == Qt.Key_Colon:
            cursor, text = get_text_before_cursor(editor)
            if self.dedent_pat.search(text) is not None:
                ls = get_leading_whitespace_on_line(editor)
                pls = get_leading_whitespace_on_line(editor, previous=True)
                if ls and ls >= pls:
                    ls = ls[:-4]
                    text = ls + text.lstrip() + ':'
                    cursor.insertText(text)
                    editor.setTextCursor(cursor)
                    return True

if __name__ == '__main__':
    import os
    from calibre.gui2.tweak_book.editor.widget import launch_editor
    launch_editor(os.path.abspath(__file__), syntax='python')
