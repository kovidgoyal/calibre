#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from collections import defaultdict

from calibre.constants import plugins
from calibre.utils.icu import ord_string


def character_name_from_code(code):
    return plugins['unicode_names'][0].name_for_codepoint(code) or 'U+{:X}'.format(code)


def html_entities():
    ans = getattr(html_entities, 'ans', None)
    if ans is None:
        from calibre.ebooks.html_entities import html5_entities
        ans = defaultdict(set)
        for name, char in html5_entities.iteritems():
            try:
                ans[name.lower()].add(ord_string(char)[0])
            except TypeError:
                continue
        ans['nnbsp'].add(0x202F)
        ans = dict(ans)
        html_entities.ans = ans
    return ans


def points_for_word(w):
    w = w.lower()
    ans = points_for_word.cache.get(w)
    if ans is None:
        ans = plugins['unicode_names'][0].codepoints_for_word(w.encode('utf-8')) | html_entities().get(w, set())
        points_for_word.cache[w] = ans
    return ans
points_for_word.cache = {}  # noqa
