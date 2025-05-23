#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>


import importlib
import os
import re
import textwrap
import unicodedata
from contextlib import suppress

import regex
from qt.core import (
    QColor,
    QColorDialog,
    QFont,
    QFontDatabase,
    QKeySequence,
    QPainter,
    QPalette,
    QPlainTextEdit,
    QRect,
    QSize,
    Qt,
    QTextCursor,
    QTextEdit,
    QTextFormat,
    QTimer,
    QToolTip,
    QWidget,
    pyqtSignal,
)

from calibre import prepare_string_for_xml
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES, css_text
from calibre.ebooks.oeb.polish.replace import get_recommended_folders
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.gui2.tweak_book import CONTAINER_DND_MIMETYPE, TOP, current_container, tprefs
from calibre.gui2.tweak_book.completion.popup import CompletionPopup
from calibre.gui2.tweak_book.editor import CLASS_ATTRIBUTE_PROPERTY, LINK_PROPERTY, SPELL_LOCALE_PROPERTY, SPELL_PROPERTY, SYNTAX_PROPERTY, store_locale
from calibre.gui2.tweak_book.editor.smarts import NullSmarts
from calibre.gui2.tweak_book.editor.snippets import SnippetManager
from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter
from calibre.gui2.tweak_book.editor.themes import get_theme, theme_color, theme_format
from calibre.gui2.tweak_book.widgets import PARAGRAPH_SEPARATOR, PlainTextEdit
from calibre.spell.break_iterator import index_of
from calibre.utils.icu import capitalize, lower, safe_chr, string_length, swapcase, upper, utf16_length
from calibre.utils.img import image_to_data
from calibre.utils.titlecase import titlecase
from polyglot.builtins import as_unicode


def adjust_for_non_bmp_chars(raw: str, start: int, end: int) -> tuple[int, int]:
    adjusted_start = utf16_length(raw[:start])
    end = adjusted_start + utf16_length(raw[start:end])
    start = adjusted_start
    return start, end


def get_highlighter(syntax):
    if syntax:
        try:
            return importlib.import_module('calibre.gui2.tweak_book.editor.syntax.' + syntax).Highlighter
        except (ImportError, AttributeError):
            pass
    return SyntaxHighlighter


def get_smarts(syntax):
    if syntax:
        smartsname = {'xml':'html'}.get(syntax, syntax)
        try:
            return importlib.import_module('calibre.gui2.tweak_book.editor.smarts.' + smartsname).Smarts
        except (ImportError, AttributeError):
            pass


_dff = None


def default_font_family():
    global _dff
    if _dff is None:
        families = set(map(str, QFontDatabase.families()))
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


