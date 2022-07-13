'''
Created on 26 Mar 2021

@author: Charles Haley
Based on classes in calibre.gui2.tweak_book.editor

License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>
'''

from qt.core import (
    QFont, QPainter, QPalette, QPlainTextEdit, QRect, Qt, QTextEdit,
    QTextFormat, QTextCursor
)

from calibre.gui2.tweak_book.editor.text import LineNumbers
from calibre.gui2.tweak_book.editor.themes import get_theme, theme_color


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
        # Don't highlight if no text so that the placeholder text shows
        if not (self.blockCount() == 1 and len(self.toPlainText().strip()) == 0):
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
        fm = self.fontMetrics()
        self.number_width = max(map(lambda x:fm.horizontalAdvance(str(x)), range(10)))
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

    def number_of_lines(self):
        return self.blockCount()

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
                              Qt.AlignmentFlag.AlignRight, str(num + 1))
                painter.restore()
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num += 1

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Insert:
            self.setOverwriteMode(self.overwriteMode() ^ True)
            ev.accept()
            return
        key = ev.key()
        if key == Qt.Key_Tab or key == Qt.Key_Backtab:
            '''
            Handle indenting usingTab and Shift Tab. This is remarkably
            difficult because of the way Qt represents the edit buffer.

            Selections represent the start and end as character positions in the
            buffer. To convert a position into a line number we must get the
            block number containing that position. You so this by setting a
            cursor to that position.

            To get the text of a line we must convert the line number (the
            block number) to a block and then fetch the text from that.

            To change text we must create a cursor that selects all the text on
            the line. Because cursors use document positions, not block numbers
            or blocks, we must convert line numbers to blocks then get the
            position of the first character of the block. We then "extend" the
            selection to the end by computing the end position: the start + the
            length of the text on the line. We then uses that cursor to
            "insert" the new text, which magically replaces the selected text.
            '''
            # Get the position of the start and end of the selection.
            cursor = self.textCursor()
            start_position = cursor.selectionStart()
            end_position = cursor.selectionEnd()

            # Now convert positions into block (line) numbers
            cursor.setPosition(start_position)
            start_block = cursor.block().blockNumber()
            cursor.setPosition(end_position)
            end_block = cursor.block().blockNumber()

            def select_block(block_number, curs):
                # Note the side effect: 'curs' is changed to select the line
                blk = self.document().findBlockByNumber(block_number)
                txt = blk.text()
                pos = blk.position()
                curs.setPosition(pos)
                curs.setPosition(pos+len(txt), QTextCursor.MoveMode.KeepAnchor)
                return txt

            # Check if there is a selection. If not then only Shift-Tab is valid
            if start_position == end_position:
                if key == Qt.Key_Backtab:
                    txt = select_block(start_block, cursor)
                    if txt.startswith('\t'):
                        # This works because of the side effect in select_block()
                        cursor.insertText(txt[1:])
                    cursor.setPosition(start_position-1)
                    self.setTextCursor(cursor)
                    ev.accept()
                else:
                    QPlainTextEdit.keyPressEvent(self, ev)
                return
            # There is a selection so both Tab and Shift-Tab do indenting operations
            for bn in range(start_block, end_block+1):
                txt = select_block(bn, cursor)
                if key == Qt.Key_Backtab:
                    if txt.startswith('\t'):
                        cursor.insertText(txt[1:])
                        if bn == start_block:
                            start_position -= 1
                        end_position -= 1
                else:
                    cursor.insertText('\t' + txt)
                    if bn == start_block:
                        start_position += 1
                    end_position += 1
            # Restore the selection, adjusted for the added or deleted tabs
            cursor.setPosition(start_position)
            cursor.setPosition(end_position, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            ev.accept()
            return
        QPlainTextEdit.keyPressEvent(self, ev)
