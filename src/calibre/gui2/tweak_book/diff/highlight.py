#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

import os
from typing import TYPE_CHECKING

from qt.core import QPlainTextDocumentLayout, QTextCursor, QTextDocument

from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.editor.syntax.utils import NULL_FMT, format_for_pygments_token
from calibre.gui2.tweak_book.editor.text import SyntaxHighlighter
from calibre.gui2.tweak_book.editor.text import get_highlighter as calibre_highlighter
from calibre.gui2.tweak_book.editor.themes import get_theme, highlight_to_char_format

if TYPE_CHECKING:
    from pygments.lexer import Lexer
    from pygments.token import _TokenType
    from qt.core import QObject, QTextCharFormat

    from calibre.gui2.tweak_book.diff.view import TextBrowser
    from calibre.gui2.tweak_book.editor.themes import Theme


class QtHighlighter(QTextDocument):
    def __init__(self, parent: QObject | None, text: str, hlclass: type[SyntaxHighlighter]) -> None:
        QTextDocument.__init__(self, parent)
        self.l = QPlainTextDocumentLayout(self)
        self.setDocumentLayout(self.l)
        self.highlighter = hlclass()
        self.highlighter.apply_theme(get_theme(tprefs['editor_theme']))
        self.highlighter.set_document(self)
        self.setPlainText(text)

    def copy_lines(self, lo: int, hi: int, cursor: QTextCursor) -> None:
        """Copy specified lines from the syntax highlighted buffer into the
        destination cursor, preserving all formatting created by the syntax
        highlighter."""
        self.highlighter.join()
        num = hi - lo
        if num > 0:
            block = self.findBlockByNumber(lo)
            while num > 0:
                num -= 1
                cursor.insertText(block.text())
                dest_block = cursor.block()
                c = QTextCursor(dest_block)
                layout = block.layout()
                assert layout is not None
                try:
                    afs = layout.formats()
                except AttributeError:
                    afs = ()
                for af in afs:
                    start = dest_block.position() + af.start
                    c.setPosition(start), c.setPosition(start + af.length, QTextCursor.MoveMode.KeepAnchor)
                    c.setCharFormat(af.format)
                cursor.insertBlock()
                cursor.setCharFormat(NULL_FMT)
                block = block.next()


class NullHighlighter:
    def __init__(self, text: str) -> None:
        self.lines = text.splitlines()

    def copy_lines(self, lo: int, hi: int, cursor: QTextCursor) -> None:
        for i in range(lo, hi):
            cursor.insertText(self.lines[i])
            cursor.insertBlock()


def pygments_lexer(filename: str) -> Lexer | None:
    try:
        from pygments.lexers import get_lexer_for_filename
        from pygments.util import ClassNotFound
    except ImportError:
        return None

    def glff(n: str) -> Lexer:
        return get_lexer_for_filename(n, stripnl=False)

    try:
        return glff(filename)
    except ClassNotFound:
        if filename.lower().endswith('.recipe'):
            return glff('a.py')
        return None


class PygmentsHighlighter:
    def __init__(self, text: str, lexer: Lexer) -> None:
        theme: Theme | dict[str | None, QTextCharFormat]
        theme, cache = get_theme(tprefs['editor_theme']), {}
        theme = {k: highlight_to_char_format(v) for k, v in theme.items()}
        theme[None] = NULL_FMT

        def fmt(token: _TokenType) -> QTextCharFormat:
            return format_for_pygments_token(theme, cache, token)

        from pygments import lex

        lines: list[list[tuple[QTextCharFormat, str]]]
        lines = self.lines = [[]]
        current_line = lines[0]
        for token, val in lex(text, lexer):
            for v in val.splitlines(True):
                current_line.append((fmt(token), v))
                if v[-1] in '\n\r':
                    lines.append([])
                    current_line = lines[-1]
                    continue

    def copy_lines(self, lo: int, hi: int, cursor: QTextCursor) -> None:
        for i in range(lo, hi):
            for fmt, text in self.lines[i]:
                cursor.insertText(text, fmt)
            cursor.setCharFormat(NULL_FMT)


def get_highlighter(parent: TextBrowser, text: str, syntax: str | None) -> QtHighlighter | NullHighlighter | PygmentsHighlighter:
    hlclass = calibre_highlighter(syntax)
    if hlclass is SyntaxHighlighter:
        filename = os.path.basename(parent.headers[-1][1])
        lexer = pygments_lexer(filename)
        if lexer is None:
            return NullHighlighter(text)
        return PygmentsHighlighter(text, lexer)
    return QtHighlighter(parent, text, hlclass)