class TextEdit(PlainTextEdit):

    link_clicked = pyqtSignal(object)
    class_clicked = pyqtSignal(object)
    smart_highlighting_updated = pyqtSignal()

    def __init__(self, parent=None, expected_geometry=(100, 50)):
        PlainTextEdit.__init__(self, parent)
        self.snippet_manager = SnippetManager(self)
        self.completion_popup = CompletionPopup(self)
        self.request_completion = self.completion_doc_name = None
        self.clear_completion_cache_timer = t = QTimer(self)
        t.setInterval(5000), t.timeout.connect(self.clear_completion_cache), t.setSingleShot(True)
        self.textChanged.connect(t.start)
        self.last_completion_request = -1
        self.gutter_width = 0
        self.tw = 2
        self.expected_geometry = expected_geometry
        self.saved_matches = {}
        self.syntax = None
        self.smarts = NullSmarts(self)
        self.current_cursor_line = None
        self.current_search_mark = None
        self.smarts_highlight_timer = t = QTimer()
        t.setInterval(750), t.setSingleShot(True), t.timeout.connect(self.update_extra_selections)
        self.highlighter = SyntaxHighlighter()
        self.line_number_area = LineNumbers(self)
        self.apply_settings()
        self.setMouseTracking(True)
        self.cursorPositionChanged.connect(self.highlight_cursor_line)
        self.blockCountChanged[int].connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)

    def get_droppable_files(self, md):

        def is_mt_ok(mt):
            return self.syntax == 'html' and (
                mt in OEB_DOCS or mt in OEB_STYLES or mt.startswith('image/')
            )

        if md.hasFormat(CONTAINER_DND_MIMETYPE):
            for line in as_unicode(bytes(md.data(CONTAINER_DND_MIMETYPE))).splitlines():
                mt = current_container().mime_map.get(line, 'application/octet-stream')
                if is_mt_ok(mt):
                    yield line, mt, True
            return
        for qurl in md.urls():
            if qurl.isLocalFile() and os.access(qurl.toLocalFile(), os.R_OK):
                path = qurl.toLocalFile()
                mt = guess_type(path)
                if is_mt_ok(mt):
                    yield path, mt, False

    def canInsertFromMimeData(self, md):
        if md.hasText() or (md.hasHtml() and self.syntax == 'html') or md.hasImage():
            return True
        elif tuple(self.get_droppable_files(md)):
            return True
        return False

    def insertFromMimeData(self, md):
        files = tuple(self.get_droppable_files(md))
        base = self.highlighter.doc_name or None

        def get_name(name):
            folder = get_recommended_folders(current_container(), (name,))[name] or ''
            if folder:
                folder += '/'
            return folder + name

        def get_href(name):
            return current_container().name_to_href(name, base)

        def insert_text(text):
            c = self.textCursor()
            c.insertText(text)
            self.setTextCursor(c)
            self.ensureCursorVisible()

        def add_file(name, data, mt=None):
            from calibre.gui2.tweak_book.boss import get_boss
            name = current_container().add_file(name, data, media_type=mt, modify_name_if_needed=True)
            get_boss().refresh_file_list()
            return name

        if files:
            for path, mt, is_name in files:
                if is_name:
                    name = path
                else:
                    name = get_name(os.path.basename(path))
                    with open(path, 'rb') as f:
                        name = add_file(name, f.read(), mt)
                href = get_href(name)
                if mt.startswith('image/'):
                    self.insert_image(href)
                elif mt in OEB_STYLES:
                    insert_text(f'<link href="{href}" rel="stylesheet" type="text/css"/>')
                elif mt in OEB_DOCS:
                    self.insert_hyperlink(href, name)
            self.ensureCursorVisible()
            return
        if md.hasImage():
            img = md.imageData()
            if img is not None and not img.isNull():
                data = image_to_data(img, fmt='PNG')
                name = add_file(get_name('dropped_image.png'), data)
                self.insert_image(get_href(name))
                self.ensureCursorVisible()
                return
        if md.hasText():
            return insert_text(md.text())
        if md.hasHtml():
            insert_text(md.html())
            return

    @property
    def is_modified(self):
        ''' True if the document has been modified since it was loaded or since
        the last time is_modified was set to False. '''
        return self.document().isModified()

    @is_modified.setter
    def is_modified(self, val):
        self.document().setModified(bool(val))

    def sizeHint(self):
        return self.size_hint

    def apply_line_wrap_mode(self, yes: bool = True) -> None:
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if yes else QPlainTextEdit.LineWrapMode.NoWrap)

    def apply_settings(self, prefs=None, dictionaries_changed=False):  # {{{
        prefs = prefs or tprefs
        self.setAcceptDrops(prefs.get('editor_accepts_drops', True))
        self.apply_line_wrap_mode(prefs['editor_line_wrap'])
        with suppress(Exception):
            self.setCursorWidth(int(prefs.get('editor_cursor_width', 1)))
        theme = get_theme(prefs['editor_theme'])
        self.apply_theme(theme)
        fm = self.fontMetrics()
        self.space_width = fm.horizontalAdvance(' ')
        self.tw = self.smarts.override_tab_stop_width if self.smarts.override_tab_stop_width is not None else prefs['editor_tab_stop_width']
        self.setTabStopDistance(self.tw * self.space_width)
        if dictionaries_changed:
            self.highlighter.rehighlight()

    def apply_theme(self, theme):
        self.theme = theme
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, theme_color(theme, 'Normal', 'bg'))
        pal.setColor(QPalette.ColorRole.AlternateBase, theme_color(theme, 'CursorLine', 'bg'))
        pal.setColor(QPalette.ColorRole.Text, theme_color(theme, 'Normal', 'fg'))
        pal.setColor(QPalette.ColorRole.Highlight, theme_color(theme, 'Visual', 'bg'))
        pal.setColor(QPalette.ColorRole.HighlightedText, theme_color(theme, 'Visual', 'fg'))
        self.setPalette(pal)
        vpal = self.viewport().palette()
        vpal.setColor(QPalette.ColorRole.Base, pal.color(QPalette.ColorRole.Base))
        self.viewport().setPalette(vpal)
        self.tooltip_palette = pal = QPalette()
        pal.setColor(QPalette.ColorRole.ToolTipBase, theme_color(theme, 'Tooltip', 'bg'))
        pal.setColor(QPalette.ColorRole.ToolTipText, theme_color(theme, 'Tooltip', 'fg'))
        self.line_number_palette = pal = QPalette()
        pal.setColor(QPalette.ColorRole.Base, theme_color(theme, 'LineNr', 'bg'))
        pal.setColor(QPalette.ColorRole.Text, theme_color(theme, 'LineNr', 'fg'))
        pal.setColor(QPalette.ColorRole.BrightText, theme_color(theme, 'LineNrC', 'fg'))
        self.match_paren_format = theme_format(theme, 'MatchParen')
        font = self.font()
        ff = tprefs['editor_font_family']
        if ff is None:
            ff = default_font_family()
        font.setFamily(ff)
        font.setPointSizeF(tprefs['editor_font_size'])
        self.tooltip_font = QFont(font)
        self.tooltip_font.setPointSizeF(font.pointSizeF() - 1.)
        self.setFont(font)
        self.highlighter.apply_theme(theme)
        fm = self.fontMetrics()
        self.number_width = max(fm.horizontalAdvance(str(x)) for x in range(10))
        self.size_hint = QSize(self.expected_geometry[0] * fm.averageCharWidth(), self.expected_geometry[1] * fm.height())
        self.highlight_color = theme_color(theme, 'HighlightRegion', 'bg')
        self.highlight_cursor_line()
        self.completion_popup.clear_caches(), self.completion_popup.update()
    # }}}

    def load_text(self, text, syntax='html', process_template=False, doc_name=None):
        self.syntax = syntax
        self.highlighter = get_highlighter(syntax)()
        self.highlighter.apply_theme(self.theme)
        self.highlighter.set_document(self.document(), doc_name=doc_name)
        sclass = get_smarts(syntax)
        if sclass is not None:
            self.smarts = sclass(self)
            if self.smarts.override_tab_stop_width is not None:
                self.tw = self.smarts.override_tab_stop_width
                self.setTabStopDistance(self.tw * self.space_width)
        if isinstance(text, bytes):
            text = text.decode('utf-8', 'replace')
        self.setPlainText(unicodedata.normalize('NFC', str(text)))
        if process_template and QPlainTextEdit.find(self, '%CURSOR%'):
            c = self.textCursor()
            c.insertText('')

    def change_document_name(self, newname):
        self.highlighter.doc_name = newname
        self.highlighter.rehighlight()  # Ensure links are checked w.r.t. the new name correctly

    def replace_text(self, text):
        c = self.textCursor()
        pos = c.position()
        c.beginEditBlock()
        c.clearSelection()
        c.select(QTextCursor.SelectionType.Document)
        c.insertText(unicodedata.normalize('NFC', text))
        c.endEditBlock()
        c.setPosition(min(pos, len(text)))
        self.setTextCursor(c)
        self.ensureCursorVisible()

    def simple_replace(self, text, cursor=None):
        c = cursor or self.textCursor()
        c.insertText(unicodedata.normalize('NFC', text))
        self.setTextCursor(c)

    def go_to_line(self, lnum, col=None):
        lnum = max(1, min(self.blockCount(), lnum))
        c = self.textCursor()
        c.clearSelection()
        c.movePosition(QTextCursor.MoveOperation.Start)
        c.movePosition(QTextCursor.MoveOperation.NextBlock, n=lnum - 1)
        c.movePosition(QTextCursor.MoveOperation.StartOfLine)
        c.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        text = str(c.selectedText()).rstrip('\0')
        if col is None:
            c.movePosition(QTextCursor.MoveOperation.StartOfLine)
            lt = text.lstrip()
            if text and lt and lt != text:
                c.movePosition(QTextCursor.MoveOperation.NextWord)
        else:
            c.setPosition(c.block().position() + col)
            if c.blockNumber() + 1 > lnum:
                # We have moved past the end of the line
                c.setPosition(c.block().position())
                c.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        self.setTextCursor(c)
        self.ensureCursorVisible()

    def update_extra_selections(self, instant=True):
        sel = []
        if self.current_cursor_line is not None:
            sel.extend(self.current_cursor_line)
        if self.current_search_mark is not None:
            sel.append(self.current_search_mark)
        if instant and not self.highlighter.has_requests and self.smarts is not None:
            sel.extend(self.smarts.get_extra_selections(self))
            self.smart_highlighting_updated.emit()
        else:
            self.smarts_highlight_timer.start()
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
        c.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)
        raw = str(c.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')
        m = pat.search(raw)
        if m is None:
            return False
        start, end = m.span()
        if start == end:
            return False
        start, end = adjust_for_non_bmp_chars(raw, start, end)
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
        c.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(c)
        # Center search result on screen
        self.centerCursor()
        if save_match is not None:
            self.saved_matches[save_match] = (pat, m)
        return True

    def all_in_marked(self, pat, template=None):
        if self.current_search_mark is None:
            return 0
        c = self.current_search_mark.cursor
        raw = str(c.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')
        if template is None:
            count = len(pat.findall(raw))
        else:
            from calibre.gui2.tweak_book.function_replace import Function
            repl_is_func = isinstance(template, Function)
            if repl_is_func:
                template.init_env()
            raw, count = pat.subn(template, raw)
            if repl_is_func:
                from calibre.gui2.tweak_book.search import show_function_debug_output
                if getattr(template.func, 'append_final_output_to_marked', False):
                    retval = template.end()
                    if retval:
                        raw += str(retval)
                else:
                    template.end()
                show_function_debug_output(template)
            if count > 0:
                start_pos = min(c.anchor(), c.position())
                c.insertText(raw)
                end_pos = max(c.anchor(), c.position())
                c.setPosition(start_pos), c.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
                self.update_extra_selections()
        return count

    def smart_comment(self):
        from calibre.gui2.tweak_book.editor.comments import smart_comment
        smart_comment(self, self.syntax)

    def sort_css(self):
        from calibre.gui2.dialogs.confirm_delete import confirm
        if confirm(_('Sorting CSS rules can in rare cases change the effective styles applied to the book.'
                     ' Are you sure you want to proceed?'), 'edit-book-confirm-sort-css', parent=self, config_set=tprefs):
            c = self.textCursor()
            c.beginEditBlock()
            c.movePosition(QTextCursor.MoveOperation.Start), c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            text = str(c.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')
            from calibre.ebooks.oeb.polish.css import sort_sheet
            text = css_text(sort_sheet(current_container(), text))
            c.insertText(text)
            c.movePosition(QTextCursor.MoveOperation.Start)
            c.endEditBlock()
            self.setTextCursor(c)

    def find(self, pat, wrap=False, marked=False, complete=False, save_match=None):
        if marked:
            return self.find_in_marked(pat, wrap=wrap, save_match=save_match)
        reverse = pat.flags & regex.REVERSE
        c = self.textCursor()
        c.clearSelection()
        if complete:
            # Search the entire text
            c.movePosition(QTextCursor.MoveOperation.End if reverse else QTextCursor.MoveOperation.Start)
        pos = QTextCursor.MoveOperation.Start if reverse else QTextCursor.MoveOperation.End
        if wrap and not complete:
            pos = QTextCursor.MoveOperation.End if reverse else QTextCursor.MoveOperation.Start
        c.movePosition(pos, QTextCursor.MoveMode.KeepAnchor)
        raw = str(c.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')
        m = pat.search(raw)
        if m is None:
            return False
        start, end = m.span()
        if start == end:
            return False
        start, end = adjust_for_non_bmp_chars(raw, start, end)
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
        c.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(c)
        # Center search result on screen
        self.centerCursor()
        if save_match is not None:
            self.saved_matches[save_match] = (pat, m)
        return True

    def find_text(self, pat, wrap=False, complete=False):
        reverse = pat.flags & regex.REVERSE
        c = self.textCursor()
        c.clearSelection()
        if complete:
            # Search the entire text
            c.movePosition(QTextCursor.MoveOperation.End if reverse else QTextCursor.MoveOperation.Start)
        pos = QTextCursor.MoveOperation.Start if reverse else QTextCursor.MoveOperation.End
        if wrap and not complete:
            pos = QTextCursor.MoveOperation.End if reverse else QTextCursor.MoveOperation.Start
        c.movePosition(pos, QTextCursor.MoveMode.KeepAnchor)
        if hasattr(self.smarts, 'find_text'):
            self.highlighter.join()
            found, start, end = self.smarts.find_text(pat, c, reverse)
            if not found:
                return False
        else:
            raw = str(c.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')
            m = pat.search(raw)
            if m is None:
                return False
            start, end = m.span()
            if start == end:
                return False
            start, end = adjust_for_non_bmp_chars(raw, start, end)
        if reverse:
            start, end = end, start
        c.clearSelection()
        c.setPosition(start)
        c.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(c)
        # Center search result on screen
        self.centerCursor()
        return True

    def find_spell_word(self, original_words, lang, from_cursor=True, center_on_cursor=True):
        c = self.textCursor()
        c.setPosition(c.position())
        if not from_cursor:
            c.movePosition(QTextCursor.MoveOperation.Start)
        c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)

        def find_first_word(haystack):
            match_pos, match_word = -1, None
            for w in original_words:
                idx = index_of(w, haystack, lang=lang)
                if idx > -1 and (match_pos == -1 or match_pos > idx):
                    match_pos, match_word = idx, w
            return match_pos, match_word

        while True:
            text = str(c.selectedText()).rstrip('\0')
            idx, word = find_first_word(text)
            if idx == -1:
                return False
            c.setPosition(c.anchor() + idx)
            c.setPosition(c.position() + string_length(word), QTextCursor.MoveMode.KeepAnchor)
            if self.smarts.verify_for_spellcheck(c, self.highlighter):
                self.highlighter.join()  # Ensure highlighting is finished
                locale = self.spellcheck_locale_for_cursor(c)
                if not lang or not locale or (locale and lang == locale.langcode):
                    self.setTextCursor(c)
                    if center_on_cursor:
                        self.centerCursor()
                    return True
            c.setPosition(c.position())
            c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)

        return False

    def find_next_spell_error(self, from_cursor=True):
        c = self.textCursor()
        if not from_cursor:
            c.movePosition(QTextCursor.MoveOperation.Start)
        block = c.block()
        while block.isValid():
            for r in block.layout().formats():
                if r.format.property(SPELL_PROPERTY):
                    if not from_cursor or block.position() + r.start + r.length > c.position():
                        c.setPosition(block.position() + r.start)
                        c.setPosition(c.position() + r.length, QTextCursor.MoveMode.KeepAnchor)
                        self.setTextCursor(c)
                        return True
            block = block.next()
        return False

    def replace(self, pat, template, saved_match='gui'):
        c = self.textCursor()
        raw = str(c.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')
        m = pat.fullmatch(raw)
        if m is None:
            # This can happen if either the user changed the selected text or
            # the search expression uses lookahead/lookbehind operators. See if
            # the saved match matches the currently selected text and
            # use it, if so.
            if saved_match is not None and saved_match in self.saved_matches:
                saved_pat, saved = self.saved_matches.pop(saved_match)
                if saved_pat == pat and saved.group() == raw:
                    m = saved
        if m is None:
            return False
        if callable(template):
            text = template(m)
        else:
            text = m.expand(template)
        c.insertText(text)
        return True

    def go_to_anchor(self, anchor):
        if anchor is TOP:
            c = self.textCursor()
            c.movePosition(QTextCursor.MoveOperation.Start)
            self.setTextCursor(c)
            return True
        base = rf'''%s\s*=\s*['"]{{0,1}}{regex.escape(anchor)}'''
        raw = str(self.toPlainText())
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
        self._highlight_cursor_line()

    def _highlight_cursor_line(self, highlight_now=True):
        if self.highlighter.is_working:
            QTimer.singleShot(10, self.highlight_cursor_line)
            if not highlight_now:
                return
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(self.palette().alternateBase())
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.current_cursor_line = [sel]

        # apply any formats that have a background over the cursor line format
        # to ensure they are visible
        c = self.textCursor()
        block = c.block()
        c.clearSelection()
        c.select(QTextCursor.SelectionType.LineUnderCursor)
        start = min(c.anchor(), c.position())
        length = max(c.anchor(), c.position()) - start
        for f in self.highlighter.formats_for_line(block, start, length):
            sel = QTextEdit.ExtraSelection()
            c = self.textCursor()
            c.setPosition(f.start + block.position())
            c.setPosition(c.position() + f.length, QTextCursor.MoveMode.KeepAnchor)
            sel.cursor, sel.format = c, f.format
            self.current_cursor_line.append(sel)

        self.update_extra_selections(instant=False)
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
        self.gutter_width = self.line_number_area_width()
        self.setViewportMargins(self.gutter_width, 0, 0, 0)

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
        painter.fillRect(ev.rect(), self.line_number_palette.color(QPalette.ColorRole.Base))

        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current = self.textCursor().block().blockNumber()
        painter.setPen(self.line_number_palette.color(QPalette.ColorRole.Text))

        while block.isValid() and top <= ev.rect().bottom():
            if block.isVisible() and bottom >= ev.rect().top():
                if current == num:
                    painter.save()
                    painter.setPen(self.line_number_palette.color(QPalette.ColorRole.BrightText))
                    f = QFont(self.font())
                    f.setBold(True)
                    painter.setFont(f)
                    self.last_current_lnum = (top, bottom - top)
                painter.drawText(0, top, self.line_number_area.width() - 5, self.fontMetrics().height(),
                              Qt.AlignmentFlag.AlignRight, str(num + 1))
                if current == num:
                    painter.restore()
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num += 1
    # }}}

    def override_shortcut(self, ev):
        # Let the global cut/copy/paste/undo/redo shortcuts work, this avoids the nbsp
        # problem as well, since they use the overridden createMimeDataFromSelection() method
        # instead of the one from Qt (which makes copy() work), and allows proper customization
        # of the shortcuts
        if ev in (
            QKeySequence.StandardKey.Copy, QKeySequence.StandardKey.Cut, QKeySequence.StandardKey.Paste,
            QKeySequence.StandardKey.Undo, QKeySequence.StandardKey.Redo
        ):
            ev.ignore()
            return True
        # This is used to convert typed hex codes into unicode
        # characters
        if ev.key() == Qt.Key.Key_X and ev.modifiers() == Qt.KeyboardModifier.AltModifier:
            ev.accept()
            return True
        return PlainTextEdit.override_shortcut(self, ev)

    def text_for_range(self, block, r):
        c = self.textCursor()
        c.setPosition(block.position() + r.start)
        c.setPosition(c.position() + r.length, QTextCursor.MoveMode.KeepAnchor)
        return self.selected_text_from_cursor(c)

    def spellcheck_locale_for_cursor(self, c):
        with store_locale:
            formats = self.highlighter.parse_single_block(c.block())[0]
        pos = c.positionInBlock()
        for r in formats:
            if r.start <= pos <= r.start + r.length and r.format.property(SPELL_PROPERTY):
                return r.format.property(SPELL_LOCALE_PROPERTY)

    def recheck_word(self, word, locale):
        c = self.textCursor()
        c.movePosition(QTextCursor.MoveOperation.Start)
        block = c.block()
        while block.isValid():
            for r in block.layout().formats():
                if r.format.property(SPELL_PROPERTY) and self.text_for_range(block, r) == word:
                    self.highlighter.reformat_block(block)
                    break
            block = block.next()

    # Tooltips {{{
    def syntax_range_for_cursor(self, cursor):
        if cursor.isNull():
            return
        pos = cursor.positionInBlock()
        for r in cursor.block().layout().formats():
            if r.start <= pos <= r.start + r.length and r.format.property(SYNTAX_PROPERTY):
                return r

    def show_tooltip(self, ev):
        c = self.cursorForPosition(ev.pos())
        fmt_range = self.syntax_range_for_cursor(c)
        fmt = getattr(fmt_range, 'format', None)
        if fmt is not None:
            tt = str(fmt.toolTip())
            if tt:
                QToolTip.setFont(self.tooltip_font)
                QToolTip.setPalette(self.tooltip_palette)
                QToolTip.showText(ev.globalPos(), textwrap.fill(tt))
                return
        QToolTip.hideText()
        ev.ignore()
    # }}}

    def link_for_position(self, pos):
        c = self.cursorForPosition(pos)
        r = self.syntax_range_for_cursor(c)
        if r is not None and r.format.property(LINK_PROPERTY):
            return self.text_for_range(c.block(), r)

    def select_class_name_at_cursor(self, cursor):
        valid = re.compile(r'[\w_0-9\-]+', flags=re.UNICODE)

        def keep_going():
            q = cursor.selectedText()
            m = valid.match(q)
            return m is not None and m.group() == q

        def run_loop(forward=True):
            cursor.setPosition(pos)
            n, p = QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveOperation.PreviousCharacter
            if not forward:
                n, p = p, n
            while True:
                if not cursor.movePosition(n, QTextCursor.MoveMode.KeepAnchor):
                    break
                if not keep_going():
                    cursor.movePosition(p, QTextCursor.MoveMode.KeepAnchor)
                    break
            ans = cursor.position()
            cursor.setPosition(pos)
            return ans

        pos = cursor.position()
        forwards_limit = run_loop()
        backwards_limit = run_loop(forward=False)
        cursor.setPosition(backwards_limit)
        cursor.setPosition(forwards_limit, QTextCursor.MoveMode.KeepAnchor)
        return self.selected_text_from_cursor(cursor)

    def class_for_position(self, pos):
        c = self.cursorForPosition(pos)
        r = self.syntax_range_for_cursor(c)
        if r is not None and r.format.property(CLASS_ATTRIBUTE_PROPERTY):
            class_name = self.select_class_name_at_cursor(c)
            if class_name:
                tags = self.current_tag(for_position_sync=False, cursor=c)
                return {'class': class_name, 'sourceline_address': tags}

    def mousePressEvent(self, ev):
        if self.completion_popup.isVisible() and not self.completion_popup.rect().contains(ev.pos()):
            # For some reason using eventFilter for this does not work, so we
            # implement it here
            self.completion_popup.abort()
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            url = self.link_for_position(ev.pos())
            if url is not None:
                ev.accept()
                self.link_clicked.emit(url)
                return
            class_data = self.class_for_position(ev.pos())
            if class_data is not None:
                ev.accept()
                self.class_clicked.emit(class_data)
                return
        return PlainTextEdit.mousePressEvent(self, ev)

    def get_range_inside_tag(self):
        c = self.textCursor()
        left = min(c.anchor(), c.position())
        right = max(c.anchor(), c.position())
        # For speed we use QPlainTextEdit's toPlainText as we don't care about
        # spaces in this context
        raw = str(QPlainTextEdit.toPlainText(self))
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
        if formatting.startswith('justify_'):
            return self.smarts.set_text_alignment(self, formatting.partition('_')[-1])
        color = 'currentColor'
        if formatting in {'color', 'background-color'}:
            color = QColorDialog.getColor(
                QColor(Qt.GlobalColor.black if formatting == 'color' else Qt.GlobalColor.white),
                self, _('Choose color'), QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if not color.isValid():
                return
            r, g, b, a = color.getRgb()
            if a == 255:
                color = f'rgb({r}, {g}, {b})'
            else:
                color = f'rgba({r}, {g}, {b}, {a / 255:.2g})'
        prefix, suffix = {
            'bold': ('<b>', '</b>'),
            'italic': ('<i>', '</i>'),
            'underline': ('<u>', '</u>'),
            'strikethrough': ('<span style="text-decoration: line-through">', '</span>'),
            'superscript': ('<sup>', '</sup>'),
            'subscript': ('<sub>', '</sub>'),
            'color': (f'<span style="color: {color}">', '</span>'),
            'background-color': (f'<span style="background-color: {color}">', '</span>'),
        }[formatting]
        self.smarts.surround_with_custom_tag(self, prefix, suffix)

    def insert_image(self, href, fullpage=False, preserve_aspect_ratio=False, width=-1, height=-1):
        if width <= 0:
            width = 1200
        if height <= 0:
            height = 1600
        c = self.textCursor()
        template, alt = 'url(%s)', ''
        left = min(c.position(), c.anchor())
        if self.syntax == 'html':
            left, right = self.get_range_inside_tag()
            c.setPosition(left)
            c.setPosition(right, QTextCursor.MoveMode.KeepAnchor)
            href = prepare_string_for_xml(href, True)
            if fullpage:
                template = '''\
<div style="page-break-before:always; page-break-after:always; page-break-inside:avoid">\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" \
version="1.1" width="100%%" height="100%%" viewBox="0 0 {w} {h}" preserveAspectRatio="{a}">\
<image width="{w}" height="{h}" xlink:href="%s"/>\
</svg></div>'''.format(w=width, h=height, a='xMidYMid meet' if preserve_aspect_ratio else 'none')
            else:
                alt = _('Image')
                template = f'<img alt="{alt}" src="%s" />'
        text = template % href
        c.insertText(text)
        if self.syntax == 'html' and not fullpage:
            c.setPosition(left + 10)
            c.setPosition(c.position() + len(alt), QTextCursor.MoveMode.KeepAnchor)
        else:
            c.setPosition(left)
            c.setPosition(left + len(text), QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(c)

    def insert_hyperlink(self, target, text, template=None):
        if hasattr(self.smarts, 'insert_hyperlink'):
            self.smarts.insert_hyperlink(self, target, text, template=template)

    def insert_tag(self, tag):
        if hasattr(self.smarts, 'insert_tag'):
            self.smarts.insert_tag(self, tag)

    def remove_tag(self):
        if hasattr(self.smarts, 'remove_tag'):
            self.smarts.remove_tag(self)

    def split_tag(self):
        if hasattr(self.smarts, 'split_tag'):
            self.smarts.split_tag(self)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_X and ev.modifiers() == Qt.KeyboardModifier.AltModifier:
            if self.replace_possible_unicode_sequence():
                ev.accept()
                return
        if ev.key() == Qt.Key.Key_Insert:
            self.setOverwriteMode(self.overwriteMode() ^ True)
            ev.accept()
            return
        if self.snippet_manager.handle_key_press(ev):
            self.completion_popup.hide()
            return
        if self.smarts.handle_key_press(ev, self):
            self.handle_keypress_completion(ev)
            return
        QPlainTextEdit.keyPressEvent(self, ev)
        self.handle_keypress_completion(ev)

    def handle_keypress_completion(self, ev):
        if self.request_completion is None:
            return
        code = ev.key()
        if code in (
            0, Qt.Key.Key_unknown, Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt,
            Qt.Key.Key_Meta, Qt.Key.Key_AltGr, Qt.Key.Key_CapsLock, Qt.Key.Key_NumLock,
            Qt.Key.Key_ScrollLock, Qt.Key.Key_Up, Qt.Key.Key_Down):
            # We ignore up/down arrow so as to not break scrolling through the
            # text with the arrow keys
            return
        result = self.smarts.get_completion_data(self, ev)
        if result is None:
            self.last_completion_request += 1
        else:
            self.last_completion_request = self.request_completion(*result)
        self.completion_popup.mark_completion(self, None if result is None else result[-1])

    def handle_completion_result(self, result):
        if result.request_id[0] >= self.last_completion_request:
            self.completion_popup.handle_result(result)

    def clear_completion_cache(self):
        if self.request_completion is not None and self.completion_doc_name:
            self.request_completion(None, 'file:' + self.completion_doc_name)

    def replace_possible_unicode_sequence(self):
        c = self.textCursor()
        has_selection = c.hasSelection()
        if has_selection:
            text = str(c.selectedText()).rstrip('\0')
        else:
            c.setPosition(c.position() - min(c.positionInBlock(), 6), QTextCursor.MoveMode.KeepAnchor)
            text = str(c.selectedText()).rstrip('\0')
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
        c.setPosition(end_pos - len(text)), c.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
        c.insertText(safe_chr(num))
        return True

    def select_all(self):
        c = self.textCursor()
        c.clearSelection()
        c.setPosition(0)
        c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(c)

    def rename_block_tag(self, new_name):
        if hasattr(self.smarts, 'rename_block_tag'):
            self.smarts.rename_block_tag(self, new_name)

    def current_tag(self, for_position_sync=True, cursor=None):
        use_matched_tag = False
        if cursor is None:
            use_matched_tag = True
            cursor = self.textCursor()
        return self.smarts.cursor_position_with_sourceline(cursor, for_position_sync=for_position_sync, use_matched_tag=use_matched_tag)

    def goto_sourceline(self, sourceline, tags, attribute=None):
        return self.smarts.goto_sourceline(self, sourceline, tags, attribute=attribute)

    def get_tag_contents(self):
        c = self.smarts.get_inner_HTML(self)
        if c is not None:
            return self.selected_text_from_cursor(c)

    def goto_css_rule(self, rule_address, sourceline_address=None):
        from calibre.gui2.tweak_book.editor.smarts.css import find_rule
        block = None
        if self.syntax == 'css':
            raw = str(self.toPlainText())
            line, col = find_rule(raw, rule_address)
            if line is not None:
                block = self.document().findBlockByNumber(line - 1)
        elif sourceline_address is not None:
            sourceline, tags = sourceline_address
            if self.goto_sourceline(sourceline, tags):
                c = self.textCursor()
                c.setPosition(c.position() + 1)
                self.setTextCursor(c)
                raw = self.get_tag_contents()
                line, col = find_rule(raw, rule_address)
                if line is not None:
                    block = self.document().findBlockByNumber(c.blockNumber() + line - 1)

        if block is not None and block.isValid():
            c = self.textCursor()
            c.setPosition(block.position() + col)
            self.setTextCursor(c)

    def change_case(self, action, cursor=None):
        cursor = cursor or self.textCursor()
        text = self.selected_text_from_cursor(cursor)
        text = {'lower':lower, 'upper':upper, 'capitalize':capitalize, 'title':titlecase, 'swap':swapcase}[action](text)
        cursor.insertText(text)
        self.setTextCursor(cursor)
