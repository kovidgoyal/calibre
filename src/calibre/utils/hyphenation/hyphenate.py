#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import os

import regex

from calibre.utils.hyphenation.dictionaries import (
    dictionary_name_for_locale, path_to_dictionary
)
from polyglot.functools import lru_cache

REGEX_FLAGS = regex.VERSION1 | regex.WORD | regex.FULLCASE | regex.UNICODE


@lru_cache()
def dictionary_for_locale(locale):
    name = dictionary_name_for_locale(locale)
    if name is not None:
        from calibre_extensions import hyphen
        path = path_to_dictionary(name)
        fd = os.open(path, getattr(os, 'O_BINARY', 0) | os.O_RDONLY)
        return hyphen.load_dictionary(fd)


def add_soft_hyphens(word, dictionary, hyphen_char='\u00ad'):
    word = str(word)
    if len(word) > 99 or '=' in word:
        return word
    q = word
    q = q.replace(hyphen_char, '')
    if len(q) < 4:
        return word
    lq = q.lower()  # the hyphen library needs lowercase words to work
    from calibre_extensions import hyphen
    try:
        ans = hyphen.simple_hyphenate(dictionary, lq)
    except ValueError:
        # Can happen if the word requires non-standard hyphenation (i.e.
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
    return hyphen_char.join(parts)


tags_not_to_hyphenate = frozenset((
    'video', 'audio', 'script', 'code', 'pre', 'img', 'br', 'samp', 'kbd',
    'var', 'abbr', 'acronym', 'sub', 'sup', 'button', 'option', 'label',
    'textarea', 'input', 'math', 'svg', 'style', 'title', 'head'
))


def barename(x):
    return x.split('}', 1)[-1]


def words_pat():
    ans = getattr(words_pat, 'ans', None)
    if ans is None:
        ans = words_pat.ans = regex.compile(r'\w+', REGEX_FLAGS)
    return ans


def add_soft_hyphens_to_words(words, dictionary, hyphen_char='\u00ad'):
    pos = 0
    parts = []
    for m in words_pat().finditer(words):
        word = m.group()
        if m.start() > pos:
            parts.append(words[pos:m.start()])
        parts.append(add_soft_hyphens(word, dictionary, hyphen_char))
        pos = m.end()
    if pos < len(words):
        parts.append(words[pos:])
    return ''.join(parts)


def add_to_tag(stack, elem, locale, hyphen_char):
    name = barename(elem.tag)
    if name in tags_not_to_hyphenate:
        return
    tl = elem.get('lang') or elem.get('{http://www.w3.org/XML/1998/namespace}lang') or locale
    dictionary = dictionary_for_locale(tl)
    if dictionary is not None and elem.text and not elem.text.isspace():
        elem.text = add_soft_hyphens_to_words(elem.text, dictionary, hyphen_char)
    for child in elem:
        if dictionary is not None and child.tail and not child.tail.isspace():
            child.tail = add_soft_hyphens_to_words(child.tail, dictionary, hyphen_char)
        if not callable(getattr(child, 'tag', None)):
            stack.append((child, tl))


def add_soft_hyphens_to_html(root, locale='en', hyphen_char='\u00ad'):
    stack = [(root, locale)]
    while stack:
        elem, locale = stack.pop()
        add_to_tag(stack, elem, locale, hyphen_char)


def remove_soft_hyphens_from_html(root, hyphen_char='\u00ad'):
    for elem in root.iterdescendants():
        if elem.tail:
            elem.tail = elem.tail.replace(hyphen_char, '')
        text = getattr(elem, 'text', None)
        if text:
            elem.text = elem.text.replace(hyphen_char, '')
