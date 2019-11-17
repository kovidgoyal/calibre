#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from PyQt5.Qt import Qt

from calibre.gui2.tweak_book.editor.smarts import NullSmarts
from calibre.gui2.tweak_book.editor.smarts.utils import (
    get_text_before_cursor, get_leading_whitespace_on_block as lw,
    smart_home, smart_backspace, smart_tab)

get_leading_whitespace_on_block = lambda editor, previous=False: expand_tabs(lw(editor, previous=previous))

tw = 4  # The tab width (hardcoded to the pep8 value)


def expand_tabs(text):
    return text.replace('\t', ' ' * tw)


class Smarts(NullSmarts):

    override_tab_stop_width = tw

    def __init__(self, *args, **kwargs):
        NullSmarts.__init__(self, *args, **kwargs)
        c = re.compile
        self.escape_scope_pat = c(r'\s+(continue|break|return|pass)(\s|$)')
        self.dedent_pat = c(r'\s+(else|elif|except)(\(|\s|$)')

    def handle_key_press(self, ev, editor):
        key = ev.key()

        if key == Qt.Key_Tab and smart_tab(editor, ev):
            return True

        elif key == Qt.Key_Backspace and smart_backspace(editor, ev):
            return True

        elif key in (Qt.Key_Enter, Qt.Key_Return):
            ls = get_leading_whitespace_on_block(editor)
            cursor = editor.textCursor()
            line = cursor.block().text()
            if line.rstrip().endswith(':'):
                ls += ' ' * tw
            elif self.escape_scope_pat.match(line) is not None:
                ls = ls[:-tw]
            cursor.insertText('\n' + ls)
            editor.setTextCursor(cursor)
            return True

        elif key == Qt.Key_Colon:
            cursor, text = get_text_before_cursor(editor)
            if self.dedent_pat.search(text) is not None:
                ls = get_leading_whitespace_on_block(editor)
                pls = get_leading_whitespace_on_block(editor, previous=True)
                if ls and ls >= pls:
                    ls = ls[:-tw]
                    text = ls + text.lstrip() + ':'
                    cursor.insertText(text)
                    editor.setTextCursor(cursor)
                    return True

        if key == Qt.Key_Home and smart_home(editor, ev):
            return True


if __name__ == '__main__':
    import os
    from calibre.gui2.tweak_book.editor.widget import launch_editor
    launch_editor(os.path.abspath(__file__), syntax='python')
