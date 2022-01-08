#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import unicodedata

eaw = unicodedata.east_asian_width


def chr_width(x):
    return 1 + eaw(x).startswith('W')


def str_width(x):
    return sum(map(chr_width, x))
