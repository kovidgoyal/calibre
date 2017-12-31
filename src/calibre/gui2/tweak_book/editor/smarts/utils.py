#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import Qt


def get_text_around_cursor(editor, before=True):
    cursor = editor.textCursor()
    cursor.clearSelection()
    cursor.movePosition((cursor.StartOfBlock if before else cursor.EndOfBlock), cursor.KeepAnchor)
    text = editor.selected_text_from_cursor(cursor)
    return cursor, text


get_text_before_cursor = get_text_around_cursor
get_text_after_cursor = lambda editor: get_text_around_cursor(editor, before=False)


def is_cursor_on_wrapped_line(editor):
    cursor = editor.textCursor()
    cursor.movePosition(cursor.StartOfLine)
    sol = cursor.position()
    cursor.movePosition(cursor.StartOfBlock)
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
        if int(mods & mod_mask):
            return False
    return True


def test_modifiers(ev, *args):
    mods = ev.modifiers()
    for mod_mask in args:
        if not int(mods & mod_mask):
            return False
    return True


def smart_home(editor, ev):
    if no_modifiers(ev, Qt.ControlModifier) and not is_cursor_on_wrapped_line(editor):
        cursor, text = get_text_before_cursor(editor)
        cursor = editor.textCursor()
        mode = cursor.KeepAnchor if test_modifiers(ev, Qt.ShiftModifier) else cursor.MoveAnchor
        cursor.movePosition(cursor.StartOfBlock, mode)
        if text.strip() and text.lstrip() != text:
            # Move to the start of text
            cursor.movePosition(cursor.NextWord, mode)
        editor.setTextCursor(cursor)
        return True
    return False


def expand_tabs(text, tw):
    return text.replace('\t', ' ' * tw)


def smart_tab(editor, ev):
    cursor, text = get_text_before_cursor(editor)
    if not text.lstrip():
        # cursor is preceded by only whitespace
        tw = editor.tw
        text = expand_tabs(text, tw)
        spclen = len(text) - (len(text) % tw) + tw
        cursor.insertText(' ' * spclen)
        editor.setTextCursor(cursor)
        return True
    return False


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
