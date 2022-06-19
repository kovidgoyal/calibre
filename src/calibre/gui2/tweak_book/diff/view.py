#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

import re
import regex
import unicodedata
from collections import OrderedDict, namedtuple
from difflib import SequenceMatcher
from functools import partial
from itertools import chain
from math import ceil
from qt.core import (
    QApplication, QBrush, QColor, QEvent, QEventLoop, QFont, QHBoxLayout,
    QIcon, QImage, QKeySequence, QMenu, QPainter, QPainterPath, QPalette, QPen,
    QPixmap, QPlainTextEdit, QRect, QScrollBar, QSplitter, QSplitterHandle, Qt,
    QTextCharFormat, QTextCursor, QTextLayout, QTimer, QWidget, pyqtSignal
)

from calibre import fit_image, human_readable
from calibre.gui2 import info_dialog
from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.diff import get_sequence_matcher
from calibre.gui2.tweak_book.diff.highlight import get_highlighter
from calibre.gui2.tweak_book.editor.text import (
    LineNumbers, PlainTextEdit, default_font_family
)
from calibre.gui2.tweak_book.editor.themes import get_theme, theme_color
from calibre.gui2.widgets import BusyCursor
from calibre.utils.icu import utf16_length
from calibre.utils.xml_parse import safe_xml_fromstring
from polyglot.builtins import as_bytes, iteritems

Change = namedtuple('Change', 'ltop lbot rtop rbot kind')


def beautify_text(raw, syntax):
    from lxml import etree

    from calibre.ebooks.chardet import strip_encoding_declarations
    from calibre.ebooks.oeb.polish.parsing import parse
    from calibre.ebooks.oeb.polish.pretty import pretty_html_tree, pretty_xml_tree
    if syntax == 'xml':
        try:
            root = safe_xml_fromstring(strip_encoding_declarations(raw))
        except etree.XMLSyntaxError:
            return raw
        pretty_xml_tree(root)
    elif syntax == 'css':
        import logging
        from css_parser import CSSParser, log

        from calibre.ebooks.oeb.base import _css_logger, serialize
        from calibre.ebooks.oeb.polish.utils import setup_css_parser_serialization
        setup_css_parser_serialization(tprefs['editor_tab_stop_width'])
        log.setLevel(logging.WARN)
        log.raiseExceptions = False
        parser = CSSParser(loglevel=logging.WARNING,
                           # We dont care about @import rules
                           fetcher=lambda x: (None, None), log=_css_logger)
        data = parser.parseString(raw, href='<string>', validate=False)
        return serialize(data, 'text/css').decode('utf-8')
    else:
        root = parse(raw, line_numbers=False)
        pretty_html_tree(None, root)
    return etree.tostring(root, encoding='unicode')


class LineNumberMap(dict):  # {{{

    'Map line numbers and keep track of the maximum width of the line numbers'

    def __new__(cls):
        self = dict.__new__(cls)
        self.max_width = 1
        return self

    def __setitem__(self, k, v):
        v = str(v)
        dict.__setitem__(self, k, v)
        self.max_width = max(self.max_width, len(v))

    def clear(self):
        dict.clear(self)
        self.max_width = 1
# }}}


