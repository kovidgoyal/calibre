#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap
from math import ceil

from PyQt5.Qt import (
    QWidget, Qt, QStaticText, QTextOption, QSize, QPainter, QTimer, QPalette)

from calibre import prints, prepare_string_for_xml
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book.widgets import make_highlighted_text
from calibre.utils.icu import string_length
from polyglot.builtins import iteritems


class ChoosePopupWidget(QWidget):

    TOP_MARGIN = BOTTOM_MARGIN = 2
    SIDE_MARGIN = 4

    def __init__(self, parent, max_height=1000):
        QWidget.__init__(self, parent)

        self.setFocusPolicy(Qt.NoFocus)
        self.setFocusProxy(parent)
        self.setVisible(False)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        self.current_results = self.current_size_hint = None

        self.max_text_length = 0
        self.current_index = -1
        self.current_top_index = 0
        self.max_height = max_height

        self.text_option = to = QTextOption()
        to.setWrapMode(QTextOption.NoWrap)
        to.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.rendered_text_cache = {}
        parent.installEventFilter(self)
        self.relayout_timer = t = QTimer(self)
        t.setSingleShot(True), t.setInterval(25), t.timeout.connect(self.layout)

    def clear_caches(self):
        self.rendered_text_cache.clear()
        self.current_size_hint = None

    def set_items(self, items, descriptions=None):
        self.current_results = items
        self.current_size_hint = None
        self.descriptions = descriptions or {}
        self.clear_caches()
        self.max_text_length = 0
        self.current_index = -1
        self.current_top_index = 0
        if self.current_results:
            self.max_text_length = max(string_length(text) for text, pos in self.current_results)

    def get_static_text(self, otext, positions):
        st = self.rendered_text_cache.get(otext)
        if st is None:
            text = (otext or '').ljust(self.max_text_length + 1, '\xa0')
            text = make_highlighted_text('color: magenta', text, positions)
            desc = self.descriptions.get(otext)
            if desc:
                text += ' - <i>%s</i>' % prepare_string_for_xml(desc)
            color = self.palette().color(QPalette.Text).name()
            text = '<span style="color: %s">%s</span>' % (color, text)
            st = self.rendered_text_cache[otext] = QStaticText(text)
            st.setTextOption(self.text_option)
            st.setTextFormat(Qt.RichText)
            st.prepare(font=self.parent().font())
        return st

    def sizeHint(self):
        if self.current_size_hint is None:
            max_width = height = 0
            for text, positions in self.current_results:
                sz = self.get_static_text(text, positions).size()
                height += int(ceil(sz.height())) + self.BOTTOM_MARGIN
                max_width = max(max_width, int(ceil(sz.width())))
            self.current_size_hint = QSize(max_width + 2 * self.SIDE_MARGIN, height + self.BOTTOM_MARGIN + self.TOP_MARGIN)
        return self.current_size_hint

    def iter_visible_items(self):
        y = self.TOP_MARGIN
        bottom = self.rect().bottom()
        for i, (text, positions) in enumerate(self.current_results[self.current_top_index:]):
            st = self.get_static_text(text, positions)
            height = self.BOTTOM_MARGIN + int(ceil(st.size().height()))
            if y + height > bottom:
                break
            yield i + self.current_top_index, st, y, height
            y += height

    def index_for_y(self, y):
        for idx, st, top, height in self.iter_visible_items():
            if top <= y < top + height:
                return idx

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setClipRect(ev.rect())
        pal = self.palette()
        painter.fillRect(self.rect(), pal.color(pal.Text))
        crect = self.rect().adjusted(1, 1, -1, -1)
        painter.fillRect(crect, pal.color(pal.Base))
        painter.setClipRect(crect)
        painter.setFont(self.parent().font())
        width = self.rect().width()
        for i, st, y, height in self.iter_visible_items():
            painter.save()
            if i == self.current_index:
                painter.fillRect(1, y, width, height, pal.color(pal.Highlight))
                color = pal.color(QPalette.HighlightedText).name()
                st = QStaticText(st)
                text = st.text().partition('>')[2]
                st.setText('<span style="color: %s">%s' % (color, text))
            painter.drawStaticText(self.SIDE_MARGIN, y, st)
            painter.restore()
        painter.end()
        if self.current_size_hint is None:
            QTimer.singleShot(0, self.layout)

    def layout(self, cursor_rect=None):
        p = self.parent()
        if cursor_rect is None:
            cursor_rect = p.cursorRect().adjusted(0, 0, 0, 2)
        gutter_width = p.gutter_width
        vp = p.viewport()
        above = cursor_rect.top() > vp.height() - cursor_rect.bottom()
        max_height = min(self.max_height, (cursor_rect.top() if above else vp.height() - cursor_rect.bottom()) - 15)
        max_width = vp.width() - 25 - gutter_width
        sz = self.sizeHint()
        height = min(max_height, sz.height())
        width = min(max_width, sz.width())
        left = cursor_rect.left() + gutter_width
        extra = max_width - (width + left)
        if extra < 0:
            left += extra
        top = (cursor_rect.top() - height) if above else cursor_rect.bottom()
        self.resize(width, height)
        self.move(left, top)
        self.update()

    def ensure_index_visible(self, index):
        if index < self.current_top_index:
            self.current_top_index = max(0, index)
        else:
            try:
                i = tuple(self.iter_visible_items())[-1][0]
            except IndexError:
                return
            if i < index:
                self.current_top_index += index - i

    def show(self):
        if self.current_results:
            self.layout()
            QWidget.show(self)
            self.raise_()

    def hide(self):
        QWidget.hide(self)
        self.relayout_timer.stop()
    abort = hide

    def activate_current_result(self):
        raise NotImplementedError('You must implement this method in a subclass')

    def handle_keypress(self, ev):
        key = ev.key()
        if key == Qt.Key_Escape:
            self.abort(), ev.accept()
            return True
        if key == Qt.Key_Tab and not ev.modifiers() & Qt.CTRL:
            self.choose_next_result(previous=ev.modifiers() & Qt.ShiftModifier)
            ev.accept()
            return True
        if key == Qt.Key_Backtab and not ev.modifiers() & Qt.CTRL:
            self.choose_next_result(previous=ev.modifiers() & Qt.ShiftModifier)
            return True
        if key in (Qt.Key_Up, Qt.Key_Down):
            self.choose_next_result(previous=key == Qt.Key_Up)
            return True
        return False

    def eventFilter(self, obj, ev):
        if obj is self.parent() and self.isVisible():
            etype = ev.type()
            if etype == ev.KeyPress:
                ret = self.handle_keypress(ev)
                if ret:
                    ev.accept()
                return ret
            elif etype == ev.Resize:
                self.relayout_timer.start()
        return False

    def mouseMoveEvent(self, ev):
        y = ev.pos().y()
        idx = self.index_for_y(y)
        if idx is not None and idx != self.current_index:
            self.current_index = idx
            self.update()
            ev.accept()

    def mouseReleaseEvent(self, ev):
        y = ev.pos().y()
        idx = self.index_for_y(y)
        if idx is not None:
            self.activate_current_result()
            self.hide()
        ev.accept()

    def choose_next_result(self, previous=False):
        if self.current_results:
            if previous:
                if self.current_index == -1:
                    self.current_index = len(self.current_results) - 1
                else:
                    self.current_index -= 1
            else:
                if self.current_index == len(self.current_results) - 1:
                    self.current_index = -1
                else:
                    self.current_index += 1
            self.ensure_index_visible(self.current_index)
            self.update()


