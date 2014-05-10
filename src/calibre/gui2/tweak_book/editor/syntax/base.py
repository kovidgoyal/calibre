#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict

from PyQt4.Qt import (
    QTextCursor, pyqtSlot, QTextBlockUserData, QTextLayout)

from ..themes import highlight_to_char_format
from calibre.gui2.tweak_book.widgets import BusyCursor

def run_loop(user_data, state_map, formats, text):
    state = user_data.state
    i = 0
    seen_states = defaultdict(set)
    while i < len(text):
        orig_i = i
        seen_states[i].add(state.parse)
        fmt = state_map[state.parse](state, text, i, formats, user_data)
        for num, f in fmt:
            if num > 0:
                yield i, num, f
                i += num
        if orig_i == i and state.parse in seen_states[i]:
            # Something went wrong in the syntax highlighter
            print ('Syntax highlighter returned a zero length format, parse state:', state.parse)
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

    def clear(self, state=None):
        self.state = SimpleState() if state is None else state

class SyntaxHighlighter(object):

    create_formats_func = lambda highlighter: {}
    spell_attributes = ()
    tag_ok_for_spell = lambda x: False
    user_data_factory = SimpleUserData

    def __init__(self):
        self.doc = None

    def apply_theme(self, theme):
        self.theme = {k:highlight_to_char_format(v) for k, v in theme.iteritems()}
        self.create_formats()
        self.rehighlight()

    def create_formats(self):
        self.formats = self.create_formats_func()

    def set_document(self, doc):
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
        self.doc = None
        if doc is not None:
            self.doc = doc
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

    @pyqtSlot(int, int, int)
    def reformat_blocks(self, position, removed, added):
        doc = self.doc
        if doc is None or not hasattr(self, 'state_map'):
            return
        last_block = doc.findBlock(position + added + (1 if removed > 0 else 0))
        if not last_block.isValid():
            last_block = doc.lastBlock()
        end_pos = last_block.position() + last_block.length()
        force_next_highlight = False

        doc.contentsChange.disconnect(self.reformat_blocks)
        try:
            block = doc.findBlock(position)
            while block.isValid() and (block.position() < end_pos or force_next_highlight):
                ud, new_ud = self.get_user_data(block)
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
                ud.clear(state=start_state)  # Ensure no stale user data lingers
                formats = []
                for i, num, fmt in run_loop(ud, self.state_map, self.formats, unicode(block.text())):
                    if fmt is not None:
                        formats.append((i, num, fmt))
                self.apply_format_changes(doc, block, formats)
                force_next_highlight = new_ud or ud.state != orig_state
                block = block.next()
        finally:
            doc.contentsChange.connect(self.reformat_blocks)

    def apply_format_changes(self, doc, block, formats):
        layout = block.layout()
        preedit_start = layout.preeditAreaPosition()
        preedit_length = layout.preeditAreaText().length()
        ranges = []
        R = QTextLayout.FormatRange
        for i, num, fmt in formats:
            # Adjust range by pre-edit text, if any
            if preedit_start != 0:
                if i >= preedit_start:
                    i += preedit_length
                elif i + num >= preedit_start:
                    num += preedit_length
            r = R()
            r.start, r.length, r.format = i, num, fmt
            ranges.append(r)
        layout.setAdditionalFormats(ranges)
        doc.markContentsDirty(block.position(), block.length())

