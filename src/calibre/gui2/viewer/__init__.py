#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


def get_current_book_data(set_val=False):
    if set_val is not False:
        setattr(get_current_book_data, 'ans', set_val)
    return getattr(get_current_book_data, 'ans', {})
