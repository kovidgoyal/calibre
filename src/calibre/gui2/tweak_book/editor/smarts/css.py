#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import Qt

from calibre.gui2.tweak_book.editor.smarts import NullSmarts
from calibre.gui2.tweak_book.editor.smarts.utils import (
    no_modifiers, get_leading_whitespace_on_block, get_text_before_cursor,
    smart_home, smart_backspace, smart_tab, expand_tabs)

def find_rule(raw, rule_address):
    import tinycss
    parser = tinycss.make_full_parser()
    sheet = parser.parse_stylesheet(raw)
    rules = sheet.rules
    ans = None, None
    while rule_address:
        try:
            r = rules[rule_address[0]]
        except IndexError:
            return None, None
        else:
            ans = r.line, r.column
        rule_address = rule_address[1:]
        if rule_address:
            rules = getattr(r, 'rules', ())
    return ans

class Smarts(NullSmarts):

    def handle_key_press(self, ev, editor):
        key = ev.key()

        if key in (Qt.Key_Enter, Qt.Key_Return) and no_modifiers(ev, Qt.ControlModifier, Qt.AltModifier):
            ls = get_leading_whitespace_on_block(editor)
            cursor, text = get_text_before_cursor(editor)
            if text.rstrip().endswith('{'):
                ls += ' ' * editor.tw
            editor.textCursor().insertText('\n' + ls)
            return True

        if key == Qt.Key_BraceRight:
            ls = get_leading_whitespace_on_block(editor)
            pls = get_leading_whitespace_on_block(editor, previous=True)
            cursor, text = get_text_before_cursor(editor)
            if not text.rstrip() and ls >= pls and len(text) > 1:
                text = expand_tabs(text, editor.tw)[:-editor.tw]
                cursor.insertText(text + '}')
                editor.setTextCursor(cursor)
                return True

        if key == Qt.Key_Home and smart_home(editor, ev):
            return True

        if key == Qt.Key_Tab and smart_tab(editor, ev):
            return True

        if key == Qt.Key_Backspace and smart_backspace(editor, ev):
            return True

        return False


