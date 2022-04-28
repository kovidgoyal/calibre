#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.gui2.ui import get_gui


def get_db():
    if hasattr(get_db, 'db'):
        return get_db.db.new_api
    return get_gui().current_db.new_api
