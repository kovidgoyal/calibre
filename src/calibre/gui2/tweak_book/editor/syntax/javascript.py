#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from pygments.lexer import RegexLexer, default, include
from pygments.token import Comment, Punctuation, Number, Keyword, Text, String, Operator, Name
import pygments.unistring as uni

from calibre.gui2.tweak_book.editor.syntax.pygments_highlighter import create_highlighter

JS_IDENT_START = ('(?:[$_' + uni.combine('Lu', 'Ll', 'Lt', 'Lm', 'Lo', 'Nl') +
                  ']|\\\\u[a-fA-F0-9]{4})')
JS_IDENT_PART = ('(?:[$' + uni.combine('Lu', 'Ll', 'Lt', 'Lm', 'Lo', 'Nl',
                                       'Mn', 'Mc', 'Nd', 'Pc') +
                 u'\u200c\u200d]|\\\\u[a-fA-F0-9]{4})')
JS_IDENT = JS_IDENT_START + '(?:' + JS_IDENT_PART + ')*'


class JavascriptLexer(RegexLexer):

    """
    For JavaScript source code. This is based on the pygments JS highlighter,
    bu that does not handle multi-line comments in streaming mode, so we had to
    modify it.
    """

    flags = re.UNICODE | re.MULTILINE

    tokens = {
        b'commentsandwhitespace': [
            (r'\s+', Text),
            (r'<!--', Comment),
            (r'//.*?$', Comment.Single),
            (r'/\*', Comment.Multiline, b'comment')
        ],
        b'comment': [
            (r'[^*/]+', Comment.Multiline),
            (r'\*/', Comment.Multiline, b'#pop'),
            (r'[*/]', Comment.Multiline),
        ],
        b'slashstartsregex': [
            include(b'commentsandwhitespace'),
            (r'/(\\.|[^[/\\\n]|\[(\\.|[^\]\\\n])*])+/'
             r'([gim]+\b|\B)', String.Regex, b'#pop'),
            (r'(?=/)', Text, (b'#pop', b'badregex')),
            default(b'#pop')
        ],
        b'badregex': [
            (r'\n', Text, b'#pop')
        ],
        b'root': [
            (r'\A#! ?/.*?\n', Comment),  # shebang lines are recognized by node.js
            (r'^(?=\s|/|<!--)', Text, b'slashstartsregex'),
            include(b'commentsandwhitespace'),
            (r'\+\+|--|~|&&|\?|:|\|\||\\(?=\n)|'
             r'(<<|>>>?|==?|!=?|[-<>+*%&|^/])=?', Operator, b'slashstartsregex'),
            (r'[{(\[;,]', Punctuation, b'slashstartsregex'),
            (r'[})\].]', Punctuation),
            (r'(for|in|while|do|break|return|continue|switch|case|default|if|else|'
             r'throw|try|catch|finally|new|delete|typeof|instanceof|void|yield|'
             r'this)\b', Keyword, b'slashstartsregex'),
            (r'(var|let|with|function)\b', Keyword.Declaration, b'slashstartsregex'),
            (r'(abstract|boolean|byte|char|class|const|debugger|double|enum|export|'
             r'extends|final|float|goto|implements|import|int|interface|long|native|'
             r'package|private|protected|public|short|static|super|synchronized|throws|'
             r'transient|volatile)\b', Keyword.Reserved),
            (r'(true|false|null|NaN|Infinity|undefined)\b', Keyword.Constant),
            (r'(Array|Boolean|Date|Error|Function|Math|netscape|'
             r'Number|Object|Packages|RegExp|String|sun|decodeURI|'
             r'decodeURIComponent|encodeURI|encodeURIComponent|'
             r'Error|eval|isFinite|isNaN|parseFloat|parseInt|document|this|'
             r'window)\b', Name.Builtin),
            (JS_IDENT, Name.Other),
            (r'[0-9][0-9]*\.[0-9]+([eE][0-9]+)?[fd]?', Number.Float),
            (r'0x[0-9a-fA-F]+', Number.Hex),
            (r'[0-9]+', Number.Integer),
            (r'"(\\\\|\\"|[^"])*"', String.Double),
            (r"'(\\\\|\\'|[^'])*'", String.Single),
        ]
    }


Highlighter = create_highlighter('JavascriptHighlighter', JavascriptLexer)

if __name__ == '__main__':
    from calibre.gui2.tweak_book.editor.widget import launch_editor
    launch_editor(P('viewer/images.js'), syntax='javascript')
