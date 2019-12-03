#!/usr/bin/env python
# vim:fileencoding=utf-8

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict, deque

from PyQt5.Qt import QTextCursor, QTextBlockUserData, QTextLayout, QTimer

from ..themes import highlight_to_char_format
from calibre.gui2.tweak_book.widgets import BusyCursor
from calibre.utils.icu import utf16_length
from polyglot.builtins import iteritems, unicode_type


def run_loop(user_data, state_map, formats, text):
    state = user_data.state
    i = 0
    fix_offsets = utf16_length(text) != len(text)
    seen_states = defaultdict(set)
    while i < len(text):
        orig_i = i
        seen_states[i].add(state.parse)
        fmt = state_map[state.parse](state, text, i, formats, user_data)
        for num, f in fmt:
            if num > 0:
                if fix_offsets:
                    # We need to map offsets/lengths from UCS-4 to UTF-16 in
                    # which non-BMP characters are two code points wide
                    yield utf16_length(text[:i]), utf16_length(text[i:i+num]), f
                else:
                    yield i, num, f
                i += num
        if orig_i == i and state.parse in seen_states[i]:
            # Something went wrong in the syntax highlighter
            print('Syntax highlighter returned a zero length format, parse state:', state.parse)
            break


class SimpleState(object):

    __slots__ = ('parse',)

    def __init__(self):
        self.parse = 0

    def copy(self):
        s = SimpleState()
        s.parse = self.parse
        return s


class SimpleUserData(QTextBlockUserData):

    def __init__(self):
        QTextBlockUserData.__init__(self)
        self.state = SimpleState()
        self.doc_name = None

    def clear(self, state=None, doc_name=None):
        self.state = SimpleState() if state is None else state
        self.doc_name = doc_name


class SyntaxHighlighter(object):

    create_formats_func = lambda highlighter: {}
    spell_attributes = ()
    tag_ok_for_spell = lambda x: False
    user_data_factory = SimpleUserData

    def __init__(self):
        self.doc = None
        self.doc_name = None
        self.requests = deque()
        self.ignore_requests = False

    @property
    def has_requests(self):
        return bool(self.requests)

    def apply_theme(self, theme):
        self.theme = {k:highlight_to_char_format(v) for k, v in iteritems(theme)}
        self.create_formats()
        self.rehighlight()

    def create_formats(self):
        self.formats = self.create_formats_func()

    def set_document(self, doc, doc_name=None):
        old_doc = self.doc
        if old_doc is not None:
            old_doc.contentsChange.disconnect(self.reformat_blocks)
            c = QTextCursor(old_doc)
            c.beginEditBlock()
            blk = old_doc.begin()
            while blk.isValid():
                blk.layout().clearAdditionalFormats()
                blk = blk.next()
            c.endEditBlock()
        self.doc = self.doc_name = None
        if doc is not None:
            self.doc = doc
            self.doc_name = doc_name
            doc.contentsChange.connect(self.reformat_blocks)
            self.rehighlight()

    def rehighlight(self):
        doc = self.doc
        if doc is None:
            return
        lb = doc.lastBlock()
        with BusyCursor():
            self.reformat_blocks(0, 0, lb.position() + lb.length())

    def get_user_data(self, block):
        ud = block.userData()
        new_data = False
        if ud is None:
            ud = self.user_data_factory()
            block.setUserData(ud)
            new_data = True
        return ud, new_data

    def reformat_blocks(self, position, removed, added):
        doc = self.doc
        if doc is None or self.ignore_requests or not hasattr(self, 'state_map'):
            return

        block = doc.findBlock(position)
        if not block.isValid():
            return
        start_cursor = QTextCursor(block)
        last_block = doc.findBlock(position + added + (1 if removed > 0 else 0))
        if not last_block.isValid():
            last_block = doc.lastBlock()
        end_cursor = QTextCursor(last_block)
        end_cursor.movePosition(end_cursor.EndOfBlock)
        self.requests.append((start_cursor, end_cursor))
        QTimer.singleShot(0, self.do_one_block)

    def do_one_block(self):
        try:
            start_cursor, end_cursor = self.requests[0]
        except IndexError:
            return
        self.ignore_requests = True
        try:
            block = start_cursor.block()
            if not block.isValid():
                self.requests.popleft()
                return
            formats, force_next_highlight = self.parse_single_block(block)
            self.apply_format_changes(block, formats)
            try:
                self.doc.markContentsDirty(block.position(), block.length())
            except AttributeError:
                self.requests.clear()
                return
            ok = start_cursor.movePosition(start_cursor.NextBlock)
            if not ok:
                self.requests.popleft()
                return
            next_block = start_cursor.block()
            if next_block.position() > end_cursor.position():
                if force_next_highlight:
                    end_cursor.setPosition(next_block.position() + 1)
                else:
                    self.requests.popleft()
                return
        finally:
            self.ignore_requests = False
            QTimer.singleShot(0, self.do_one_block)

    def join(self):
        ''' Blocks until all pending highlighting requests are handled '''
        doc = self.doc
        if doc is None:
            self.requests.clear()
            return
        self.ignore_requests = True
        try:
            while self.requests:
                start_cursor, end_cursor = self.requests.popleft()
                block = start_cursor.block()
                last_block = end_cursor.block()
                if not last_block.isValid():
                    last_block = doc.lastBlock()
                end_pos = last_block.position() + last_block.length()
                force_next_highlight = False
                while block.isValid() and (force_next_highlight or block.position() < end_pos):
                    formats, force_next_highlight = self.parse_single_block(block)
                    self.apply_format_changes(block, formats)
                    doc.markContentsDirty(block.position(), block.length())
                    block = block.next()
        finally:
            self.ignore_requests = False

    @property
    def is_working(self):
        return bool(self.requests)

    def parse_single_block(self, block):
        ud, is_new_ud = self.get_user_data(block)
        orig_state = ud.state
        pblock = block.previous()
        if pblock.isValid():
            start_state = pblock.userData()
            if start_state is None:
                start_state = self.user_data_factory().state
            else:
                start_state = start_state.state.copy()
        else:
            start_state = self.user_data_factory().state
        ud.clear(state=start_state, doc_name=self.doc_name)  # Ensure no stale user data lingers
        formats = []
        for i, num, fmt in run_loop(ud, self.state_map, self.formats, unicode_type(block.text())):
            if fmt is not None:
                r = QTextLayout.FormatRange()
                r.start, r.length, r.format = i, num, fmt
                formats.append(r)
        force_next_highlight = is_new_ud or ud.state != orig_state
        return formats, force_next_highlight

    def reformat_block(self, block):
        if block.isValid():
            self.reformat_blocks(block.position(), 0, 1)

    def apply_format_changes(self, block, formats):
        layout = block.layout()
        preedit_start = layout.preeditAreaPosition()
        preedit_length = len(layout.preeditAreaText())
        if preedit_length != 0 and preedit_start != 0:
            for r in formats:
                # Adjust range by pre-edit text, if any
                if r.start >= preedit_start:
                    r.start += preedit_length
                elif r.start + r.length >= preedit_start:
                    r.length += preedit_length
        layout.setAdditionalFormats(formats)
