#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import unicodedata

eaw = unicodedata.east_asian_width
# Control characters, other than tab and newline, that could be used to inject
# escape sequences into the terminal
CONTROL_CHARS = tuple(x for x in range(32) if x not in (9, 10)) + tuple(range(127, 160))
control_chars_table = dict.fromkeys(CONTROL_CHARS)


def chr_width(x):
    return 1 + eaw(x).startswith('W')


def str_width(x):
    return sum(map(chr_width, x))


def for_terminal(text: str) -> str:
    return text.translate(control_chars_table)
