#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import namedtuple

from calibre.utils.localization import canonicalize_lang, load_iso3166

DictionaryLocale = namedtuple('DictionaryLocale', 'langcode countrycode')


def get_codes():
    data = load_iso3166()
    return data['codes'], data['three_map']


def parse_lang_code(raw):
    raw = raw or ''
    parts = raw.replace('_', '-').split('-')
    lc = canonicalize_lang(parts[0])
    if lc is None:
        raise ValueError('Invalid language code: %r' % raw)
    cc = None
    for sc in ['Cyrl', 'Latn']:
        if sc in parts:
            parts.remove(sc)
    if len(parts) > 1:
        ccodes, ccodemap = get_codes()[:2]
        q = parts[1].upper()
        if q in ccodes:
            cc = q
        else:
            cc = ccodemap.get(q, None)
    return DictionaryLocale(lc, cc)
