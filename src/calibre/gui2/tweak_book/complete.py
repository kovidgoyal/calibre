#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from math import ceil

from PyQt5.Qt import (
    QWidget, Qt, QStaticText, QTextOption, QSize, QPainter, QTimer)

from calibre.gui2.tweak_book.widgets import make_highlighted_text
from calibre.utils.icu import string_length
from calibre.utils.matcher import Matcher


class CompletionPopup(QWidget):

    TOP_MARGIN = BOTTOM_MARGIN = 2

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFocusProxy(parent)
        self.setVisible(False)

        self.matcher = None
        self.current_query = self.current_results = self.current_size_hint = None
        self.max_text_length = 0

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

    def set_items(self, items, items_are_filenames=False):
        kw = {}
        if not items_are_filenames:
            kw['level1'] = ' '
        self.matcher = Matcher(tuple(items), **kw)
        self.descriptions = dict(items) if isinstance(items, dict) else {}
        self.clear_caches()
        self.set_query()

    def set_query(self, query=''):
        self.current_size_hint = None
        self.current_query = query
        if self.matcher is None:
            self.current_results = ()
        else:
            if query:
                self.current_results = tuple(self.matcher(query).iteritems())
            else:
                self.current_results = tuple((text, ()) for text in self.matcher.items)
        self.max_text_length = 0
        if self.current_results:
            self.max_text_length = max(string_length(text) for text, pos in self.current_results)

    def get_static_text(self, otext, positions):
        st = self.rendered_text_cache.get(otext)
        if st is None:
            text = (otext or '').ljust(self.max_text_length + 1, ' ')
            text = make_highlighted_text('color: magenta', text, positions)
            desc = self.descriptions.get(otext)
            if desc:
                text += ' ' + desc
            st = self.rendered_text_cache[otext] = QStaticText(text)
            st.setTextOption(self.text_option)
            st.setTextFormat(Qt.RichText)
            st.prepare(font=self.parent().font())
        return st

    def sizeHint(self):
        if self.current_size_hint is None:
            max_width = 0
            height = 0
            for text, positions in self.current_results:
                sz = self.get_static_text(text, positions).size()
                height += int(ceil(sz.height())) + self.TOP_MARGIN + self.BOTTOM_MARGIN
                max_width = max(max_width, int(ceil(sz.width())))
            self.current_size_hint = QSize(max_width, height)
        return self.current_size_hint

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setClipRect(ev.rect())
        painter.setFont(self.parent().font())
        y = self.TOP_MARGIN
        top, bottom = ev.rect().top(), ev.rect().bottom()
        for text, positions in self.current_results:
            st = self.get_static_text(text, positions)
            height = self.BOTTOM_MARGIN + int(ceil(st.size().height()))
            if y + height < top:
                continue
            if y + height > bottom:
                break
            painter.drawStaticText(0, y, st)
            y += height
        painter.end()
        if self.current_size_hint is None:
            QTimer.singleShot(0, self.layout)

    def layout(self, cursor_rect=None):
        p = self.parent()
        if cursor_rect is None:
            cursor_rect = p.cursorRect()
        gutter_width = p.gutter_width
        vp = p.viewport()
        above = cursor_rect.top() > vp.height() - cursor_rect.bottom()
        max_height = (cursor_rect.top() if above else vp.height() - cursor_rect.bottom()) - 15
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

    def show(self):
        if self.current_results:
            self.layout()
            QWidget.show(self)
            self.raise_()

    def hide(self):
        QWidget.hide(self)
        self.relayout_timer.stop()

    def eventFilter(self, obj, ev):
        if obj is self.parent() and self.isVisible():
            if ev.type() == ev.Resize:
                self.relayout_timer.start()
        return False

if __name__ == '__main__':
    def test(editor):
        c = editor.__c = CompletionPopup(editor.editor)
        c.set_items('one two three four five'.split())
        QTimer.singleShot(10, c.show)
    from calibre.gui2.tweak_book.editor.widget import launch_editor
    launch_editor('''<p>Something something</p>''', path_is_raw=True, callback=test)
