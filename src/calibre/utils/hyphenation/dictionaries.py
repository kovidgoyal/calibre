#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json

from calibre.utils.localization import lang_as_iso639_1
from polyglot.builtins import iteritems
from polyglot.functools import lru_cache


def locale_map():
    ans = getattr(locale_map, 'ans', None)
    if ans is None:
        ans = locale_map.ans = {k.lower(): v for k, v in iteritems(json.loads(P('hyphenation/locales.json', data=True)))}
    return ans


@lru_cache()
def dictionary_name_for_locale(loc):
    loc = loc.lower().replace('-', '_')
    lmap = locale_map()
    if loc in lmap:
        return lmap[loc]
    parts = loc.split('_')
    if len(parts) > 2:
        loc = '_'.join(parts[:2])
        if loc in lmap:
            return lmap[loc]
    loc = lang_as_iso639_1(parts[0])
    if not loc:
        return
    if loc in lmap:
        return lmap[loc]
    if loc == 'en':
        return lmap['en_us']
    if loc == 'de':
        return lmap['de_de']
    q = loc + '_'
    for k, v in iteritems(lmap):
        if k.startswith(q):
            return lmap[k]
