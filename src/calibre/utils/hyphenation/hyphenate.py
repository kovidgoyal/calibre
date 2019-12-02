#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os

import regex

from calibre.constants import plugins
from calibre.utils.hyphenation.dictionaries import (
    dictionary_name_for_locale, path_to_dictionary
)
from polyglot.builtins import unicode_type
from polyglot.functools import lru_cache

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


hyphen = None


@lru_cache()
def dictionary_for_locale(locale):
    global hyphen
    name = dictionary_name_for_locale(locale)
    if name is not None:
        path = path_to_dictionary(name)
        if hyphen is None:
            hyphen, hyphen_err = plugins['hyphen']
            if hyphen_err:
                raise RuntimeError('Failed to load the hyphen plugin with error: {}'.format(hyphen_err))
        fd = os.open(path, getattr(os, 'O_BINARY', 0) | os.O_RDONLY)
        return hyphen.load_dictionary(fd)


def add_soft_hyphens(word, dictionary, hyphen_char='\u00ad'):
    word = unicode_type(word)
    if len(word) > 99 or '=' in word:
        return word
    prefix, q, suffix = remove_punctuation(word)
    q = q.replace(hyphen_char, '')
    if len(q) < 4:
        return word
    lq = q.lower()  # the hyphen library needs lowercase words to work
    try:
        ans = hyphen.simple_hyphenate(dictionary, lq)
    except ValueError:
        # Can happen is the word requires non-standard hyphenation (i.e.
        # replacements)
        return word
    parts = ans.split('=')
    if len(parts) == 1:
        return word
    if lq != q:
        aparts = []
        pos = 0
        for p in parts:
            lp = len(p)
            aparts.append(q[pos:pos+lp])
            pos += lp
        parts = aparts
    return prefix + hyphen_char.join(parts) + suffix
