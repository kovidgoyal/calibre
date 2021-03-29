'''
Created on 26 Mar 2021

@author: Charles Haley
Based on classes in calibre.gui2.tweak_book.editor

License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>
'''

from qt.core import (
    QFont, QPainter, QPalette, QPlainTextEdit, QRect, Qt, QTextEdit, QTextFormat
)

from calibre.gui2.tweak_book.editor.text import LineNumbers
from calibre.gui2.tweak_book.editor.themes import get_theme, theme_color
from polyglot.builtins import unicode_type


class LineNumberArea(LineNumbers):

    def mouseDoubleClickEvent(self, event):
        super().mousePressEvent(event)
        self.parent().line_area_doubleclick_event(event)


class CodeEditor(QPlainTextEdit):

    def __init__(self, parent):
        QPlainTextEdit.__init__(self, parent)

        # Use the default theme from the book editor
        theme = get_theme(None)
        self.line_number_palette = pal = QPalette()
        pal.setColor(QPalette.ColorRole.Base, theme_color(theme, 'LineNr', 'bg'))
        pal.setColor(QPalette.ColorRole.Text, theme_color(theme, 'LineNr', 'fg'))
        pal.setColor(QPalette.ColorRole.BrightText, theme_color(theme, 'LineNrC', 'fg'))

        self.line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_cursor_line)

        self.update_line_number_area_width(0)
        self.highlight_cursor_line()
        self.clicked_line_numbers = set()

    def highlight_cursor_line(self):
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(self.palette().alternateBase())
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel,])

    def update_line_number_area_width(self, block_count=0):
        self.gutter_width = self.line_number_area_width()
        self.setViewportMargins(self.gutter_width, 0, 0, 0)

    def line_number_area_width(self):
        # get largest width of digits
        w = self.fontMetrics()
        self.number_width = max(map(lambda x:w.width(unicode_type(x)), range(10)))
        digits = 1
        limit = max(1, self.blockCount())
        while limit >= 10:
            limit /= 10
            digits += 1
        return self.number_width * (digits+1)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, ev):
        QPlainTextEdit.resizeEvent(self, ev)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(),
                                                self.line_number_area_width(), cr.height()))

    def line_area_doubleclick_event(self, event):
        # remember that the result of the divide will be zero-based
        line = event.y()//self.fontMetrics().height() + 1 + self.firstVisibleBlock().blockNumber()
        if line in self.clicked_line_numbers:
            self.clicked_line_numbers.discard(line)
        else:
            self.clicked_line_numbers.add(line)
        self.update(self.line_number_area.geometry())

    def set_clicked_line_numbers(self, new_set):
        self.clicked_line_numbers = new_set
        self.update(self.line_number_area.geometry())

    def paint_line_numbers(self, ev):
        painter = QPainter(self.line_number_area)
        painter.fillRect(ev.rect(), self.line_number_palette.color(QPalette.ColorRole.Base))

        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current = self.textCursor().block().blockNumber()
        painter.setPen(self.line_number_palette.color(QPalette.ColorRole.Text))

        while block.isValid() and top <= ev.rect().bottom():
            if block.isVisible() and bottom >= ev.rect().top():
                set_bold = False
                set_italic = False
                if current == num:
                    set_bold = True
                if num+1 in self.clicked_line_numbers:
                    set_italic = True
                painter.save()
                if set_bold or set_italic:
                    f = QFont(self.font())
                    if set_bold:
                        f.setBold(set_bold)
                        painter.setPen(self.line_number_palette.color(QPalette.ColorRole.BrightText))
                    f.setItalic(set_italic)
                    painter.setFont(f)
                else:
                    painter.setFont(self.font())
                painter.drawText(0, top, self.line_number_area.width() - 5, self.fontMetrics().height(),
                              Qt.AlignmentFlag.AlignRight, unicode_type(num + 1))
                painter.restore()
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num += 1
