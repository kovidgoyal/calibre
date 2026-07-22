#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>


class NullSmarts:
    override_tab_stop_width = None

    def __init__(self, editor):
        pass

    def get_extra_selections(self, editor):
        return ()

    def get_smart_selection(self, editor, update=True):
        return editor.selected_text

    def verify_for_spellcheck(self, cursor, highlighter):
        return False

    def cursor_position_with_sourceline(self, cursor, for_position_sync=True, use_matched_tag=True):
        return None, None

    def goto_sourceline(self, editor, sourceline, tags, attribute=None):
        return False

    def get_inner_HTML(self, editor):
        return None

    def handle_key_press(self, ev, editor):
        return False

    def get_completion_data(self, editor, ev=None):
        return None

    def rename_block_tag(self, editor, new_name):
        pass

    def set_text_alignment(self, editor, value):
        pass

    def surround_with_custom_tag(self, editor, opent, close):
        pass

    def insert_hyperlink(self, editor, target, text, template=None):
        pass

    def insert_tag(self, editor, name):
        pass

    def remove_tag(self, editor):
        pass

    def split_tag(self, editor):
        pass