class TextBrowser(PlainTextEdit):  # {{{

    resized = pyqtSignal()
    wheel_event = pyqtSignal(object)
    next_change = pyqtSignal(object)
    scrolled = pyqtSignal()
    line_activated = pyqtSignal(object, object, object)

    def __init__(self, right=False, parent=None, show_open_in_editor=False):
        PlainTextEdit.__init__(self, parent)
        self.setFrameStyle(0)
        self.show_open_in_editor = show_open_in_editor
        self.side_margin = 0
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.right = right
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        font = self.font()
        ff = tprefs['editor_font_family']
        if ff is None:
            ff = default_font_family()
        font.setFamily(ff)
        font.setPointSizeF(tprefs['editor_font_size'])
        self.setFont(font)
        self.calculate_metrics()
        self.setTabStopDistance(tprefs['editor_tab_stop_width'] * self.space_width)
        font = self.heading_font = QFont(self.font())
        font.setPointSizeF(tprefs['editor_font_size'] * 1.5)
        font.setBold(True)
        theme = get_theme(tprefs['editor_theme'])
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, theme_color(theme, 'Normal', 'bg'))
        pal.setColor(QPalette.ColorRole.AlternateBase, theme_color(theme, 'CursorLine', 'bg'))
        pal.setColor(QPalette.ColorRole.Text, theme_color(theme, 'Normal', 'fg'))
        pal.setColor(QPalette.ColorRole.Highlight, theme_color(theme, 'Visual', 'bg'))
        pal.setColor(QPalette.ColorRole.HighlightedText, theme_color(theme, 'Visual', 'fg'))
        self.setPalette(pal)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.line_number_area = LineNumbers(self)
        self.blockCountChanged[int].connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.line_number_palette = pal = QPalette()
        pal.setColor(QPalette.ColorRole.Base, theme_color(theme, 'LineNr', 'bg'))
        pal.setColor(QPalette.ColorRole.Text, theme_color(theme, 'LineNr', 'fg'))
        pal.setColor(QPalette.ColorRole.BrightText, theme_color(theme, 'LineNrC', 'fg'))
        self.line_number_map = LineNumberMap()
        self.search_header_pos = 0
        self.changes, self.headers, self.images = [], [], OrderedDict()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff), self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.diff_backgrounds = {
            'replace' : theme_color(theme, 'DiffReplace', 'bg'),
            'insert'  : theme_color(theme, 'DiffInsert', 'bg'),
            'delete'  : theme_color(theme, 'DiffDelete', 'bg'),
            'replacereplace': theme_color(theme, 'DiffReplaceReplace', 'bg'),
            'boundary': QBrush(theme_color(theme, 'Normal', 'fg'), Qt.BrushStyle.Dense7Pattern),
        }
        self.diff_foregrounds = {
            'replace' : theme_color(theme, 'DiffReplace', 'fg'),
            'insert'  : theme_color(theme, 'DiffInsert', 'fg'),
            'delete'  : theme_color(theme, 'DiffDelete', 'fg'),
            'boundary': QColor(0, 0, 0, 0),
        }
        for x in ('replacereplace', 'insert', 'delete'):
            f = QTextCharFormat()
            f.setBackground(self.diff_backgrounds[x])
            setattr(self, '%s_format' % x, f)

    def calculate_metrics(self):
        fm = self.fontMetrics()
        self.number_width = max(map(lambda x:fm.horizontalAdvance(str(x)), range(10)))
        self.space_width = fm.horizontalAdvance(' ')

    def show_context_menu(self, pos):
        m = QMenu(self)
        a = m.addAction
        i = str(self.textCursor().selectedText()).rstrip('\0')
        if i:
            a(QIcon.ic('edit-copy.png'), _('Copy to clipboard'), self.copy).setShortcut(QKeySequence.StandardKey.Copy)

        if len(self.changes) > 0:
            a(QIcon.ic('arrow-up.png'), _('Previous change'), partial(self.next_change.emit, -1))
            a(QIcon.ic('arrow-down.png'), _('Next change'), partial(self.next_change.emit, 1))

        if self.show_open_in_editor:
            b = self.cursorForPosition(pos).block()
            if b.isValid():
                a(QIcon.ic('tweak.png'), _('Open file in the editor'), partial(self.generate_sync_request, b.blockNumber()))

        if len(m.actions()) > 0:
            m.exec(self.mapToGlobal(pos))

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == 1:
            b = self.cursorForPosition(ev.pos()).block()
            if b.isValid():
                self.generate_sync_request(b.blockNumber())
        return PlainTextEdit.mouseDoubleClickEvent(self, ev)

    def generate_sync_request(self, block_number):
        if not self.headers:
            return
        try:
            lnum = int(self.line_number_map.get(block_number, ''))
        except:
            lnum = 1
        for i, (num, text) in enumerate(self.headers):
            if num > block_number:
                name = text if i == 0 else self.headers[i - 1][1]
                break
        else:
            name = self.headers[-1][1]
        self.line_activated.emit(name, lnum, bool(self.right))

    def search(self, query, reverse=False):
        ''' Search for query, also searching the headers. Matches in headers
        are not highlighted as managing the highlight is too much of a pain.'''
        if not query.strip():
            return
        c = self.textCursor()
        lnum = c.block().blockNumber()
        cpos = c.positionInBlock()
        headers = dict(self.headers)
        if lnum in headers:
            cpos = self.search_header_pos
        lines = str(self.toPlainText()).splitlines()
        for hn, text in self.headers:
            lines[hn] = text
        prefix, postfix = lines[lnum][:cpos], lines[lnum][cpos:]
        before, after = enumerate(lines[0:lnum]), ((lnum+1+i, x) for i, x in enumerate(lines[lnum+1:]))
        if reverse:
            sl = chain([(lnum, prefix)], reversed(tuple(before)), reversed(tuple(after)), [(lnum, postfix)])
        else:
            sl = chain([(lnum, postfix)], after, before, [(lnum, prefix)])
        flags = regex.REVERSE if reverse else 0
        pat = regex.compile(regex.escape(query, special_only=True), flags=regex.UNICODE|regex.IGNORECASE|flags)
        for num, text in sl:
            try:
                m = next(pat.finditer(text))
            except StopIteration:
                continue
            start, end = m.span()
            length = end - start
            if text is postfix:
                start += cpos
            c = QTextCursor(self.document().findBlockByNumber(num))
            c.setPosition(c.position() + start)
            if num in headers:
                self.search_header_pos = start + length
            else:
                c.setPosition(c.position() + length, QTextCursor.MoveMode.KeepAnchor)
                self.search_header_pos = 0
            if reverse:
                pos, anchor = c.position(), c.anchor()
                c.setPosition(pos), c.setPosition(anchor, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(c)
            self.centerCursor()
            self.scrolled.emit()
            break
        else:
            info_dialog(self, _('No matches found'), _(
                'No matches found for query: %s' % query), show=True)

    def clear(self):
        PlainTextEdit.clear(self)
        self.line_number_map.clear()
        del self.changes[:]
        del self.headers[:]
        self.images.clear()
        self.search_header_pos = 0
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def update_line_number_area_width(self, block_count=0):
        self.side_margin = self.line_number_area_width()
        if self.right:
            self.setViewportMargins(0, 0, self.side_margin, 0)
        else:
            self.setViewportMargins(self.side_margin, 0, 0, 0)

    def available_width(self):
        return self.width() - self.side_margin

    def line_number_area_width(self):
        return 9 + (self.line_number_map.max_width * self.number_width)

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
        self.resized.emit()

    def paint_line_numbers(self, ev):
        painter = QPainter(self.line_number_area)
        painter.fillRect(ev.rect(), self.line_number_palette.color(QPalette.ColorRole.Base))

        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        painter.setPen(self.line_number_palette.color(QPalette.ColorRole.Text))
        change_starts = {x[0] for x in self.changes}

        while block.isValid() and top <= ev.rect().bottom():
            r = ev.rect()
            if block.isVisible() and bottom >= r.top():
                text = str(self.line_number_map.get(num, ''))
                is_start = text != '-' and num in change_starts
                if is_start:
                    painter.save()
                    f = QFont(self.font())
                    f.setBold(True)
                    painter.setFont(f)
                    painter.setPen(self.line_number_palette.color(QPalette.ColorRole.BrightText))
                if text == '-':
                    painter.drawLine(r.left() + 2, (top + bottom)//2, r.right() - 2, (top + bottom)//2)
                else:
                    if self.right:
                        painter.drawText(r.left() + 3, top, r.right(), self.fontMetrics().height(),
                                Qt.AlignmentFlag.AlignLeft, text)
                    else:
                        painter.drawText(r.left() + 2, top, r.right() - 5, self.fontMetrics().height(),
                                Qt.AlignmentFlag.AlignRight, text)
                if is_start:
                    painter.restore()
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num += 1

    def paintEvent(self, event):
        w = self.viewport().rect().width()
        painter = QPainter(self.viewport())
        painter.setClipRect(event.rect())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        floor = event.rect().bottom()
        ceiling = event.rect().top()
        fv = self.firstVisibleBlock().blockNumber()
        origin = self.contentOffset()
        doc = self.document()
        lines = []

        for num, text in self.headers:
            top, bot = num, num + 3
            if bot < fv:
                continue
            y_top = self.blockBoundingGeometry(doc.findBlockByNumber(top)).translated(origin).y()
            y_bot = self.blockBoundingGeometry(doc.findBlockByNumber(bot)).translated(origin).y()
            if max(y_top, y_bot) < ceiling:
                continue
            if min(y_top, y_bot) > floor:
                break
            painter.setFont(self.heading_font)
            br = painter.drawText(3, int(y_top), int(w), int(y_bot - y_top - 5), Qt.TextFlag.TextSingleLine, text)
            painter.setPen(QPen(self.palette().text(), 2))
            painter.drawLine(0, int(br.bottom()+3), w, int(br.bottom()+3))

        for top, bot, kind in self.changes:
            if bot < fv:
                continue
            y_top = self.blockBoundingGeometry(doc.findBlockByNumber(top)).translated(origin).y()
            y_bot = self.blockBoundingGeometry(doc.findBlockByNumber(bot)).translated(origin).y()
            if max(y_top, y_bot) < ceiling:
                continue
            if min(y_top, y_bot) > floor:
                break
            if y_top != y_bot:
                painter.fillRect(0,  int(y_top), int(w), int(y_bot - y_top), self.diff_backgrounds[kind])
            lines.append((y_top, y_bot, kind))
            if top in self.images:
                img, maxw = self.images[top][:2]
                if bot > top + 1 and not img.isNull():
                    y_top = self.blockBoundingGeometry(doc.findBlockByNumber(top+1)).translated(origin).y() + 3
                    y_bot -= 3
                    scaled, imgw, imgh = fit_image(int(img.width()/img.devicePixelRatio()), int(img.height()/img.devicePixelRatio()), w - 3, y_bot - y_top)
                    painter.drawPixmap(QRect(3, int(y_top), int(imgw), int(imgh)), img)

        painter.end()
        PlainTextEdit.paintEvent(self, event)
        painter = QPainter(self.viewport())
        painter.setClipRect(event.rect())
        for top, bottom, kind in sorted(lines, key=lambda t_b_k:{'replace':0}.get(t_b_k[2], 1)):
            painter.setPen(QPen(self.diff_foregrounds[kind], 1))
            painter.drawLine(0, int(top), int(w), int(top))
            painter.drawLine(0, int(bottom - 1), int(w), int(bottom - 1))

    def wheelEvent(self, ev):
        if ev.angleDelta().x() == 0:
            self.wheel_event.emit(ev)
        else:
            return PlainTextEdit.wheelEvent(self, ev)

# }}}


class DiffSplitHandle(QSplitterHandle):  # {{{

    WIDTH = 30  # px
    wheel_event = pyqtSignal(object)

    def event(self, ev):
        if ev.type() in (QEvent.Type.HoverEnter, QEvent.Type.HoverLeave):
            self.hover = ev.type() == QEvent.Type.HoverEnter
        return QSplitterHandle.event(self, ev)

    def paintEvent(self, event):
        QSplitterHandle.paintEvent(self, event)
        left, right = self.parent().left, self.parent().right
        painter = QPainter(self)
        painter.setClipRect(event.rect())
        w = self.width()
        h = self.height()
        painter.setRenderHints(QPainter.RenderHint.Antialiasing, True)

        C = 16  # Curve factor.

        def create_line(ly, ry, right_to_left=False):
            ' Create path that represents upper or lower line of change marker '
            line = QPainterPath()
            if not right_to_left:
                line.moveTo(0, ly)
                line.cubicTo(C, ly, w - C, ry, w, ry)
            else:
                line.moveTo(w, ry)
                line.cubicTo(w - C, ry, C, ly, 0, ly)
            return line

        ldoc, rdoc = left.document(), right.document()
        lorigin, rorigin = left.contentOffset(), right.contentOffset()
        lfv, rfv = left.firstVisibleBlock().blockNumber(), right.firstVisibleBlock().blockNumber()
        lines = []

        for (ltop, lbot, kind), (rtop, rbot, kind) in zip(left.changes, right.changes):
            if lbot < lfv and rbot < rfv:
                continue
            ly_top = left.blockBoundingGeometry(ldoc.findBlockByNumber(ltop)).translated(lorigin).y()
            ly_bot = left.blockBoundingGeometry(ldoc.findBlockByNumber(lbot)).translated(lorigin).y()
            ry_top = right.blockBoundingGeometry(rdoc.findBlockByNumber(rtop)).translated(rorigin).y()
            ry_bot = right.blockBoundingGeometry(rdoc.findBlockByNumber(rbot)).translated(rorigin).y()
            if max(ly_top, ly_bot, ry_top, ry_bot) < 0:
                continue
            if min(ly_top, ly_bot, ry_top, ry_bot) > h:
                break

            upper_line = create_line(ly_top, ry_top)
            lower_line = create_line(ly_bot, ry_bot, True)

            region = QPainterPath()
            region.moveTo(0, ly_top)
            region.connectPath(upper_line)
            region.lineTo(w, ry_bot)
            region.connectPath(lower_line)
            region.closeSubpath()

            painter.fillPath(region, left.diff_backgrounds[kind])
            for path, aa in zip((upper_line, lower_line), (ly_top != ry_top, ly_bot != ry_bot)):
                lines.append((kind, path, aa))

        for kind, path, aa in sorted(lines, key=lambda x:{'replace':0}.get(x[0], 1)):
            painter.setPen(left.diff_foregrounds[kind])
            painter.setRenderHints(QPainter.RenderHint.Antialiasing, aa)
            painter.drawPath(path)

        painter.setFont(left.heading_font)
        for (lnum, text), (rnum, text) in zip(left.headers, right.headers):
            ltop, lbot, rtop, rbot = lnum, lnum + 3, rnum, rnum + 3
            if lbot < lfv and rbot < rfv:
                continue
            ly_top = left.blockBoundingGeometry(ldoc.findBlockByNumber(ltop)).translated(lorigin).y()
            ly_bot = left.blockBoundingGeometry(ldoc.findBlockByNumber(lbot)).translated(lorigin).y()
            ry_top = right.blockBoundingGeometry(rdoc.findBlockByNumber(rtop)).translated(rorigin).y()
            ry_bot = right.blockBoundingGeometry(rdoc.findBlockByNumber(rbot)).translated(rorigin).y()
            if max(ly_top, ly_bot, ry_top, ry_bot) < 0:
                continue
            if min(ly_top, ly_bot, ry_top, ry_bot) > h:
                break
            ly = painter.boundingRect(3, int(ly_top), int(left.width()), int(ly_bot - ly_top - 5), Qt.TextFlag.TextSingleLine, text).bottom() + 3
            ry = painter.boundingRect(3, int(ry_top), int(right.width()), int(ry_bot - ry_top - 5), Qt.TextFlag.TextSingleLine, text).bottom() + 3
            line = create_line(ly, ry)
            painter.setPen(QPen(left.palette().text(), 2))
            painter.setRenderHints(QPainter.RenderHint.Antialiasing, ly != ry)
            painter.drawPath(line)

        painter.end()
        # Paint the splitter without the change lines if the mouse is over the
        # splitter
        if getattr(self, 'hover', False):
            QSplitterHandle.paintEvent(self, event)

    def sizeHint(self):
        ans = QSplitterHandle.sizeHint(self)
        ans.setWidth(self.WIDTH)
        return ans

    def wheelEvent(self, ev):
        if ev.angleDelta().x() == 0:
            self.wheel_event.emit(ev)
        else:
            return QSplitterHandle.wheelEvent(self, ev)
# }}}


class DiffSplit(QSplitter):  # {{{

    def __init__(self, parent=None, show_open_in_editor=False):
        QSplitter.__init__(self, parent)
        self._failed_img = None

        self.left, self.right = TextBrowser(parent=self), TextBrowser(right=True, parent=self, show_open_in_editor=show_open_in_editor)
        self.addWidget(self.left), self.addWidget(self.right)
        self.split_words = re.compile(r"\w+|\W", re.UNICODE)
        self.clear()

    def createHandle(self):
        return DiffSplitHandle(self.orientation(), self)

    def clear(self):
        self.left.clear(), self.right.clear()

    def finalize(self):
        for v in (self.left, self.right):
            c = v.textCursor()
            c.movePosition(QTextCursor.MoveOperation.Start)
            v.setTextCursor(c)
        self.update()

    def add_diff(self, left_name, right_name, left_text, right_text, context=None, syntax=None, beautify=False):
        left_text, right_text = left_text or '', right_text or ''
        is_identical = len(left_text) == len(right_text) and left_text == right_text and left_name == right_name
        is_text = isinstance(left_text, str) and isinstance(right_text, str)
        left_name = left_name or '[%s]'%_('This file was added')
        right_name = right_name or '[%s]'%_('This file was removed')
        self.left.headers.append((self.left.blockCount() - 1, left_name))
        self.right.headers.append((self.right.blockCount() - 1, right_name))
        for v in (self.left, self.right):
            c = v.textCursor()
            c.movePosition(QTextCursor.MoveOperation.End)
            (c.insertBlock(), c.insertBlock(), c.insertBlock())

        with BusyCursor():
            if is_identical:
                for v in (self.left, self.right):
                    c = v.textCursor()
                    c.movePosition(QTextCursor.MoveOperation.End)
                    c.insertText('[%s]\n\n' % _('The files are identical'))
            elif left_name != right_name and not left_text and not right_text:
                self.add_text_diff(_('[This file was renamed to %s]') % right_name, _('[This file was renamed from %s]') % left_name, context, None)
                for v in (self.left, self.right):
                    v.appendPlainText('\n')
            elif is_text:
                self.add_text_diff(left_text, right_text, context, syntax, beautify=beautify)
            elif syntax == 'raster_image':
                self.add_image_diff(left_text, right_text)
            else:
                text = '[%s]' % _('Binary file of size: %s')
                left_text, right_text = text % human_readable(len(left_text)), text % human_readable(len(right_text))
                self.add_text_diff(left_text, right_text, None, None)
                for v in (self.left, self.right):
                    v.appendPlainText('\n')

    # image diffs {{{
    @property
    def failed_img(self):
        if self._failed_img is None:
            try:
                dpr = self.devicePixelRatioF()
            except AttributeError:
                dpr = self.devicePixelRatio()
            i = QImage(200, 150, QImage.Format.Format_ARGB32)
            i.setDevicePixelRatio(dpr)
            i.fill(Qt.GlobalColor.white)
            p = QPainter(i)
            r = i.rect().adjusted(10, 10, -10, -10)
            n = QPen(Qt.PenStyle.DashLine)
            n.setColor(Qt.GlobalColor.black)
            p.setPen(n)
            p.drawRect(r)
            p.setPen(Qt.GlobalColor.black)
            f = self.font()
            f.setPixelSize(20)
            p.setFont(f)
            p.drawText(r.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, _('Image could not be rendered'))
            p.end()
            self._failed_img = QPixmap.fromImage(i)
        return self._failed_img

    def add_image_diff(self, left_data, right_data):
        def load(data):
            p = QPixmap()
            p.loadFromData(as_bytes(data))
            try:
                dpr = self.devicePixelRatioF()
            except AttributeError:
                dpr = self.devicePixelRatio()
            p.setDevicePixelRatio(dpr)
            if data and p.isNull():
                p = self.failed_img
            return p
        left_img, right_img = load(left_data), load(right_data)
        change = []
        # Let any initial resizing of the window finish in case this is the
        # first diff, to avoid the expensive resize calculation later
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents | QEventLoop.ProcessEventsFlag.ExcludeSocketNotifiers)
        for v, img, size in ((self.left, left_img, len(left_data)), (self.right, right_img, len(right_data))):
            c = v.textCursor()
            c.movePosition(QTextCursor.MoveOperation.End)
            start = c.block().blockNumber()
            lines, w = self.get_lines_for_image(img, v)
            c.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            if size > 0:
                c.beginEditBlock()
                c.insertText(_('Size: {0} Resolution: {1}x{2}').format(human_readable(size), img.width(), img.height()))
                for i in range(lines + 1):
                    c.insertBlock()
            change.extend((start, c.block().blockNumber()))
            c.insertBlock()
            c.endEditBlock()
            v.images[start] = (img, w, lines)
        change.append('replace' if left_data and right_data else 'delete' if left_data else 'insert')
        self.left.changes.append((change[0], change[1], change[-1]))
        self.right.changes.append((change[2], change[3], change[-1]))
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents | QEventLoop.ProcessEventsFlag.ExcludeSocketNotifiers)

    def resized(self):
        ' Resize images to fit in new view size and adjust all line number references accordingly '
        for v in (self.left, self.right):
            changes = []
            for i, (top, bot, kind) in enumerate(v.changes):
                if top in v.images:
                    img, oldw, oldlines = v.images[top]
                    lines, w = self.get_lines_for_image(img, v)
                    if lines != oldlines:
                        changes.append((i, lines, lines - oldlines, img, w))

            for i, lines, delta, img, w in changes:
                top, bot, kind = v.changes[i]
                c = QTextCursor(v.document().findBlockByNumber(top+1))
                c.beginEditBlock()
                c.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                if delta > 0:
                    for _ in range(delta):
                        c.insertBlock()
                else:
                    c.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.KeepAnchor, -delta)
                    c.removeSelectedText()
                c.endEditBlock()
                v.images[top] = (img, w, lines)

                def mapnum(x):
                    return x if x <= top else x + delta
                lnm = LineNumberMap()
                lnm.max_width = v.line_number_map.max_width
                for x, val in iteritems(v.line_number_map):
                    dict.__setitem__(lnm, mapnum(x), val)
                v.line_number_map = lnm
                v.changes = [(mapnum(t), mapnum(b), k) for t, b, k in v.changes]
                v.headers = [(mapnum(x), name) for x, name in v.headers]
                v.images = OrderedDict((mapnum(x), v) for x, v in iteritems(v.images))
            v.viewport().update()

    def get_lines_for_image(self, img, view):
        if img.isNull():
            return 0, 0
        w, h = int(img.width()/img.devicePixelRatio()), int(img.height()/img.devicePixelRatio())
        scaled, w, h = fit_image(w, h, view.available_width() - 3, int(0.9 * view.height()))
        line_height = view.blockBoundingRect(view.document().begin()).height()
        return int(ceil(h / line_height)) + 1, w
    # }}}

    # text diffs {{{
    def add_text_diff(self, left_text, right_text, context, syntax, beautify=False):
        left_text = unicodedata.normalize('NFC', left_text)
        right_text = unicodedata.normalize('NFC', right_text)
        if beautify and syntax in {'xml', 'html', 'css'}:
            left_text, right_text = beautify_text(left_text, syntax), beautify_text(right_text, syntax)
            if len(left_text) == len(right_text) and left_text == right_text:
                for v in (self.left, self.right):
                    c = v.textCursor()
                    c.movePosition(QTextCursor.MoveOperation.End)
                    c.insertText('[%s]\n\n' % _('The files are identical after beautifying'))
                return

        left_lines = self.left_lines = left_text.splitlines()
        right_lines = self.right_lines = right_text.splitlines()

        cruncher = get_sequence_matcher()(None, left_lines, right_lines)

        left_highlight, right_highlight = get_highlighter(self.left, left_text, syntax), get_highlighter(self.right, right_text, syntax)
        cl, cr = self.left_cursor, self.right_cursor = self.left.textCursor(), self.right.textCursor()
        cl.beginEditBlock(), cr.beginEditBlock()
        cl.movePosition(QTextCursor.MoveOperation.End), cr.movePosition(QTextCursor.MoveOperation.End)
        self.left_insert = partial(self.do_insert, cl, left_highlight, self.left.line_number_map)
        self.right_insert = partial(self.do_insert, cr, right_highlight, self.right.line_number_map)

        self.changes = []

        if context is None:
            for tag, alo, ahi, blo, bhi in cruncher.get_opcodes():
                getattr(self, tag)(alo, ahi, blo, bhi)
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents | QEventLoop.ProcessEventsFlag.ExcludeSocketNotifiers)
        else:
            def insert_boundary():
                self.changes.append(Change(
                    ltop=cl.block().blockNumber()-1, lbot=cl.block().blockNumber(),
                    rtop=cr.block().blockNumber()-1, rbot=cr.block().blockNumber(), kind='boundary'))
                self.left.line_number_map[self.changes[-1].ltop] = '-'
                self.right.line_number_map[self.changes[-1].rtop] = '-'

            ahi = bhi = 0
            for i, group in enumerate(cruncher.get_grouped_opcodes(context)):
                for j, (tag, alo, ahi, blo, bhi) in enumerate(group):
                    if j == 0 and (i > 0 or min(alo, blo) > 0):
                        insert_boundary()
                    getattr(self, tag)(alo, ahi, blo, bhi)
                    QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents | QEventLoop.ProcessEventsFlag.ExcludeSocketNotifiers)
                cl.insertBlock(), cr.insertBlock()
            if ahi < len(left_lines) - 1 or bhi < len(right_lines) - 1:
                insert_boundary()

        cl.endEditBlock(), cr.endEditBlock()
        del self.left_lines
        del self.right_lines
        del self.left_insert
        del self.right_insert

        self.coalesce_changes()

        for ltop, lbot, rtop, rbot, kind in self.changes:
            if kind != 'equal':
                self.left.changes.append((ltop, lbot, kind))
                self.right.changes.append((rtop, rbot, kind))

        del self.changes

    def coalesce_changes(self):
        'Merge neighboring changes of the same kind, if any'
        changes = []
        for x in self.changes:
            if changes and changes[-1].kind == x.kind:
                changes[-1] = changes[-1]._replace(lbot=x.lbot, rbot=x.rbot)
            else:
                changes.append(x)
        self.changes = changes

    def do_insert(self, cursor, highlighter, line_number_map, lo, hi):
        start_block = cursor.block()
        highlighter.copy_lines(lo, hi, cursor)
        for num, i in enumerate(range(start_block.blockNumber(), cursor.blockNumber())):
            line_number_map[i] = lo + num + 1
        return start_block.blockNumber(), cursor.block().blockNumber()

    def equal(self, alo, ahi, blo, bhi):
        lsb, lcb = self.left_insert(alo, ahi)
        rsb, rcb = self.right_insert(blo, bhi)
        self.changes.append(Change(
            rtop=rsb, rbot=rcb, ltop=lsb, lbot=lcb, kind='equal'))

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

    def trim_identical_leading_lines(self, alo, ahi, blo, bhi):
        ''' The patience diff algorithm sometimes results in a block of replace
        lines with identical leading lines. Remove these. This can cause extra
        lines of context, but that is better than having extra lines of diff
        with no actual changes. '''
        a, b = self.left_lines, self.right_lines
        leading = 0
        while alo < ahi and blo < bhi and a[alo] == b[blo]:
            leading += 1
            alo += 1
            blo += 1
        if leading > 0:
            self.equal(alo - leading, alo, blo - leading, blo)
        return alo, ahi, blo, bhi

    def replace(self, alo, ahi, blo, bhi):
        ''' When replacing one block of lines with another, search the blocks
        for *similar* lines; the best-matching pair (if any) is used as a synch
        point, and intraline difference marking is done on the similar pair.
        Lots of work, but often worth it.  '''
        alo, ahi, blo, bhi = self.trim_identical_leading_lines(alo, ahi, blo, bhi)
        if alo == ahi and blo == bhi:
            return
        if ahi + bhi - alo - blo > 100:
            # Too many lines, this will be too slow
            # http://bugs.python.org/issue6931
            return self.do_replace(alo, ahi, blo, bhi)
        # don't synch up unless the lines have a similarity score of at
        # least cutoff; best_ratio tracks the best score seen so far
        best_ratio, cutoff = 0.74, 0.75
        cruncher = SequenceMatcher()
        eqi, eqj = None, None   # 1st indices of equal lines (if any)
        a, b = self.left_lines, self.right_lines

        # search for the pair that matches best without being identical
        # (identical lines must be junk lines, & we don't want to synch up
        # on junk -- unless we have to)
        for j in range(blo, bhi):
            bj = b[j]
            cruncher.set_seq2(bj)
            for i in range(alo, ahi):
                ai = a[i]
                if ai == bj:
                    if eqi is None:
                        eqi, eqj = i, j
                    continue
                cruncher.set_seq1(ai)
                # computing similarity is expensive, so use the quick
                # upper bounds first -- have seen this speed up messy
                # compares by a factor of 3.
                # note that ratio() is only expensive to compute the first
                # time it's called on a sequence pair; the expensive part
                # of the computation is cached by cruncher
                if (cruncher.real_quick_ratio() > best_ratio and
                        cruncher.quick_ratio() > best_ratio and
                        cruncher.ratio() > best_ratio):
                    best_ratio, best_i, best_j = cruncher.ratio(), i, j
        if best_ratio < cutoff:
            # no non-identical "pretty close" pair
            if eqi is None:
                # no identical pair either -- treat it as a straight replace
                self.do_replace(alo, ahi, blo, bhi)
                return
            # no close pair, but an identical pair -- synch up on that
            best_i, best_j, best_ratio = eqi, eqj, 1.0
        else:
            # there's a close pair, so forget the identical pair (if any)
            eqi = None

        # a[best_i] very similar to b[best_j]; eqi is None iff they're not
        # identical

        # pump out diffs from before the synch point
        self.replace_helper(alo, best_i, blo, best_j)

        # do intraline marking on the synch pair
        if eqi is None:
            self.do_replace(best_i, best_i+1, best_j, best_j+1)
        else:
            # the synch pair is identical
            self.equal(best_i, best_i+1, best_j, best_j+1)

        # pump out diffs from after the synch point
        self.replace_helper(best_i+1, ahi, best_j+1, bhi)

    def replace_helper(self, alo, ahi, blo, bhi):
        if alo < ahi:
            if blo < bhi:
                self.replace(alo, ahi, blo, bhi)
            else:
                self.delete(alo, ahi, blo, blo)
        elif blo < bhi:
            self.insert(alo, alo, blo, bhi)

    def do_replace(self, alo, ahi, blo, bhi):
        lsb, lcb = self.left_insert(alo, ahi)
        rsb, rcb = self.right_insert(blo, bhi)
        self.changes.append(Change(
            rtop=rsb, rbot=rcb, ltop=lsb, lbot=lcb, kind='replace'))

        l, r = '\n'.join(self.left_lines[alo:ahi]), '\n'.join(self.right_lines[blo:bhi])
        ll, rl = self.split_words.findall(l), self.split_words.findall(r)
        cruncher = get_sequence_matcher()(None, ll, rl)
        lsb, rsb = self.left.document().findBlockByNumber(lsb), self.right.document().findBlockByNumber(rsb)

        def do_tag(block, words, lo, hi, pos, fmts):
            for word in words[lo:hi]:
                if word == '\n':
                    if fmts:
                        block.layout().setFormats(fmts)
                    pos, block, fmts = 0, block.next(), []
                    continue

                if tag in {'replace', 'insert', 'delete'}:
                    fmt = getattr(self.left, '%s_format' % ('replacereplace' if tag == 'replace' else tag))
                    f = QTextLayout.FormatRange()
                    f.start, f.length, f.format = pos, len(word), fmt
                    fmts.append(f)
                pos += utf16_length(word)
            return block, pos, fmts

        lfmts, rfmts, lpos, rpos = [], [], 0, 0
        for tag, llo, lhi, rlo, rhi in cruncher.get_opcodes():
            lsb, lpos, lfmts = do_tag(lsb, ll, llo, lhi, lpos, lfmts)
            rsb, rpos, rfmts = do_tag(rsb, rl, rlo, rhi, rpos, rfmts)
        for block, fmts in ((lsb, lfmts), (rsb, rfmts)):
            if fmts:
                block.layout().setFormats(fmts)
    # }}}

