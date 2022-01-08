#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import regex

REGEX_FLAGS = regex.VERSION1 | regex.WORD | regex.FULLCASE | regex.MULTILINE | regex.UNICODE

regex_cache = {}


def compile_regular_expression(text, flags=REGEX_FLAGS):
    key = flags, text
    ans = regex_cache.get(key)
    if ans is None:
        ans = regex_cache[key] = regex.compile(text, flags=flags)
    return ans
