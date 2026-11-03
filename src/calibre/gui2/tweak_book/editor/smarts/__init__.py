#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>


class NullSmarts:
    override_tab_stop_width = None

    def __init__(self, editor) -> None:
        pass

    def get_extra_selections(self, editor):
        return ()

    def get_smart_selection(self, editor, update=True):
        return editor.selected_text

    def verify_for_spellcheck(self, cursor, highlighter) -> bool:
        return False

    def cursor_position_with_sourceline(self, cursor, for_position_sync=True, use_matched_tag=True):
        return None, None

    def goto_sourceline(self, editor, sourceline, tags, attribute=None) -> bool:
        return False

    def get_inner_HTML(self, editor) -> None:
        return None

    def handle_key_press(self, ev, editor) -> bool:
        return False

    def get_completion_data(self, editor, ev=None) -> None:
        return None

    def rename_block_tag(self, editor, new_name) -> None:
        pass

    def set_text_alignment(self, editor, value) -> None:
        pass

    def surround_with_custom_tag(self, editor, opent, close) -> None:
        pass

    def insert_hyperlink(self, editor, target, text, template=None) -> None:
        pass

    def insert_tag(self, editor, name) -> None:
        pass

    def remove_tag(self, editor) -> None:
        pass

    def split_tag(self, editor) -> None:
        pass
