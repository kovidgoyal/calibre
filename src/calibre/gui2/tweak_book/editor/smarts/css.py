#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from qt.core import Qt, QTextCursor

from calibre.gui2.tweak_book import current_container
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

    def __init__(self, *args, **kwargs):
        if not hasattr(Smarts, 'regexps_compiled'):
            Smarts.regexps_compiled = True
            Smarts.complete_attr_pat = re.compile(r'''url\s*\(\s*['"]{0,1}([^)]*)$''')
        NullSmarts.__init__(self, *args, **kwargs)

    def handle_key_press(self, ev, editor):
        key = ev.key()

        if key in (Qt.Key.Key_Enter, Qt.Key.Key_Return) and no_modifiers(ev, Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.AltModifier):
            ls = get_leading_whitespace_on_block(editor)
            cursor, text = get_text_before_cursor(editor)
            if text.rstrip().endswith('{'):
                ls += ' ' * editor.tw
            editor.textCursor().insertText('\n' + ls)
            return True

        if key == Qt.Key.Key_BraceRight:
            ls = get_leading_whitespace_on_block(editor)
            pls = get_leading_whitespace_on_block(editor, previous=True)
            cursor, text = get_text_before_cursor(editor)
            if not text.rstrip() and ls >= pls and len(text) > 1:
                text = expand_tabs(text, editor.tw)[:-editor.tw]
                cursor.insertText(text + '}')
                editor.setTextCursor(cursor)
                return True

        if key == Qt.Key.Key_Home and smart_home(editor, ev):
            return True

        if key == Qt.Key.Key_Tab:
            mods = ev.modifiers()
            if not mods & Qt.KeyboardModifier.ControlModifier and smart_tab(editor, ev):
                return True

        if key == Qt.Key.Key_Backspace and smart_backspace(editor, ev):
            return True

        return False

    def get_completion_data(self, editor, ev=None):
        c = editor.textCursor()
        c.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
        text = c.selectedText()
        m = self.complete_attr_pat.search(text)
        if m is None:
            return
        query = m.group(1) or ''
        doc_name = editor.completion_doc_name
        if doc_name:
            return 'complete_names', ('css_resource', doc_name, current_container().root), query
