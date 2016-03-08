#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

import regex

REGEX_FLAGS = regex.VERSION1 | regex.UNICODE

def compile_pat(pat):
    return regex.compile(pat, flags=REGEX_FLAGS)

def parse_length(raw):
    raise NotImplementedError('TODO: implement this')
