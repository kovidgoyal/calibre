#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys
from functools import partial
from collections import namedtuple

from PyQt4.Qt import (
    QSplitter, QApplication, QPlainTextDocumentLayout, QTextDocument,
    QTextCursor, QTextCharFormat, Qt, QRect, QPainter, QPalette, QPen)

from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.editor.text import PlainTextEdit, get_highlighter, default_font_family, LineNumbers
from calibre.gui2.tweak_book.editor.themes import THEMES, default_theme, theme_color
from calibre.utils.diff import get_sequence_matcher

Change = namedtuple('Change', 'ltop lbot rtop rbot kind')

def get_theme():
    theme = THEMES.get(tprefs['editor_theme'], None)
    if theme is None:
        theme = THEMES[default_theme()]
    return theme

class TextBrowser(PlainTextEdit):  # {{{

    def __init__(self, right=False, parent=None):
        PlainTextEdit.__init__(self, parent)
        self.right = right
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
        self.changes = []
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.diff_backgrounds = {
            'replace' : theme_color(theme, 'DiffReplace', 'bg'),
            'insert'  : theme_color(theme, 'DiffInsert', 'bg'),
            'delete'  : theme_color(theme, 'DiffDelete', 'bg'),
        }
        self.diff_foregrounds = {
            'replace' : theme_color(theme, 'DiffReplace', 'fg'),
            'insert'  : theme_color(theme, 'DiffInsert', 'fg'),
            'delete'  : theme_color(theme, 'DiffDelete', 'fg'),
        }

    def clear(self):
        PlainTextEdit.clear(self)
        self.line_number_map.clear()
        del self.changes[:]

    def update_line_number_area_width(self, block_count=0):
        if self.right:
            self.setViewportMargins(0, 0, self.line_number_area_width(), 0)
        else:
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
        if self.right:
            self.line_number_area.setGeometry(QRect(cr.right() - self.line_number_area_width(), cr.top(), cr.right(), cr.height()))
        else:
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
            r = ev.rect()
            if block.isVisible() and bottom >= r.top():
                if self.right:
                    painter.drawText(r.left() + 3, top, r.right(), self.fontMetrics().height(),
                              Qt.AlignLeft, unicode(self.line_number_map.get(num, '')))
                else:
                    painter.drawText(r.left(), top, r.right() - 5, self.fontMetrics().height(),
                              Qt.AlignRight, unicode(self.line_number_map.get(num, '')))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num += 1

    def paintEvent(self, event):
        w = self.width()
        painter = QPainter(self.viewport())
        painter.setClipRect(event.rect())
        floor = event.rect().bottom()
        ceiling = event.rect().top()
        fv = self.firstVisibleBlock().blockNumber()
        origin = self.contentOffset()
        doc = self.document()

        for top, bot, kind in self.changes:
            if bot < fv:
                continue
            y_top = self.blockBoundingGeometry(doc.findBlockByNumber(top)).translated(origin).y() - 1
            y_bot = self.blockBoundingGeometry(doc.findBlockByNumber(bot)).translated(origin).y() + 1
            if max(y_top, y_bot) < ceiling:
                continue
            if min(y_top, y_bot) > floor:
                break
            painter.fillRect(0,  y_top, w, y_bot - y_top, self.diff_backgrounds[kind])
            painter.setPen(QPen(self.diff_foregrounds[kind], 1))
            painter.drawLine(0, y_top, w, y_top)
            painter.drawLine(0, y_bot - 1, w, y_bot - 1)
        painter.end()
        PlainTextEdit.paintEvent(self, event)

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

        self.left, self.right = TextBrowser(parent=self), TextBrowser(right=True, parent=self)
        self.addWidget(self.left), self.addWidget(self.right)

    def __call__(self, left_text, right_text, context=None, syntax=None):
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()
        self.left_highlight, self.right_highlight = Highlight(self, left_text, syntax), Highlight(self, right_text, syntax)
        self.context = context

        self.cruncher = get_sequence_matcher()(None, left_lines, right_lines)
        self.do_layout(context)

    def refresh(self):
        self.do_layout(self.context)

    def do_layout(self, context=None):
        self.left.clear(), self.right.clear()
        cl, cr = self.left_cursor, self.right_cursor = self.left.textCursor(), self.right.textCursor()
        cl.beginEditBlock(), cr.beginEditBlock()
        self.changes = []
        self.left_insert = partial(self.do_insert, cl, self.left_highlight, self.left.line_number_map)
        self.right_insert = partial(self.do_insert, cr, self.right_highlight, self.right.line_number_map)

        if context is None:
            for tag, alo, ahi, blo, bhi in self.cruncher.get_opcodes():
                getattr(self, tag)(alo, ahi, blo, bhi)
        else:
            for group in self.cruncher.get_grouped_opcodes():
                for tag, alo, ahi, blo, bhi in group:
                    getattr(self, tag)(alo, ahi, blo, bhi)
        cl.endEditBlock(), cr.endEditBlock()

        for v in (self.left, self.right):
            c = v.textCursor()
            c.movePosition(c.Start)
            v.setTextCursor(c)

        for ltop, lbot, rtop, rbot, kind in self.changes:
            self.left.changes.append((ltop, lbot, kind))
            self.right.changes.append((rtop, rbot, kind))

        self.update()

    def do_insert(self, cursor, highlighter, line_number_map, lo, hi):
        start_block = cursor.block()
        highlighter.copy_lines(lo, hi, cursor)
        for num, i in enumerate(xrange(start_block.blockNumber(), cursor.blockNumber())):
            line_number_map[i] = lo + num + 1
        return start_block.blockNumber(), cursor.block().blockNumber()

    def equal(self, alo, ahi, blo, bhi):
        self.left_insert(alo, ahi), self.right_insert(blo, bhi)

    def delete(self, alo, ahi, blo, bhi):
        start_block, current_block = self.left_insert(alo, ahi)
        r = self.right_cursor.block().blockNumber()
        self.changes.append(Change(
            ltop=start_block, lbot=current_block, rtop=r, rbot=r, kind='delete'))

    def insert(self, alo, ahi, blo, bhi):
        start_block, current_block = self.right_insert(blo, bhi)
        l = self.left_cursor.block().blockNumber()
        self.changes.append(Change(
            rtop=start_block, rbot=current_block, ltop=l, lbot=l, kind='insert'))

    def replace(self, alo, ahi, blo, bhi):
        lsb, lcb = self.left_insert(alo, ahi)
        rsb, rcb = self.right_insert(blo, bhi)
        self.changes.append(Change(
            rtop=rsb, rbot=rcb, ltop=lsb, lbot=lcb, kind='replace'))

if __name__ == '__main__':
    app = QApplication([])
    raw1 = open(sys.argv[-2], 'rb').read().decode('utf-8')
    raw2 = open(sys.argv[-1], 'rb').read().decode('utf-8')
    w = TextDiffView()
    w.show()
    w(raw1, raw2, syntax='html', context=None)
    app.exec_()

# TODO: Add diff colors for other color schemes
# TODO: Handle scroll wheel and key up/down events
