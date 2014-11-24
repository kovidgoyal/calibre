#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

def get_text_before_cursor(editor):
    cursor = editor.textCursor()
    cursor.clearSelection()
    cursor.movePosition(cursor.StartOfBlock, cursor.KeepAnchor)
    text = cursor.selectedText()
    return cursor, text

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



