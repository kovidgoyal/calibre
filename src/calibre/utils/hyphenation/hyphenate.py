#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

# TODO: lower case word? remove trailing punctuation. abort early if contains = or length < 4 or length > 99
# TODO: test with replacement words


import regex
REGEX_FLAGS = regex.VERSION1 | regex.WORD | regex.FULLCASE | regex.UNICODE


def pats():
    ans = getattr(pats, 'ans', None)
    if ans is None:
        pats.ans = ans = regex.compile(r'^\p{P}+', REGEX_FLAGS), regex.compile(r'\p{P}+$', REGEX_FLAGS)
    return ans


def remove_punctuation(word):
    leading, trailing = pats()
    prefix = suffix = ''
    nword, n = leading.subn('', word)
    if n > 0:
        count = len(word) - len(nword)
        prefix, word = word[:count], nword
    nword, n = trailing.subn('', word)
    if n > 0:
        count = len(word) - len(nword)
        suffix, word = word[-count:], nword
    return prefix, word, suffix
