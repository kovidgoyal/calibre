#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys
from functools import partial

from PyQt4.Qt import (
    QSplitter, QApplication, QPlainTextDocumentLayout, QTextDocument,
    QTextCursor, QTextCharFormat, Qt, QRect, QPainter, QPalette)

from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.editor.text import PlainTextEdit, get_highlighter, default_font_family, LineNumbers
from calibre.gui2.tweak_book.editor.themes import THEMES, default_theme, theme_color
from calibre.utils.diff import get_sequence_matcher

def get_theme():
    theme = THEMES.get(tprefs['editor_theme'], None)
    if theme is None:
        theme = THEMES[default_theme()]
    return theme

class TextBrowser(PlainTextEdit):  # {{{

    def __init__(self, parent=None):
        PlainTextEdit.__init__(self, parent)
        self.setReadOnly(True)
        w = self.fontMetrics()
        self.number_width = max(map(lambda x:w.width(str(x)), xrange(10)))
        self.space_width = w.width(' ')
        self.setLineWrapMode(self.WidgetWidth if tprefs['editor_line_wrap'] else self.NoWrap)
        self.setTabStopWidth(tprefs['editor_tab_stop_width'] * self.space_width)
        font = self.font()
        ff = tprefs['editor_font_family']
        if ff is None:
            ff = default_font_family()
        font.setFamily(ff)
        font.setPointSize(tprefs['editor_font_size'])
        self.setFont(font)
        theme = get_theme()
        pal = self.palette()
        pal.setColor(pal.Base, theme_color(theme, 'Normal', 'bg'))
        pal.setColor(pal.AlternateBase, theme_color(theme, 'CursorLine', 'bg'))
        pal.setColor(pal.Text, theme_color(theme, 'Normal', 'fg'))
        pal.setColor(pal.Highlight, theme_color(theme, 'Visual', 'bg'))
        pal.setColor(pal.HighlightedText, theme_color(theme, 'Visual', 'fg'))
        self.setPalette(pal)
        self.viewport().setCursor(Qt.ArrowCursor)
        self.line_number_area = LineNumbers(self)
        self.blockCountChanged[int].connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.line_number_palette = pal = QPalette()
        pal.setColor(pal.Base, theme_color(theme, 'LineNr', 'bg'))
        pal.setColor(pal.Text, theme_color(theme, 'LineNr', 'fg'))
        pal.setColor(pal.BrightText, theme_color(theme, 'LineNrC', 'fg'))
        self.line_number_map = {}

    def update_line_number_area_width(self, block_count=0):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def line_number_area_width(self):
        digits = 1
        limit = max(1, self.blockCount())
        while limit >= 10:
            limit /= 10
            digits += 1

        return 8 + self.number_width * digits

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, ev):
        PlainTextEdit.resizeEvent(self, ev)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def paint_line_numbers(self, ev):
        painter = QPainter(self.line_number_area)
        painter.fillRect(ev.rect(), self.line_number_palette.color(QPalette.Base))

        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        painter.setPen(self.line_number_palette.color(QPalette.Text))

        while block.isValid() and top <= ev.rect().bottom():
            if block.isVisible() and bottom >= ev.rect().top():
                painter.drawText(0, top, self.line_number_area.width() - 5, self.fontMetrics().height(),
                              Qt.AlignRight, unicode(self.line_number_map.get(num, '')))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num += 1
# }}}

class Highlight(QTextDocument):  # {{{

    def __init__(self, parent, text, syntax):
        QTextDocument.__init__(self, parent)
        self.l = QPlainTextDocumentLayout(self)
        self.setDocumentLayout(self.l)
        self.highlighter = get_highlighter(syntax)(self)
        self.highlighter.apply_theme(get_theme())
        self.highlighter.setDocument(self)
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
                cursor.setCharFormat(QTextCharFormat())
                block = block.next()
# }}}

class TextDiffView(QSplitter):

    def __init__(self, parent=None):
        QSplitter.__init__(self, parent)

        self.left, self.right = TextBrowser(self), TextBrowser(self)
        self.addWidget(self.left), self.addWidget(self.right)

    def __call__(self, left_text, right_text, context=None, syntax=None):
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()
        self.left_highlight, self.right_highlight = Highlight(self, left_text, syntax), Highlight(self, right_text, syntax)
        self.context = context

        self.left_insert = partial(self.do_insert, self.left.textCursor(), self.left_highlight, self.left.line_number_map)
        self.right_insert = partial(self.do_insert, self.right.textCursor(), self.right_highlight, self.right.line_number_map)
        self.cruncher = get_sequence_matcher()(None, left_lines, right_lines)
        self.do_layout(context)

    def refresh(self):
        self.do_layout(self.context)

    def do_layout(self, context=None):
        self.left.clear(), self.right.clear()
        self.left.line_number_map.clear(), self.right.line_number_map.clear()
        if context is None:
            for tag, alo, ahi, blo, bhi in self.cruncher.get_opcodes():
                getattr(self, tag)(alo, ahi, blo, bhi)
        else:
            for group in self.cruncher.get_grouped_opcodes():
                for tag, alo, ahi, blo, bhi in group:
                    getattr(self, tag)(alo, ahi, blo, bhi)

        for v in (self.left, self.right):
            c = v.textCursor()
            c.movePosition(c.Start)
            v.setTextCursor(c)

    def do_insert(self, cursor, highlighter, line_number_map, lo, hi):
        start_block = cursor.blockNumber()
        highlighter.copy_lines(lo, hi, cursor)
        for num, i in enumerate(xrange(start_block, cursor.blockNumber())):
            line_number_map[i] = lo + num + 1
        return start_block, cursor.blockNumber()

    def equal(self, alo, ahi, blo, bhi):
        self.left_insert(alo, ahi), self.right_insert(blo, bhi)

    def delete(self, alo, ahi, blo, bhi):
        self.left_insert(alo, ahi)

    def insert(self, alo, ahi, blo, bhi):
        self.right_insert(blo, bhi)

    def replace(self, alo, ahi, blo, bhi):
        self.left_insert(alo, ahi)
        self.right_insert(blo, bhi)

if __name__ == '__main__':
    app = QApplication([])
    raw1 = open(sys.argv[-2], 'rb').read().decode('utf-8')
    raw2 = open(sys.argv[-1], 'rb').read().decode('utf-8')
    w = TextDiffView()
    w(raw1, raw2, syntax='html', context=None)
    w.show()
    app.exec_()