class CompletionPopup(ChoosePopupWidget):

    def __init__(self, parent, max_height=1000):
        ChoosePopupWidget.__init__(self, parent, max_height=max_height)
        self.completion_error_shown = False

        self.current_query = self.current_completion = None

    def set_items(self, items, descriptions=None, query=None):
        self.current_query = query
        ChoosePopupWidget.set_items(self, tuple(iteritems(items)), descriptions=descriptions)

    def choose_next_result(self, previous=False):
        ChoosePopupWidget.choose_next_result(self, previous=previous)
        self.activate_current_result()

    def activate_current_result(self):
        if self.current_completion is not None:
            c = self.current_completion
            text = self.current_query if self.current_index == -1 else self.current_results[self.current_index][0]
            c.insertText(text)
            chars = string_length(text)
            c.setPosition(c.position() - chars)
            c.setPosition(c.position() + chars, c.KeepAnchor)

    def abort(self):
        ChoosePopupWidget.abort(self)
        self.current_completion = self.current_query = None

    def mark_completion(self, editor, query):
        self.current_completion = c = editor.textCursor()
        chars = string_length(query or '')
        c.setPosition(c.position() - chars), c.setPosition(c.position() + chars, c.KeepAnchor)
        self.hide()

    def handle_result(self, result):
        if result.traceback:
            prints(result.traceback)
            if not self.completion_error_shown:
                error_dialog(self, _('Completion failed'), _(
                    'Failed to get completions, click "Show Details" for more information.'
                    ' Future errors during completion will be suppressed.'), det_msg=result.traceback, show=True)
                self.completion_error_shown = True
            self.hide()
            return
        if result.ans is None:
            self.hide()
            return
        items, descriptions = result.ans
        if not items:
            self.hide()
            return
        self.set_items(items, descriptions, result.query)
        self.show()


if __name__ == '__main__':
    from calibre.utils.matcher import Matcher

    def test(editor):
        c = editor.__c = CompletionPopup(editor.editor, max_height=100)
        items = 'a ab abc abcd abcde abcdef abcdefg abcdefgh'.split()
        m = Matcher(items)
        c.set_items(m('a'), descriptions={x:x for x in items})
        QTimer.singleShot(100, c.show)
    from calibre.gui2.tweak_book.editor.widget import launch_editor
    raw = textwrap.dedent('''\
    Is the same as saying through shrinking from toil and pain. These
    cases are perfectly simple and easy to distinguish. In a free hour, when
    our power of choice is untrammelled and when nothing prevents our being
    able to do what we like best, every pleasure is to be welcomed and every
    pain avoided.

    But in certain circumstances and owing to the claims of duty or the obligations
    of business it will frequently occur that pleasures have to be repudiated and
    annoyances accepted. The wise man therefore always holds in these matters to
    this principle of selection: he rejects pleasures to secure.
    ''')
    launch_editor(raw, path_is_raw=True, callback=test)
