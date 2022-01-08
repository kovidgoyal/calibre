#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QTextCursor, QTextDocument

opening_map = {
    'css':'/*',
    'html':'<!--',
    'xml':'<!--',
    'javascript':'/*',
}

closing_map = {
    'css':'*/',
    'html':'-->',
    'xml':'-->',
    'javascript':'*/',
}


def apply_smart_comment(editor, opening='/*', closing='*/', line_comment=None):
    doc = editor.document()
    c = QTextCursor(editor.textCursor())
    c.clearSelection()
    before_opening = doc.find(opening, c, QTextDocument.FindFlag.FindBackward | QTextDocument.FindFlag.FindCaseSensitively)
    before_closing = doc.find(closing, c, QTextDocument.FindFlag.FindBackward | QTextDocument.FindFlag.FindCaseSensitively)
    after_opening = doc.find(opening, c, QTextDocument.FindFlag.FindCaseSensitively)
    after_closing = doc.find(closing, c, QTextDocument.FindFlag.FindCaseSensitively)
    in_block_comment = (not before_opening.isNull() and (before_closing.isNull() or before_opening.position() >= before_closing.position())) and \
        (not after_closing.isNull() and (after_opening.isNull() or after_closing.position() <= after_opening.position()))
    if in_block_comment:
        before_opening.removeSelectedText(), after_closing.removeSelectedText()
        return
    c = QTextCursor(editor.textCursor())
    left, right = min(c.position(), c.anchor()), max(c.position(), c.anchor())
    c.beginEditBlock()
    c.setPosition(right), c.insertText(closing)
    c.setPosition(left), c.insertText(opening)
    c.endEditBlock()


def smart_comment(editor, syntax):
    apply_smart_comment(editor, opening=opening_map.get(syntax, '/*'), closing=closing_map.get(syntax, '*/'))
