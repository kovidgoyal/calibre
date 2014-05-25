#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from PyQt4.Qt import QTextDocument, QTextCursor, QTextCharFormat, QPlainTextDocumentLayout

from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.editor.text import get_highlighter as calibre_highlighter, SyntaxHighlighter
from calibre.gui2.tweak_book.editor.themes import get_theme, highlight_to_char_format

NULL_FMT = QTextCharFormat()

class QtHighlighter(QTextDocument):

    def __init__(self, parent, text, hlclass):
        QTextDocument.__init__(self, parent)
        self.l = QPlainTextDocumentLayout(self)
        self.setDocumentLayout(self.l)
        self.highlighter = hlclass()
        self.highlighter.apply_theme(get_theme(tprefs['editor_theme']))
        self.highlighter.set_document(self)
        self.setPlainText(text)

    def copy_lines(self, lo, hi, cursor):
        ''' Copy specified lines from the syntax highlighted buffer into the
        destination cursor, preserving all formatting created by the syntax
        highlighter. '''
        num = hi - lo
        if num > 0:
            block = self.findBlockByNumber(lo)
            while num > 0:
                num -= 1
                cursor.insertText(block.text())
                dest_block = cursor.block()
                c = QTextCursor(dest_block)
                for af in block.layout().additionalFormats():
                    start = dest_block.position() + af.start
                    c.setPosition(start), c.setPosition(start + af.length, c.KeepAnchor)
                    c.setCharFormat(af.format)
                cursor.insertBlock()
                cursor.setCharFormat(NULL_FMT)
                block = block.next()

class NullHighlighter(object):

    def __init__(self, text):
        self.lines = text.splitlines()

    def copy_lines(self, lo, hi, cursor):
        for i in xrange(lo, hi):
            cursor.insertText(self.lines[i])
            cursor.insertBlock()

def pygments_lexer(filename):
    try:
        from pygments.lexers import get_lexer_for_filename
        from pygments.util import ClassNotFound
    except ImportError:
        return None
    glff = lambda n: get_lexer_for_filename(n, stripnl=False)
    try:
        return glff(filename)
    except ClassNotFound:
        if filename.lower().endswith('.recipe'):
            return glff('a.py')
        return None

_pyg_map = None
def pygments_map():
    global _pyg_map
    if _pyg_map is None:
        from pygments.token import Token
        _pyg_map = {
            Token: None,
            Token.Comment: 'Comment',
            Token.Comment.Preproc: 'PreProc',
            Token.String: 'String',
            Token.Number: 'Number',
            Token.Keyword.Type: 'Type',
            Token.Keyword: 'Keyword',
            Token.Name.Builtin: 'Identifier',
            Token.Operator: 'Statement',
            Token.Name.Function: 'Function',
            Token.Literal: 'Constant',
            Token.Error: 'Error',
        }
    return _pyg_map

def format_for_token(theme, cache, token):
    try:
        return cache[token]
    except KeyError:
        pass
    pmap = pygments_map()
    while token is not None:
        try:
            name = pmap[token]
        except KeyError:
            token = token.parent
            continue
        cache[token] = ans = theme[name]
        return ans
    cache[token] = ans = NULL_FMT
    return ans

class PygmentsHighlighter(object):

    def __init__(self, text, lexer):
        theme, cache = get_theme(tprefs['editor_theme']), {}
        theme = {k:highlight_to_char_format(v) for k, v in theme.iteritems()}
        theme[None] = NULL_FMT
        def fmt(token):
            return format_for_token(theme, cache, token)

        from pygments import lex
        lines = self.lines = [[]]
        current_line = lines[0]
        for token, val in lex(text, lexer):
            for v in val.splitlines(True):
                current_line.append((fmt(token), v))
                if v[-1] in '\n\r':
                    lines.append([])
                    current_line = lines[-1]
                    continue

    def copy_lines(self, lo, hi, cursor):
        for i in xrange(lo, hi):
            for fmt, text in self.lines[i]:
                cursor.insertText(text, fmt)
            cursor.setCharFormat(NULL_FMT)

def get_highlighter(parent, text, syntax):
    hlclass = calibre_highlighter(syntax)
    if hlclass is SyntaxHighlighter:
        filename = os.path.basename(parent.headers[-1][1])
        lexer = pygments_lexer(filename)
        if lexer is None:
            return NullHighlighter(text)
        return PygmentsHighlighter(text, lexer)
    return QtHighlighter(parent, text, hlclass)