# }}}


class DiffView(QWidget):  # {{{

    SYNC_POSITION = 0.4
    line_activated = pyqtSignal(object, object, object)

    def __init__(self, parent=None, show_open_in_editor=False):
        QWidget.__init__(self, parent)
        self.changes = [[], [], []]
        self.delta = 0
        self.l = l = QHBoxLayout(self)
        self.setLayout(l)
        self.syncpos = 0
        l.setContentsMargins(0, 0, 0, 0), l.setSpacing(0)
        self.view = DiffSplit(self, show_open_in_editor=show_open_in_editor)
        l.addWidget(self.view)
        self.add_diff = self.view.add_diff
        self.scrollbar = QScrollBar(self)
        l.addWidget(self.scrollbar)
        self.syncing = False
        self.bars = []
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.resize_debounced)
        for bar in (self.scrollbar, self.view.left.verticalScrollBar(), self.view.right.verticalScrollBar()):
            self.bars.append(bar)
            bar.scroll_idx = len(self.bars) - 1
            connect_lambda(bar.valueChanged[int], self, lambda self: self.scrolled(self.sender().scroll_idx))
        self.view.left.resized.connect(self.resized)
        for v in (self.view.left, self.view.right, self.view.handle(1)):
            v.wheel_event.connect(self.scrollbar.wheelEvent)
            if v is self.view.left or v is self.view.right:
                v.next_change.connect(self.next_change)
                v.line_activated.connect(self.line_activated)
                connect_lambda(v.scrolled, self,
                        lambda self: self.scrolled(1 if self.sender() is self.view.left else 2))

    def next_change(self, delta):
        assert delta in (1, -1)
        position = self.get_position_from_scrollbar(0)
        if position[0] == 'in':
            p = n = position[1]
        else:
            p, n = position[1], position[1] + 1
            if p < 0:
                p = None
            if n >= len(self.changes[0]):
                n = None
        if p == n:
            nc = p + delta
            if nc < 0 or nc >= len(self.changes[0]):
                nc = None
        else:
            nc = {1:n, -1:p}[delta]
        if nc is None:
            self.scrollbar.setValue(0 if delta == -1 else self.scrollbar.maximum())
        else:
            val = self.scrollbar.value()
            self.scroll_to(0, ('in', nc, 0))
            nval = self.scrollbar.value()
            if nval == val:
                nval += 5 * delta
                if 0 <= nval <= self.scrollbar.maximum():
                    self.scrollbar.setValue(nval)

    def resized(self):
        self.resize_timer.start(300)

    def resize_debounced(self):
        self.view.resized()
        self.calculate_length()
        self.adjust_range()
        self.view.handle(1).update()

    def get_position_from_scrollbar(self, which):
        changes = self.changes[which]
        bar = self.bars[which]
        syncpos = self.syncpos + bar.value()
        prev = 0
        for i, (top, bot, kind) in enumerate(changes):
            if syncpos <= bot:
                if top <= syncpos:
                    # syncpos is inside a change
                    try:
                        ratio = float(syncpos - top) / (bot - top)
                    except ZeroDivisionError:
                        ratio = 0
                    return 'in', i, ratio
                else:
                    # syncpos is after the previous change
                    offset = syncpos - prev
                    return 'after', i - 1, offset
            else:
                # syncpos is after the current change
                prev = bot
        offset = syncpos - prev
        return 'after', len(changes) - 1, offset

    def scroll_to(self, which, position):
        changes = self.changes[which]
        bar = self.bars[which]
        val = None
        if position[0] == 'in':
            change_idx, ratio = position[1:]
            start, end = changes[change_idx][:2]
            val = start + int((end - start) * ratio)
        else:
            change_idx, offset = position[1:]
            start = 0 if change_idx < 0 else changes[change_idx][1]
            val = start + offset
        bar.setValue(val - self.syncpos)

    def scrolled(self, which, *args):
        if self.syncing:
            return
        position = self.get_position_from_scrollbar(which)
        with self:
            for x in {0, 1, 2} - {which}:
                self.scroll_to(x, position)
        self.view.handle(1).update()

    def __enter__(self):
        self.syncing = True

    def __exit__(self, *args):
        self.syncing = False

    def clear(self):
        with self:
            self.view.clear()
            self.changes = [[], [], []]
            self.delta = 0
            self.scrollbar.setRange(0, 0)

    def adjust_range(self):
        ls, rs = self.view.left.verticalScrollBar(), self.view.right.verticalScrollBar()
        self.scrollbar.setPageStep(min(ls.pageStep(), rs.pageStep()))
        self.scrollbar.setSingleStep(min(ls.singleStep(), rs.singleStep()))
        self.scrollbar.setRange(0, ls.maximum() + self.delta)
        self.scrollbar.setVisible(self.view.left.document().lineCount() > ls.pageStep() or self.view.right.document().lineCount() > rs.pageStep())
        self.syncpos = int(ceil(self.scrollbar.pageStep() * self.SYNC_POSITION))

    def finalize(self):
        self.view.finalize()
        self.changes = [[], [], []]
        self.calculate_length()
        self.adjust_range()

    def calculate_length(self):
        delta = 0
        line_number_changes = ([], [])
        for v, lmap, changes in zip((self.view.left, self.view.right), ({}, {}), line_number_changes):
            b = v.document().firstBlock()
            ebl = v.document().documentLayout().ensureBlockLayout
            last_line_count = 0
            while b.isValid():
                ebl(b)
                lmap[b.blockNumber()] = last_line_count
                last_line_count += b.layout().lineCount()
                b = b.next()
            for top, bot, kind in v.changes:
                changes.append((lmap[top], lmap[bot], kind))

        changes = []
        for (l_top, l_bot, kind), (r_top, r_bot, kind) in zip(*line_number_changes):
            height = max(l_bot - l_top, r_bot - r_top)
            top = delta + l_top
            changes.append((top, top + height, kind))
            delta = top + height - l_bot
        self.changes, self.delta = (changes,) + line_number_changes, delta

    def handle_key(self, ev):
        amount, d = None, 1
        key = ev.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_J, Qt.Key.Key_K):
            amount = self.scrollbar.singleStep()
            if key in (Qt.Key.Key_Up, Qt.Key.Key_K):
                d = -1
        elif key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            amount = self.scrollbar.pageStep()
            if key in (Qt.Key.Key_PageUp,):
                d = -1
        elif key in (Qt.Key.Key_Home, Qt.Key.Key_End):
            self.scrollbar.setValue(0 if key == Qt.Key.Key_Home else self.scrollbar.maximum())
            return True
        elif key in (Qt.Key.Key_N, Qt.Key.Key_P):
            self.next_change(1 if key == Qt.Key.Key_N else -1)
            return True

        if amount is not None:
            self.scrollbar.setValue(self.scrollbar.value() + d * amount)
            return True
        return False
# }}}
