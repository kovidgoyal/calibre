#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QTextCharFormat, QFont, QBrush, QColor

from pygments.formatter import Formatter as PF
from pygments.token import Token

class Formatter(object):

    def __init__(self, prompt, continuation, **options):
        if len(prompt) != len(continuation):
            raise ValueError('%r does not have the same length as %r' %
                    (prompt, continuation))

        self.prompt, self.continuation = prompt, continuation

        pf = PF(**options)
        self.styles = {}
        self.normal = self.base_fmt()
        for ttype, ndef in pf.style:
            fmt = self.base_fmt()
            if ndef['color']:
                fmt.setForeground(QBrush(QColor('#%s'%ndef['color'])))
                fmt.setUnderlineColor(QColor('#%s'%ndef['color']))
            if ndef['bold']:
                fmt.setFontWeight(QFont.Bold)
            if ndef['italic']:
                fmt.setFontItalic(True)
            if ndef['underline']:
                fmt.setFontUnderline(True)
            if ndef['bgcolor']:
                fmt.setBackground(QBrush(QColor('#%s'%ndef['bgcolor'])))
            if ndef['border']:
                pass # No support for borders

            self.styles[ttype] = fmt

    def base_fmt(self):
        fmt = QTextCharFormat()
        fmt.setFontFamily('monospace')
        return fmt

    def render_raw(self, raw, cursor):
        cursor.insertText(raw, self.normal)

    def render_syntax_error(self, tb, cursor):
        fmt = self.styles[Token.Error]
        cursor.insertText(tb, fmt)

    def render(self, tokens, cursor):
        lastval = ''
        lasttype = None

        for ttype, value in tokens:
            while ttype not in self.styles:
                ttype = ttype.parent
            if ttype == lasttype:
                lastval += value
            else:
                if lastval:
                    fmt = self.styles[lasttype]
                    cursor.insertText(lastval, fmt)
                lastval = value
                lasttype = ttype

        if lastval:
            fmt = self.styles[lasttype]
            cursor.insertText(lastval, fmt)

    def render_prompt(self, is_continuation, cursor):
        pr = self.continuation if is_continuation else self.prompt
        fmt = self.styles[Token.Generic.Subheading]
        cursor.insertText(pr, fmt)


