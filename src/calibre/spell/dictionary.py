#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import cPickle, os, glob
from collections import namedtuple
from operator import attrgetter

from calibre.constants import plugins, config_dir
from calibre.utils.config import JSONConfig
from calibre.utils.localization import get_lang, canonicalize_lang

DictionaryLocale = namedtuple('DictionaryLocale', 'langcode countrycode')
Dictionary = namedtuple('Dictionary', 'primary_locale locales dicpath affpath builtin name')
LoadedDictionary = namedtuple('Dictionary', 'primary_locale locales obj builtin name')
hunspell = plugins['hunspell'][0]
if hunspell is None:
    raise RuntimeError('Failed to load hunspell: %s' % plugins[1])
dprefs = JSONConfig('dictionaries/prefs.json')
dprefs.defaults['preferred_dictionaries'] = {}
dprefs.defaults['preferred_locales'] = {}
not_present = object()

ccodes, ccodemap, country_names = None, None, None
def get_codes():
    global ccodes, ccodemap
    if ccodes is None:
        data = cPickle.loads(P('localization/iso3166.pickle', allow_user_override=False, data=True))
        ccodes, ccodemap, country_names = data['codes'], data['three_map'], data['names']
    return ccodes, ccodemap

def parse_lang_code(raw):
    parts = raw.replace('_', '-').split('-')
    lc = canonicalize_lang(parts[0])
    if lc is None:
        raise ValueError('Invalid language code: %r' % raw)
    cc = None
    if len(parts) > 1:
        ccodes, ccodemap = get_codes()[:2]
        q = parts[1].upper()
        if q in ccodes:
            cc = q
        else:
            cc = ccodemap.get(q, None)
    return DictionaryLocale(lc, cc)

_builtins = _custom = None

def builtin_dictionaries():
    global _builtins
    if _builtins is None:
        dics = []
        for lc in glob.glob(os.path.join(P('dictionaries', allow_user_override=False), '*/locales')):
            locales = filter(None, open(lc, 'rb').read().decode('utf-8').splitlines())
            locale = locales[0]
            base = os.path.dirname(lc)
            dics.append(Dictionary(
                parse_lang_code(locale), frozenset(map(parse_lang_code, locales)), os.path.join(base, '%s.dic' % locale),
                os.path.join(base, '%s.aff' % locale), True, None))
        _builtins = frozenset(dics)
    return _builtins

def custom_dictionaries(reread=False):
    global _custom
    if reread:
        _custom = None
    if _custom is None:
        dics = []
        for lc in glob.glob(os.path.join(config_dir, 'dictionaries', '*/locales')):
            locales = filter(None, open(lc, 'rb').read().decode('utf-8').splitlines())
            name, locale, locales = locales[0], locales[1], locales[1:]
            base = os.path.dirname(lc)
            dics.append(Dictionary(
                parse_lang_code(locale), frozenset(map(parse_lang_code, locales)), os.path.join(base, '%s.dic' % locale),
                os.path.join(base, '%s.aff' % locale), False, name))
        _custom = frozenset(dics)
    return _custom

_default_lang_codes = {'eng':parse_lang_code('en-US'), 'deu':parse_lang_code('de-DE'), 'spa':parse_lang_code('es-ES'), 'fra':parse_lang_code('fr-FR')}

def get_dictionary(locale, exact_match=False):
    preferred = {parse_lang_code(k):v for k, v in dprefs['preferred_dictionaries']}.get(locale, None)
    # First find all dictionaries that match locale exactly
    exact_matches = {}
    for collection in (custom_dictionaries(), builtin_dictionaries()):
        for d in collection:
            if d.primary_locale == locale:
                exact_matches[d.name] = d
        for d in collection:
            for q in d.locales:
                if q == locale and d.name not in exact_matches:
                    exact_matches[d.name] = d

    # If the user has specified a preferred dictionary for this locale, use it,
    # otherwise, if a builtin dictionary exists, use that
    if preferred in exact_matches:
        return exact_matches[preferred]
    # Return one of the exactly matching dictionaries, preferring user
    # installed to builtin ones
    for k in sorted(exact_matches, key=lambda x: (1, None) if x is None else (0, x)):
        return exact_matches[k]

    if exact_match:
        return

    # No dictionary matched the locale exactly, we will now fallback to
    # matching only on language. First see if a dictionary matching the
    # preferred locale for the language exists.
    best_locale = dprefs['preferred_locales'].get(locale.langcode, _default_lang_codes.get(locale.langcode, None))
    if best_locale is not None:
        ans = get_dictionary(best_locale, exact_match=True)
        if ans is not None:
            return ans

    # Now just return any dictionary that matches the language, preferring user
    # installed ones to builtin ones
    for collection in (custom_dictionaries(), builtin_dictionaries()):
        for d in sorted(collection, key=attrgetter('name')):
            if d.primary_locale.langcode == locale.langcode:
                return d

def load_dictionary(dictionary):
    with open(dictionary.dicpath, 'rb') as dic, open(dictionary.affpath, 'rb') as aff:
        obj = hunspell.Dictionary(dic.read(), aff.read())
    return LoadedDictionary(dictionary.primary_locale, dictionary.locales, obj, dictionary.builtin, dictionary.name)

class Dictionaries(object):

    def __init__(self):
        self.dictionaries = {}
        self.word_cache = {}
        try:
            self.default_locale = parse_lang_code(get_lang())
        except ValueError:
            self.default_locale = parse_lang_code('en-US')

    def clear_caches(self):
        self.dictionaries.clear(), self.word_cache.clear()

    def dictionary_for_locale(self, locale):
        ans = self.dictionaries.get(locale, not_present)
        if ans is not_present:
            ans = get_dictionary(locale)
            if ans is not None:
                ans = load_dictionary(ans)
            self.dictionaries[locale] = ans
        return ans

    def recognized(self, word, locale=None):
        locale = locale or self.default_locale
        if not isinstance(locale, DictionaryLocale):
            locale = parse_lang_code(locale)
        key = (word, locale)
        ans = self.word_cache.get(key, None)
        if ans is None:
            ans = False
            d = self.dictionary_for_locale(locale)
            if d is not None:
                try:
                    ans = d.obj.recognized(word)
                except ValueError:
                    pass
            self.word_cache[key] = ans
        return ans


if __name__ == '__main__':
    dictionaries = Dictionaries()
    print (dictionaries.recognized('recognized', 'en'))
