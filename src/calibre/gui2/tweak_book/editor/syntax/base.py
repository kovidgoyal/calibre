#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any, Protocol, cast

from qt.core import QTextBlock, QTextBlockUserData, QTextCharFormat, QTextCursor, QTextDocument, QTextFormat, QTextLayout, QTimer

from calibre.gui2.tweak_book.editor.themes import highlight_to_char_format
from calibre.gui2.widgets import BusyCursor
from calibre.utils.icu import utf16_length

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence

    from calibre.gui2.tweak_book.editor.themes import Theme

    # The formats used by the state functions of a highlighter. In addition to
    # QTextCharFormat objects, highlighters also store helpers such as the
    # formats for embedded CSS or color preview format factories in them, so
    # the values are heterogeneous and are looked up by dynamic keys.
    Formats = dict[str, Any]
    # A sequence of (length, format) pairs produced by a state function
    FormatSpans = Sequence[tuple[int, QTextCharFormat | None]]
    StateFunction = Callable[..., FormatSpans]

    class ParseState(Protocol):
        parse: int

        def copy(self) -> ParseState: ...

    class UserData(Protocol):
        doc_name: str | None

        @property
        def state(self) -> ParseState: ...

        clear: Callable[..., None]


def run_loop(user_data: UserData, state_map: Mapping[int, StateFunction], formats: object, text: str) -> Iterator[tuple[int, int, QTextCharFormat | None]]:
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
                    yield utf16_length(text[:i]), utf16_length(text[i : i + num]), f
                else:
                    yield i, num, f
                i += num
        if orig_i == i and state.parse in seen_states[i]:
            # Something went wrong in the syntax highlighter
            print('Syntax highlighter returned a zero length format, parse state:', state.parse)
            break


class SimpleState:
    __slots__ = ('parse',)

    def __init__(self) -> None:
        self.parse = 0

    def copy(self) -> SimpleState:
        s = SimpleState()
        s.parse = self.parse
        return s


class SimpleUserData(QTextBlockUserData):
    def __init__(self) -> None:
        QTextBlockUserData.__init__(self)
        self.state = SimpleState()
        self.doc_name = None

    def clear(self, state: SimpleState | None = None, doc_name: str | None = None) -> None:
        self.state = SimpleState() if state is None else state
        self.doc_name = doc_name


class SyntaxHighlighter:
    def create_formats_func(highlighter) -> object:
        return {}

    spell_attributes = ()

    def tag_ok_for_spell(x, name: str | None = None) -> bool:
        return False

    user_data_factory: Callable[[], UserData] = SimpleUserData
    state_map: Mapping[int, StateFunction]

    def __init__(self) -> None:
        self.doc = None
        self.doc_name = None
        self.requests = deque()
        self.ignore_requests = False

    @property
    def has_requests(self) -> bool:
        return bool(self.requests)

    def apply_theme(self, theme: Theme) -> None:
        self.theme = {k: highlight_to_char_format(v) for k, v in theme.items()}
        self.create_formats()
        self.rehighlight()

    def create_formats(self) -> None:
        self.formats = self.create_formats_func()

    def set_document(self, doc: QTextDocument | None, doc_name: str | None = None) -> None:
        old_doc = self.doc
        if old_doc is not None:
            old_doc.contentsChange.disconnect(self.reformat_blocks)
            c = QTextCursor(old_doc)
            c.beginEditBlock()
            blk = old_doc.begin()
            while blk.isValid():
                layout = blk.layout()
                assert layout is not None
                layout.clearFormats()
                blk = blk.next()
            c.endEditBlock()
        self.doc = self.doc_name = None
        if doc is not None:
            self.doc = doc
            self.doc_name = doc_name
            doc.contentsChange.connect(self.reformat_blocks)
            self.rehighlight()

    def rehighlight(self) -> None:
        doc = self.doc
        if doc is None:
            return
        lb = doc.lastBlock()
        with BusyCursor():
            self.reformat_blocks(0, 0, lb.position() + lb.length())

    def get_user_data(self, block: QTextBlock) -> tuple[UserData, bool]:
        ud = block.userData()
        new_data = False
        if ud is None:
            ud = self.user_data_factory()
            block.setUserData(cast('QTextBlockUserData', ud))
            new_data = True
            return ud, new_data
        # The user data of blocks is always created by user_data_factory()
        return cast('UserData', ud), new_data

    def reformat_blocks(self, position: int, removed: int, added: int) -> None:
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
        end_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        self.requests.append((start_cursor, end_cursor))
        QTimer.singleShot(0, self.do_one_block)

    def do_one_block(self) -> None:
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
            doc = self.doc
            assert doc is not None
            try:
                doc.markContentsDirty(block.position(), block.length())
            except AttributeError:
                self.requests.clear()
                return
            ok = start_cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
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

    def join(self) -> None:
        """Blocks until all pending highlighting requests are handled"""
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
    def is_working(self) -> bool:
        return bool(self.requests)

    def parse_single_block(self, block: QTextBlock) -> tuple[list[QTextLayout.FormatRange], bool]:
        ud, is_new_ud = self.get_user_data(block)
        orig_state = ud.state
        pblock = block.previous()
        if pblock.isValid():
            start_state = cast('UserData | None', pblock.userData())
            if start_state is None:
                start_state = self.user_data_factory().state
            else:
                start_state = start_state.state.copy()
        else:
            start_state = self.user_data_factory().state
        ud.clear(state=start_state, doc_name=self.doc_name)  # Ensure no stale user data lingers
        formats = []
        for i, num, fmt in run_loop(ud, self.state_map, self.formats, str(block.text())):
            if fmt is not None:
                r = QTextLayout.FormatRange()
                r.start, r.length, r.format = i, num, fmt
                formats.append(r)
        force_next_highlight = is_new_ud or ud.state != orig_state
        return formats, force_next_highlight

    def reformat_block(self, block: QTextBlock) -> None:
        if block.isValid():
            self.reformat_blocks(block.position(), 0, 1)

    def apply_format_changes(self, block: QTextBlock, formats: list[QTextLayout.FormatRange]) -> None:
        layout = block.layout()
        assert layout is not None
        preedit_start = layout.preeditAreaPosition()
        preedit_length = len(layout.preeditAreaText())
        if preedit_length != 0 and preedit_start != 0:
            for r in formats:
                # Adjust range by pre-edit text, if any
                if r.start >= preedit_start:
                    r.start += preedit_length
                elif r.start + r.length >= preedit_start:
                    r.length += preedit_length
        layout.setFormats(formats)

    def formats_for_line(self, block: QTextBlock, start: int, length: int) -> Iterator[QTextLayout.FormatRange]:
        layout = block.layout()
        assert layout is not None
        start_in_block = start - block.position()
        limit = start_in_block + length
        for f in layout.formats():
            if f.start >= start_in_block and f.start < limit and f.format.hasProperty(QTextFormat.Property.BackgroundBrush):
                yield f
