#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import re

from calibre import prepare_string_for_xml
from calibre.gui2.ui import get_gui


def get_db():
    if hasattr(get_db, 'db'):
        return get_db.db.new_api
    return get_gui().current_db.new_api


def markup_text(text: str) -> str:
    closing = False

    def sub(m):
        nonlocal closing
        closing = not closing
        return '<b><i>' if closing else '</i></b>'

    return re.sub(r'\x1d', sub, prepare_string_for_xml(text))
