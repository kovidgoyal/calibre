#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re
import textwrap, unicodedata
from future_builtins import map

import regex
from PyQt4.Qt import (
    QPlainTextEdit, QFontDatabase, QToolTip, QPalette, QFont, QKeySequence,
    QTextEdit, QTextFormat, QWidget, QSize, QPainter, Qt, QRect, pyqtSlot,
    QApplication, QMimeData, QColor, QColorDialog)

from calibre import prepare_string_for_xml, xml_entity_to_unicode
from calibre.gui2.tweak_book import tprefs, TOP
from calibre.gui2.tweak_book.editor import SYNTAX_PROPERTY
from calibre.gui2.tweak_book.editor.themes import THEMES, default_theme, theme_color, theme_format
from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter
from calibre.gui2.tweak_book.editor.syntax.html import HTMLHighlighter, XMLHighlighter
from calibre.gui2.tweak_book.editor.syntax.css import CSSHighlighter
from calibre.gui2.tweak_book.editor.smart import NullSmarts
from calibre.gui2.tweak_book.editor.smart.html import HTMLSmarts
from calibre.utils.icu import safe_chr

PARAGRAPH_SEPARATOR = '\u2029'
entity_pat = re.compile(r'&(#{0,1}[a-zA-Z0-9]{1,8});')

def get_highlighter(syntax):
    return {'html':HTMLHighlighter, 'css':CSSHighlighter, 'xml':XMLHighlighter}.get(syntax, SyntaxHighlighter)

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

class LineNumbers(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)

    def sizeHint(self):
        return QSize(self.parent().line_number_area_width(), 0)

    def paintEvent(self, ev):
        self.parent().paint_line_numbers(ev)
# }}}

