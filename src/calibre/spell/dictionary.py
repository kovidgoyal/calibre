#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import cPickle, os, glob, shutil
from collections import namedtuple
from operator import attrgetter

from calibre.constants import plugins, config_dir
from calibre.utils.config import JSONConfig
from calibre.utils.localization import get_lang, canonicalize_lang, get_system_locale

DictionaryLocale = namedtuple('DictionaryLocale', 'langcode countrycode')
Dictionary = namedtuple('Dictionary', 'primary_locale locales dicpath affpath builtin name id')
LoadedDictionary = namedtuple('Dictionary', 'primary_locale locales obj builtin name id')
hunspell = plugins['hunspell'][0]
if hunspell is None:
    raise RuntimeError('Failed to load hunspell: %s' % plugins[1])
dprefs = JSONConfig('dictionaries/prefs.json')
dprefs.defaults['preferred_dictionaries'] = {}
dprefs.defaults['preferred_locales'] = {}
not_present = object()

ccodes, ccodemap, country_names = None, None, None
def get_codes():
    global ccodes, ccodemap, country_names
    if ccodes is None:
        data = cPickle.loads(P('localization/iso3166.pickle', allow_user_override=False, data=True))
        ccodes, ccodemap, country_names = data['codes'], data['three_map'], data['names']
    return ccodes, ccodemap

def parse_lang_code(raw):
    raw = raw or ''
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
                os.path.join(base, '%s.aff' % locale), True, None, None))
        _builtins = frozenset(dics)
    return _builtins

def custom_dictionaries(reread=False):
    global _custom
    if _custom is None or reread:
        dics = []
        for lc in glob.glob(os.path.join(config_dir, 'dictionaries', '*/locales')):
            locales = filter(None, open(lc, 'rb').read().decode('utf-8').splitlines())
            try:
                name, locale, locales = locales[0], locales[1], locales[1:]
            except IndexError:
                continue
            base = os.path.dirname(lc)
            dics.append(Dictionary(
                parse_lang_code(locale), frozenset(map(parse_lang_code, locales)), os.path.join(base, '%s.dic' % locale),
                os.path.join(base, '%s.aff' % locale), False, name, os.path.basename(base)))
        _custom = frozenset(dics)
    return _custom

default_en_locale = 'en-US'
ul = parse_lang_code(get_system_locale())
if ul is not None and ul.langcode == 'eng' and ul.countrycode in 'GB BS BZ GH IE IN JM NZ TT'.split():
    default_en_locale = 'en-' + ul.countrycode
default_preferred_locales = {'eng':default_en_locale, 'deu':'de-DE', 'spa':'es-ES', 'fra':'fr-FR'}

def best_locale_for_language(langcode):
    best_locale = dprefs['preferred_locales'].get(langcode, default_preferred_locales.get(langcode, None))
    if best_locale is not None:
        return parse_lang_code(best_locale)

def preferred_dictionary(locale):
    return {parse_lang_code(k):v for k, v in dprefs['preferred_dictionaries'].iteritems()}.get(locale, None)

def remove_dictionary(dictionary):
    if dictionary.builtin:
        raise ValueError('Cannot remove builtin dictionaries')
    base = os.path.dirname(dictionary.dicpath)
    shutil.rmtree(base)
    dprefs['preferred_dictionaries'] = {k:v for k, v in dprefs['preferred_dictionaries'].iteritems() if v != dictionary.id}

def rename_dictionary(dictionary, name):
    lf = os.path.join(os.path.dirname(dictionary.dicpath), 'locales')
    with open(lf, 'r+b') as f:
        lines = f.read().splitlines()
        lines[:1] = [name.encode('utf-8')]
        f.seek(0), f.truncate(), f.write(b'\n'.join(lines))
    custom_dictionaries(reread=True)

def get_dictionary(locale, exact_match=False):
    preferred = preferred_dictionary(locale)
    # First find all dictionaries that match locale exactly
    exact_matches = {}
    for collection in (custom_dictionaries(), builtin_dictionaries()):
        for d in collection:
            if d.primary_locale == locale:
                exact_matches[d.id] = d
        for d in collection:
            for q in d.locales:
                if q == locale and d.id not in exact_matches:
                    exact_matches[d.id] = d

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
    best_locale = best_locale_for_language(locale.langcode)
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
    return LoadedDictionary(dictionary.primary_locale, dictionary.locales, obj, dictionary.builtin, dictionary.name, dictionary.id)

class Dictionaries(object):

    def __init__(self):
        self.dictionaries = {}
        self.word_cache = {}
        try:
            self.default_locale = parse_lang_code(get_lang())
        except ValueError:
            self.default_locale = parse_lang_code('en-US')
        self.ui_locale = self.default_locale

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
