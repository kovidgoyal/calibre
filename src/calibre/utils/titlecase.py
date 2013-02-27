#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Original Perl version by: John Gruber http://daringfireball.net/ 10 May 2008
Python version by Stuart Colville http://muffinresearch.co.uk
License: http://www.opensource.org/licenses/mit-license.php
"""

import re

from calibre.utils.icu import capitalize

__all__ = ['titlecase']
__version__ = '0.5'

SMALL = 'a|an|and|as|at|but|by|en|for|if|in|of|on|or|the|to|v\.?|via|vs\.?'
PUNCT = r"""!"#$%&'‘()*+,\-‒–—―./:;?@[\\\]_`{|}~"""

SMALL_WORDS = re.compile(r'^(%s)$' % SMALL, re.I)
INLINE_PERIOD = re.compile(r'[a-z][.][a-z]', re.I)
UC_ELSEWHERE = re.compile(r'[%s]*?[a-zA-Z]+[A-Z]+?' % PUNCT)
CAPFIRST = re.compile(r"^[%s]*?([A-Za-z])" % PUNCT)
SMALL_FIRST = re.compile(r'^([%s]*)(%s)\b' % (PUNCT, SMALL), re.I)
SMALL_LAST = re.compile(r'\b(%s)[%s]?$' % (SMALL, PUNCT), re.I)
SMALL_AFTER_NUM = re.compile(r'(\d+\s+)(a|an|the)\b', re.I)
SUBPHRASE = re.compile(r'([:.;?!][ ])(%s)' % SMALL)
APOS_SECOND = re.compile(r"^[dol]{1}['‘]{1}[a-z]+$", re.I)
ALL_CAPS = re.compile(r'^[A-Z0-9\s%s]+$' % PUNCT)
UC_INITIALS = re.compile(r"^(?:[A-Z]{1}\.{1}|[A-Z]{1}\.{1}[A-Z]{1})+$")

_lang = None

def lang():
    global _lang
    if _lang is None:
        from calibre.utils.localization import get_lang
        _lang = get_lang().lower()
    return _lang

def titlecase(text):

    """
    Titlecases input text

    This filter changes all words to Title Caps, and attempts to be clever
    about *un*capitalizing SMALL words like a/an/the in the input.

    The list of "SMALL words" which are not capped comes from
    the New York Times Manual of Style, plus 'vs' and 'v'.

    """

    all_caps = ALL_CAPS.match(text)

    words = re.split('\s+', text)
    line = []
    for word in words:
        if all_caps:
            if UC_INITIALS.match(word):
                line.append(word)
                continue
            else:
                word = icu_lower(word)

        if APOS_SECOND.match(word):
            word = word.replace(word[0], icu_upper(word[0]), 1)
            word = word[:2] + icu_upper(word[2]) + word[3:]
            line.append(word)
            continue
        if INLINE_PERIOD.search(word) or UC_ELSEWHERE.match(word):
            line.append(word)
            continue
        if SMALL_WORDS.match(word):
            line.append(icu_lower(word))
            continue

        hyphenated = []
        for item in word.split('-'):
            hyphenated.append(CAPFIRST.sub(lambda m: icu_upper(m.group(0)), item))
        line.append("-".join(hyphenated))


    result = " ".join(line)

    result = SMALL_FIRST.sub(lambda m: '%s%s' % (
        m.group(1),
        capitalize(m.group(2))
    ), result)

    result = SMALL_AFTER_NUM.sub(lambda m: '%s%s' % (m.group(1),
        capitalize(m.group(2))
    ), result)

    result = SMALL_LAST.sub(lambda m: capitalize(m.group(0)), result)

    result = SUBPHRASE.sub(lambda m: '%s%s' % (
        m.group(1),
        capitalize(m.group(2))
    ), result)

    return result

