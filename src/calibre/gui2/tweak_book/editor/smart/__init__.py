#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

class NullSmarts(object):

    def __init__(self, editor):
        pass

    def get_extra_selections(self, editor):
        return ()

    def get_smart_selection(self, editor, update=True):
        return editor.selected_text

    def verify_for_spellcheck(self, cursor, highlighter):
        return False

    def cursor_position_with_sourceline(self, cursor):
        return None, None

    def goto_sourceline(self, editor, sourceline, tags, attribute=None):
        return False

    def get_inner_HTML(self, editor):
        return None
