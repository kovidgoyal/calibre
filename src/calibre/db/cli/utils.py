#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import unicodedata

eaw = unicodedata.east_asian_width


def chr_width(x):
    return 1 + eaw(x).startswith('W')


def str_width(x):
    return sum(map(chr_width, x))