class PlainTextEdit(QPlainTextEdit):

    ''' A class that overrides some methods from QPlainTextEdit to fix handling
    of the nbsp unicode character. '''

    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        self.selectionChanged.connect(self.selection_changed)

    def toPlainText(self):
        # QPlainTextEdit's toPlainText implementation replaces nbsp with normal
        # space, so we re-implement it using QTextCursor, which does not do
        # that
        c = self.textCursor()
        c.clearSelection()
        c.movePosition(c.Start)
        c.movePosition(c.End, c.KeepAnchor)
        ans = c.selectedText().replace(PARAGRAPH_SEPARATOR, '\n')
        # QTextCursor pads the return value of selectedText with null bytes if
        # non BMP characters such as 0x1f431 are present.
        if hasattr(ans, 'rstrip'):
            ans = ans.rstrip('\0')
        else:  # QString
            while ans[-1] == '\0':
                ans.chop(1)
        return ans

    @pyqtSlot()
    def copy(self):
        # Workaround Qt replacing nbsp with normal spaces on copy
        c = self.textCursor()
        if not c.hasSelection():
            return
        md = QMimeData()
        md.setText(self.selected_text)
        QApplication.clipboard().setMimeData(md)

    @pyqtSlot()
    def cut(self):
        # Workaround Qt replacing nbsp with normal spaces on copy
        self.copy()
        self.textCursor().removeSelectedText()

    @property
    def selected_text(self):
        return unicodedata.normalize('NFC', unicode(self.textCursor().selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0'))

    def selection_changed(self):
        # Workaround Qt replacing nbsp with normal spaces on copy
        clipboard = QApplication.clipboard()
        if clipboard.supportsSelection() and self.textCursor().hasSelection():
            md = QMimeData()
            md.setText(self.selected_text)
            clipboard.setMimeData(md, clipboard.Selection)

    def event(self, ev):
        if ev.type() == ev.ShortcutOverride and ev in (QKeySequence.Copy, QKeySequence.Cut):
            ev.accept()
            (self.copy if ev == QKeySequence.Copy else self.cut)()
            return True
        return QPlainTextEdit.event(self, ev)

class TextEdit(PlainTextEdit):

    def __init__(self, parent=None):
        PlainTextEdit.__init__(self, parent)
        self.saved_matches = {}
        self.smarts = NullSmarts(self)
        self.current_cursor_line = None
        self.current_search_mark = None
        self.highlighter = SyntaxHighlighter(self)
        self.line_number_area = LineNumbers(self)
        self.apply_settings()
        self.setMouseTracking(True)
        self.cursorPositionChanged.connect(self.highlight_cursor_line)
        self.blockCountChanged[int].connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.syntax = None

    @dynamic_property
    def is_modified(self):
        ''' True if the document has been modified since it was loaded or since
        the last time is_modified was set to False. '''
        def fget(self):
            return self.document().isModified()
        def fset(self, val):
            self.document().setModified(bool(val))
        return property(fget=fget, fset=fset)

    def sizeHint(self):
        return self.size_hint

    def apply_settings(self, prefs=None):  # {{{
        prefs = prefs or tprefs
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth if prefs['editor_line_wrap'] else QPlainTextEdit.NoWrap)
        theme = THEMES.get(prefs['editor_theme'], None)
        if theme is None:
            theme = THEMES[default_theme()]
        self.apply_theme(theme)
        w = self.fontMetrics()
        self.space_width = w.width(' ')
        self.setTabStopWidth(prefs['editor_tab_stop_width'] * self.space_width)

    def apply_theme(self, theme):
        self.theme = theme
        pal = self.palette()
        pal.setColor(pal.Base, theme_color(theme, 'Normal', 'bg'))
        pal.setColor(pal.AlternateBase, theme_color(theme, 'CursorLine', 'bg'))
        pal.setColor(pal.Text, theme_color(theme, 'Normal', 'fg'))
        pal.setColor(pal.Highlight, theme_color(theme, 'Visual', 'bg'))
        pal.setColor(pal.HighlightedText, theme_color(theme, 'Visual', 'fg'))
        self.setPalette(pal)
        self.tooltip_palette = pal = QPalette()
        pal.setColor(pal.ToolTipBase, theme_color(theme, 'Tooltip', 'bg'))
        pal.setColor(pal.ToolTipText, theme_color(theme, 'Tooltip', 'fg'))
        self.line_number_palette = pal = QPalette()
        pal.setColor(pal.Base, theme_color(theme, 'LineNr', 'bg'))
        pal.setColor(pal.Text, theme_color(theme, 'LineNr', 'fg'))
        pal.setColor(pal.BrightText, theme_color(theme, 'LineNrC', 'fg'))
        self.match_paren_format = theme_format(theme, 'MatchParen')
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
        w = self.fontMetrics()
        self.number_width = max(map(lambda x:w.width(str(x)), xrange(10)))
        self.size_hint = QSize(100 * w.averageCharWidth(), 50 * w.height())
        self.highlight_color = theme_color(theme, 'HighlightRegion', 'bg')
        self.highlight_cursor_line()
    # }}}

    def load_text(self, text, syntax='html', process_template=False):
        self.syntax = syntax
        self.highlighter = get_highlighter(syntax)(self)
        self.highlighter.apply_theme(self.theme)
        self.highlighter.setDocument(self.document())
        sclass = {'html':HTMLSmarts, 'xml':HTMLSmarts}.get(syntax, None)
        if sclass is not None:
            self.smarts = sclass(self)
        self.setPlainText(unicodedata.normalize('NFC', text))
        if process_template and QPlainTextEdit.find(self, '%CURSOR%'):
            c = self.textCursor()
            c.insertText('')

    def replace_text(self, text):
        c = self.textCursor()
        pos = c.position()
        c.beginEditBlock()
        c.clearSelection()
        c.select(c.Document)
        c.insertText(unicodedata.normalize('NFC', text))
        c.endEditBlock()
        c.setPosition(min(pos, len(text)))
        self.setTextCursor(c)
        self.ensureCursorVisible()

    def go_to_line(self, lnum, col=None):
        lnum = max(1, min(self.blockCount(), lnum))
        c = self.textCursor()
        c.clearSelection()
        c.movePosition(c.Start)
        c.movePosition(c.NextBlock, n=lnum - 1)
        c.movePosition(c.StartOfLine)
        c.movePosition(c.EndOfLine, c.KeepAnchor)
        text = unicode(c.selectedText()).rstrip('\0')
        if col is None:
            c.movePosition(c.StartOfLine)
            lt = text.lstrip()
            if text and lt and lt != text:
                c.movePosition(c.NextWord)
        else:
            c.setPosition(c.block().position() + col)
            if c.blockNumber() + 1 > lnum:
                # We have moved past the end of the line
                c.setPosition(c.block().position())
                c.movePosition(c.EndOfBlock)
        self.setTextCursor(c)
        self.ensureCursorVisible()

    def update_extra_selections(self):
        sel = []
        if self.current_cursor_line is not None:
            sel.append(self.current_cursor_line)
        if self.current_search_mark is not None:
            sel.append(self.current_search_mark)
        sel.extend(self.smarts.get_extra_selections(self))
        self.setExtraSelections(sel)

    # Search and replace {{{
    def mark_selected_text(self):
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(self.highlight_color)
        sel.cursor = self.textCursor()
        if sel.cursor.hasSelection():
            self.current_search_mark = sel
            c = self.textCursor()
            c.clearSelection()
            self.setTextCursor(c)
        else:
            self.current_search_mark = None
        self.update_extra_selections()

    def find_in_marked(self, pat, wrap=False, save_match=None):
        if self.current_search_mark is None:
            return False
        csm = self.current_search_mark.cursor
        reverse = pat.flags & regex.REVERSE
        c = self.textCursor()
        c.clearSelection()
        m_start = min(csm.position(), csm.anchor())
        m_end = max(csm.position(), csm.anchor())
        if c.position() < m_start:
            c.setPosition(m_start)
        if c.position() > m_end:
            c.setPosition(m_end)
        pos = m_start if reverse else m_end
        if wrap:
            pos = m_end if reverse else m_start
        c.setPosition(pos, c.KeepAnchor)
        raw = unicode(c.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')
        m = pat.search(raw)
        if m is None:
            return False
        start, end = m.span()
        if start == end:
            return False
        if wrap:
            if reverse:
                textpos = c.anchor()
                start, end = textpos + end, textpos + start
            else:
                start, end = m_start + start, m_start + end
        else:
            if reverse:
                start, end = m_start + end, m_start + start
            else:
                start, end = c.anchor() + start, c.anchor() + end

        c.clearSelection()
        c.setPosition(start)
        c.setPosition(end, c.KeepAnchor)
        self.setTextCursor(c)
        # Center search result on screen
        self.centerCursor()
        if save_match is not None:
            self.saved_matches[save_match] = m
        return True

    def all_in_marked(self, pat, template=None):
        if self.current_search_mark is None:
            return 0
        c = self.current_search_mark.cursor
        raw = unicode(c.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')
        if template is None:
            count = len(pat.findall(raw))
        else:
            raw, count = pat.subn(template, raw)
            if count > 0:
                c.setKeepPositionOnInsert(True)
                c.insertText(raw)
                c.setKeepPositionOnInsert(False)
                self.update_extra_selections()
        return count

    def find(self, pat, wrap=False, marked=False, complete=False, save_match=None):
        if marked:
            return self.find_in_marked(pat, wrap=wrap, save_match=save_match)
        reverse = pat.flags & regex.REVERSE
        c = self.textCursor()
        c.clearSelection()
        if complete:
            # Search the entire text
            c.movePosition(c.End if reverse else c.Start)
        pos = c.Start if reverse else c.End
        if wrap and not complete:
            pos = c.End if reverse else c.Start
        c.movePosition(pos, c.KeepAnchor)
        raw = unicode(c.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')
        m = pat.search(raw)
        if m is None:
            return False
        start, end = m.span()
        if start == end:
            return False
        if wrap and not complete:
            if reverse:
                textpos = c.anchor()
                start, end = textpos + end, textpos + start
        else:
            if reverse:
                # Put the cursor at the start of the match
                start, end = end, start
            else:
                textpos = c.anchor()
                start, end = textpos + start, textpos + end
        c.clearSelection()
        c.setPosition(start)
        c.setPosition(end, c.KeepAnchor)
        self.setTextCursor(c)
        # Center search result on screen
        self.centerCursor()
        if save_match is not None:
            self.saved_matches[save_match] = m
        return True

    def replace(self, pat, template, saved_match='gui'):
        c = self.textCursor()
        raw = unicode(c.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')
        m = pat.fullmatch(raw)
        if m is None:
            # This can happen if either the user changed the selected text or
            # the search expression uses lookahead/lookbehind operators. See if
            # the saved match matches the currently selected text and
            # use it, if so.
            if saved_match is not None and saved_match in self.saved_matches:
                saved = self.saved_matches.pop(saved_match)
                if saved.group() == raw:
                    m = saved
        if m is None:
            return False
        text = m.expand(template)
        c.insertText(text)
        return True

    def go_to_anchor(self, anchor):
        if anchor is TOP:
            c = self.textCursor()
            c.movePosition(c.Start)
            self.setTextCursor(c)
            return True
        base = r'''%%s\s*=\s*['"]{0,1}%s''' % regex.escape(anchor)
        raw = unicode(self.toPlainText())
        m = regex.search(base % 'id', raw)
        if m is None:
            m = regex.search(base % 'name', raw)
        if m is not None:
            c = self.textCursor()
            c.setPosition(m.start())
            self.setTextCursor(c)
            return True
        return False

    # }}}

    # Line numbers and cursor line {{{
    def highlight_cursor_line(self):
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(self.palette().alternateBase())
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.current_cursor_line = sel
        self.update_extra_selections()
        # Update the cursor line's line number in the line number area
        try:
            self.line_number_area.update(0, self.last_current_lnum[0], self.line_number_area.width(), self.last_current_lnum[1])
        except AttributeError:
            pass
        block = self.textCursor().block()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        height = int(self.blockBoundingRect(block).height())
        self.line_number_area.update(0, top, self.line_number_area.width(), height)

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
        QPlainTextEdit.resizeEvent(self, ev)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def paint_line_numbers(self, ev):
        painter = QPainter(self.line_number_area)
        painter.fillRect(ev.rect(), self.line_number_palette.color(QPalette.Base))

        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current = self.textCursor().block().blockNumber()
        painter.setPen(self.line_number_palette.color(QPalette.Text))

        while block.isValid() and top <= ev.rect().bottom():
            if block.isVisible() and bottom >= ev.rect().top():
                if current == num:
                    painter.save()
                    painter.setPen(self.line_number_palette.color(QPalette.BrightText))
                    f = QFont(self.font())
                    f.setBold(True)
                    painter.setFont(f)
                    self.last_current_lnum = (top, bottom - top)
                painter.drawText(0, top, self.line_number_area.width() - 5, self.fontMetrics().height(),
                              Qt.AlignRight, str(num + 1))
                if current == num:
                    painter.restore()
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num += 1
    # }}}

    def event(self, ev):
        if ev.type() == ev.ToolTip:
            self.show_tooltip(ev)
            return True
        if ev.type() == ev.ShortcutOverride:
            if ev in (
                # Let the global cut/copy/paste shortcuts work,this avoids the nbsp
                # problem as well, since they use the overridden copy() method
                # instead of the one from Qt
                QKeySequence.Copy, QKeySequence.Cut, QKeySequence.Paste,
            ) or (
                # This is used to convert typed hex codes into unicode
                # characters
                ev.key() == Qt.Key_X and ev.modifiers() == Qt.AltModifier
            ):
                ev.ignore()
                return False
        return QPlainTextEdit.event(self, ev)

    # Tooltips {{{
    def syntax_format_for_cursor(self, cursor):
        if cursor.isNull():
            return
        pos = cursor.positionInBlock()
        for r in cursor.block().layout().additionalFormats():
            if r.start <= pos < r.start + r.length and r.format.property(SYNTAX_PROPERTY).toBool():
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
    # }}}

    def get_range_inside_tag(self):
        c = self.textCursor()
        left = min(c.anchor(), c.position())
        right = max(c.anchor(), c.position())
        # For speed we use QPlainTextEdit's toPlainText as we dont care about
        # spaces in this context
        raw = unicode(QPlainTextEdit.toPlainText(self))
        # Make sure the left edge is not within a <>
        gtpos = raw.find('>', left)
        ltpos = raw.find('<', left)
        if gtpos < ltpos:
            left = gtpos + 1 if gtpos > -1 else left
        right = max(left, right)
        if right != left:
            gtpos = raw.find('>', right)
            ltpos = raw.find('<', right)
            if ltpos > gtpos:
                ltpos = raw.rfind('<', left, right+1)
                right = max(ltpos, left)
        return left, right

    def format_text(self, formatting):
        if self.syntax != 'html':
            return
        color = 'currentColor'
        if formatting in {'color', 'background-color'}:
            color = QColorDialog.getColor(QColor(Qt.black if formatting == 'color' else Qt.white), self, _('Choose color'), QColorDialog.ShowAlphaChannel)
            if not color.isValid():
                return
            r, g, b, a = color.getRgb()
            if a == 255:
                color = 'rgb(%d, %d, %d)' % (r, g, b)
            else:
                color = 'rgba(%d, %d, %d, %.2g)' % (r, g, b, a/255)
        prefix, suffix = {
            'bold': ('<b>', '</b>'),
            'italic': ('<i>', '</i>'),
            'underline': ('<u>', '</u>'),
            'strikethrough': ('<strike>', '</strike>'),
            'superscript': ('<sup>', '</sup>'),
            'subscript': ('<sub>', '</sub>'),
            'color': ('<span style="color: %s">' % color, '</span>'),
            'background-color': ('<span style="background-color: %s">' % color, '</span>'),
        }[formatting]
        left, right = self.get_range_inside_tag()
        c = self.textCursor()
        c.setPosition(left)
        c.setPosition(right, c.KeepAnchor)
        prev_text = unicode(c.selectedText()).rstrip('\0')
        c.insertText(prefix + prev_text + suffix)
        if prev_text:
            right = c.position()
            c.setPosition(left)
            c.setPosition(right, c.KeepAnchor)
        else:
            c.setPosition(c.position() - len(suffix))
        self.setTextCursor(c)

    def insert_image(self, href):
        c = self.textCursor()
        template, alt = 'url(%s)', ''
        left = min(c.position(), c.anchor)
        if self.syntax == 'html':
            left, right = self.get_range_inside_tag()
            c.setPosition(left)
            c.setPosition(right, c.KeepAnchor)
            alt = _('Image')
            template = '<img alt="{0}" src="%s" />'.format(alt)
            href = prepare_string_for_xml(href, True)
        text = template % href
        c.insertText(text)
        if self.syntax == 'html':
            c.setPosition(left + 10)
            c.setPosition(c.position() + len(alt), c.KeepAnchor)
        else:
            c.setPosition(left)
            c.setPosition(left + len(text), c.KeepAnchor)
        self.setTextCursor(c)

    def insert_hyperlink(self, target):
        if hasattr(self.smarts, 'insert_hyperlink'):
            self.smarts.insert_hyperlink(self, target)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_X and ev.modifiers() == Qt.AltModifier:
            if self.replace_possible_unicode_sequence():
                ev.accept()
                return
        QPlainTextEdit.keyPressEvent(self, ev)
        if (ev.key() == Qt.Key_Semicolon or ';' in unicode(ev.text())) and tprefs['replace_entities_as_typed'] and self.syntax == 'html':
            self.replace_possible_entity()

    def replace_possible_unicode_sequence(self):
        c = self.textCursor()
        has_selection = c.hasSelection()
        if has_selection:
            text = unicode(c.selectedText()).rstrip('\0')
        else:
            c.setPosition(c.position() - min(c.positionInBlock(), 6), c.KeepAnchor)
            text = unicode(c.selectedText()).rstrip('\0')
        m = re.search(r'[a-fA-F0-9]{2,6}$', text)
        if m is None:
            return False
        text = m.group()
        try:
            num = int(text, 16)
        except ValueError:
            return False
        if num > 0x10ffff or num < 1:
            return False
        end_pos = max(c.anchor(), c.position())
        c.setPosition(end_pos - len(text)), c.setPosition(end_pos, c.KeepAnchor)
        c.insertText(safe_chr(num))
        return True

    def replace_possible_entity(self):
        c = self.textCursor()
        c.setPosition(c.position() - min(c.positionInBlock(), 10), c.KeepAnchor)
        text = unicode(c.selectedText()).rstrip('\0')
        m = entity_pat.search(text)
        if m is None:
            return
        ent = m.group()
        repl = xml_entity_to_unicode(m)
        if repl != ent:
            c.setPosition(c.position() + m.start(), c.KeepAnchor)
            c.insertText(repl)

    def select_all(self):
        c = self.textCursor()
        c.clearSelection()
        c.setPosition(0)
        c.movePosition(c.End, c.KeepAnchor)
        self.setTextCursor(c)

    def rename_block_tag(self, new_name):
        if hasattr(self.smarts, 'rename_block_tag'):
            self.smarts.rename_block_tag(self, new_name)

