#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap

from PyQt4.Qt import (
    QPlainTextEdit, QApplication, QFontDatabase, QToolTip, QPalette, QFont)

from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.editor.themes import THEMES, DEFAULT_THEME, theme_color
from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter
from calibre.gui2.tweak_book.editor.syntax.html import HTMLHighlighter

_dff = None
def default_font_family():
    global _dff
    if _dff is None:
        families = set(map(unicode, QFontDatabase().families()))
        for x in ('Ubuntu Mono', 'Consolas', 'Liberation Mono'):
            if x in families:
                _dff = x
                break
        if _dff is None:
            _dff = 'Courier New'
    return _dff

class TextEdit(QPlainTextEdit):

    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        self.highlighter = SyntaxHighlighter(self)
        self.apply_theme()
        self.setMouseTracking(True)

    def apply_theme(self):
        theme = THEMES.get(tprefs['editor_theme'], None)
        if theme is None:
            theme = THEMES[DEFAULT_THEME]
        self.theme = theme
        pal = self.palette()
        pal.setColor(pal.Base, theme_color(theme, 'Normal', 'bg'))
        pal.setColor(pal.Text, theme_color(theme, 'Normal', 'fg'))
        pal.setColor(pal.Highlight, theme_color(theme, 'Visual', 'bg'))
        pal.setColor(pal.HighlightedText, theme_color(theme, 'Visual', 'fg'))
        self.setPalette(pal)
        self.tooltip_palette = pal = QPalette()
        pal.setColor(pal.ToolTipBase, theme_color(theme, 'Tooltip', 'bg'))
        pal.setColor(pal.ToolTipText, theme_color(theme, 'Tooltip', 'fg'))
        font = self.font()
        ff = tprefs['editor_font_family']
        if ff is None:
            ff = default_font_family()
        font.setFamily(ff)
        font.setPointSize(tprefs['editor_font_size'])
        self.tooltip_font = QFont(font)
        self.tooltip_font.setPointSize(font.pointSize() - 1)
        self.setFont(font)
        self.highlighter.apply_theme(theme)

    def load_text(self, text, syntax='html'):
        self.highlighter = {'html':HTMLHighlighter}.get(syntax, SyntaxHighlighter)(self)
        self.highlighter.apply_theme(self.theme)
        self.highlighter.setDocument(self.document())
        self.setPlainText(text)

    def event(self, ev):
        if ev.type() == ev.ToolTip:
            self.show_tooltip(ev)
            return True
        return QPlainTextEdit.event(self, ev)

    def syntax_format_for_cursor(self, cursor):
        if cursor.isNull():
            return
        pos = cursor.positionInBlock()
        for r in cursor.block().layout().additionalFormats():
            if r.start <= pos < r.start + r.length:
                return r.format

    def show_tooltip(self, ev):
        c = self.cursorForPosition(ev.pos())
        fmt = self.syntax_format_for_cursor(c)
        if fmt is not None:
            tt = unicode(fmt.toolTip())
            if tt:
                QToolTip.setFont(self.tooltip_font)
                QToolTip.setPalette(self.tooltip_palette)
                QToolTip.showText(ev.globalPos(), textwrap.fill(tt))
        QToolTip.hideText()
        ev.ignore()

if __name__ == '__main__':
    app = QApplication([])
    t = TextEdit()
    t.show()
    t.load_text(textwrap.dedent('''\
                <html>
                <head>
                    <title>Page title</title>
                    <style type="text/css">
                        body { color: green; }
                    </style>
                </head id="1">
                <body>
                <!-- The start of the document -->a
                <h1 class="head" id="one" >A heading</h1>
                <p> A single &. An proper entity &amp;.
                A single < and a single >.
                These cases are perfectly simple and easy to
                distinguish. In a free hour, when our power of choice is
                untrammelled and when nothing prevents our being able to do
                what we like best, every pleasure is to be welcomed and every
                pain avoided.</p>

                <p>
                But in certain circumstances and owing to the claims of duty or the obligations
                of business it will frequently occur that pleasures have to be
                repudiated and annoyances accepted. The wise man therefore
                always holds in these matters to this principle of selection:
                he rejects pleasures to secure other greater pleasures, or else
                he endures pains.</p>
                </body>
                </html>
                '''))
    app.exec_()

