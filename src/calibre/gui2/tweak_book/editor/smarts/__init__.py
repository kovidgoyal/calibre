#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qt.core import QKeyEvent, QTextCursor, QTextEdit

    from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter
    from calibre.gui2.tweak_book.editor.text import TextEdit

    # The completion type, the data needed to perform the completion and the query
    CompletionData = tuple[str, object, str]


class NullSmarts:
    override_tab_stop_width: int | None = None

    def __init__(self, editor: TextEdit) -> None:
        pass

    def get_extra_selections(self, editor: TextEdit) -> Sequence[QTextEdit.ExtraSelection]:
        return ()

    def get_smart_selection(self, editor: TextEdit, update: bool = True) -> str:
        return editor.selected_text

    def verify_for_spellcheck(self, cursor: QTextCursor, highlighter: SyntaxHighlighter) -> bool:
        return False

    def cursor_position_with_sourceline(
        self, cursor: QTextCursor, for_position_sync: bool = True, use_matched_tag: bool = True
    ) -> tuple[int, list[str]] | tuple[None, None]:
        return None, None

    def goto_sourceline(self, editor: TextEdit, sourceline: int | None, tags: list[str], attribute: str | None = None) -> bool:
        return False

    def get_inner_HTML(self, editor: TextEdit) -> QTextCursor | None:
        return None

    def handle_key_press(self, ev: QKeyEvent, editor: TextEdit) -> bool:
        return False

    def get_completion_data(self, editor: TextEdit, ev: QKeyEvent | None = None) -> CompletionData | None:
        return None

    def rename_block_tag(self, editor: TextEdit, new_name: str) -> int | None:
        pass

    def set_text_alignment(self, editor: TextEdit, value: str) -> int | None:
        pass

    def surround_with_custom_tag(self, editor: TextEdit, opent: str, close: str) -> None:
        pass

    def insert_hyperlink(self, editor: TextEdit, target: str, text: str, template: str | None = None) -> None:
        pass

    def insert_tag(self, editor: TextEdit, name: str) -> None:
        pass

    def remove_tag(self, editor: TextEdit) -> None:
        pass

    def split_tag(self, editor: TextEdit) -> int | None:
        pass
