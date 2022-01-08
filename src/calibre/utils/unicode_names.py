#!/usr/bin/env python
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


from collections import defaultdict

from calibre.utils.icu import ord_string
from polyglot.builtins import iteritems


def character_name_from_code(code):
    from calibre_extensions.unicode_names import name_for_codepoint
    return name_for_codepoint(code) or f'U+{code:X}'


def html_entities():
    ans = getattr(html_entities, 'ans', None)
    if ans is None:
        from calibre.ebooks.html_entities import html5_entities
        ans = defaultdict(set)
        for name, char in iteritems(html5_entities):
            try:
                ans[name.lower()].add(ord_string(char)[0])
            except TypeError:
                continue
        ans['nnbsp'].add(0x202F)
        ans = dict(ans)
        html_entities.ans = ans
    return ans


def points_for_word(w):
    """Returns the set of all codepoints that contain ``word`` in their names"""
    w = w.lower()
    ans = points_for_word.cache.get(w)
    if ans is None:
        from calibre_extensions.unicode_names import codepoints_for_word
        ans = codepoints_for_word(w) | html_entities().get(w, set())
        points_for_word.cache[w] = ans
    return ans


points_for_word.cache = {}  # noqa
