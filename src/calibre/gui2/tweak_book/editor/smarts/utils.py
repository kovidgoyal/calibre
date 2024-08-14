#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from qt.core import Qt, QTextCursor


def get_text_around_cursor(editor, before=True):
    cursor = editor.textCursor()
    cursor.clearSelection()
    cursor.movePosition((QTextCursor.MoveOperation.StartOfBlock if before else QTextCursor.MoveOperation.EndOfBlock), QTextCursor.MoveMode.KeepAnchor)
    text = editor.selected_text_from_cursor(cursor)
    return cursor, text


get_text_before_cursor = get_text_around_cursor
def get_text_after_cursor(editor):
    return get_text_around_cursor(editor, before=False)


def is_cursor_on_wrapped_line(editor):
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
    sol = cursor.position()
    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
    return sol != cursor.position()


def get_leading_whitespace_on_block(editor, previous=False):
    cursor = editor.textCursor()
    block = cursor.block()
    if previous:
        block = block.previous()
    if block.isValid():
        text = block.text()
        ntext = text.lstrip()
        return text[:len(text)-len(ntext)]
    return ''


def no_modifiers(ev, *args):
    mods = ev.modifiers()
    for mod_mask in args:
        if mods & mod_mask:
            return False
    return True


def test_modifiers(ev, *args):
    mods = ev.modifiers()
    for mod_mask in args:
        if not mods & mod_mask:
            return False
    return True


def smart_home(editor, ev):
    if no_modifiers(ev, Qt.KeyboardModifier.ControlModifier) and not is_cursor_on_wrapped_line(editor):
        cursor, text = get_text_before_cursor(editor)
        cursor = editor.textCursor()
        mode = QTextCursor.MoveMode.KeepAnchor if test_modifiers(ev, Qt.KeyboardModifier.ShiftModifier) else QTextCursor.MoveMode.MoveAnchor
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, mode)
        if text.strip() and text.lstrip() != text:
            # Move to the start of text
            cursor.movePosition(QTextCursor.MoveOperation.NextWord, mode)
        editor.setTextCursor(cursor)
        return True
    return False


def expand_tabs(text, tw):
    return text.replace('\t', ' ' * tw)


def smart_tab_if_whitespace_only_before_cursor(editor, backwards):
    cursor, text = get_text_before_cursor(editor)
    if not text.lstrip():
        # cursor is preceded by only whitespace
        tw = editor.tw
        text = expand_tabs(text, tw)
        if backwards:
            if leading := len(text):
                new_leading = max(0, leading - tw)
                extra = new_leading % tw
                if extra:
                    new_leading += tw - extra
                cursor.insertText(' ' * new_leading)
                return True
        else:
            spclen = len(text) - (len(text) % tw) + tw
            cursor.insertText(' ' * spclen)
            editor.setTextCursor(cursor)
            return True
    return False


def smart_tab_all_blocks_in_selection(editor, backwards):
    cursor = editor.textCursor()
    c = QTextCursor(cursor)
    c.clearSelection()
    c.setPosition(cursor.selectionStart())
    tab_width = editor.tw
    changed = False
    while not c.atEnd() and c.position() <= cursor.selectionEnd():
        c.clearSelection()
        c.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        c.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        c.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        # select leading whitespace
        while not c.atEnd() and c.document().characterAt(c.position()).isspace():
            c.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
        text = expand_tabs(editor.selected_text_from_cursor(c), tab_width)
        leading = len(text)
        replaced = False
        if backwards:
            if leading:
                new_leading = max(0, leading - tab_width)
                extra = new_leading % tab_width
                if extra:
                    new_leading += tab_width - extra
                replaced = True
        else:
            new_leading = leading + tab_width
            new_leading -= new_leading % tab_width
            replaced = True
        if replaced:
            c.insertText(' ' * new_leading)
            changed = True
        c.movePosition(QTextCursor.MoveOperation.NextBlock)
        c.movePosition(QTextCursor.MoveOperation.StartOfBlock)
    return changed


def smart_tab(editor, ev):
    cursor = editor.textCursor()
    backwards = ev.key() == Qt.Key.Key_Backtab or (ev.key() == Qt.Key.Key_Tab and bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier))
    if cursor.hasSelection():
        return smart_tab_all_blocks_in_selection(editor, backwards)
    return smart_tab_if_whitespace_only_before_cursor(editor, backwards)


def smart_backspace(editor, ev):
    if editor.textCursor().hasSelection():
        return False
    cursor, text = get_text_before_cursor(editor)
    if text and not text.lstrip():
        # cursor is preceded by only whitespace
        tw = editor.tw
        text = expand_tabs(text, tw)
        spclen = max(0, len(text) - (len(text) % tw) - tw)
        cursor.insertText(' ' * spclen)
        editor.setTextCursor(cursor)
        return True
    return False
