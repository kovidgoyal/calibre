#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>


import glob
import os
import re
import shutil
import sys
from calibre_extensions import hunspell
from collections import defaultdict, namedtuple
from functools import partial
from itertools import chain

from calibre import prints
from calibre.constants import config_dir, filesystem_encoding, iswindows
from calibre.spell import parse_lang_code
from calibre.utils.config import JSONConfig
from calibre.utils.icu import capitalize
from calibre.utils.localization import get_lang, get_system_locale
from polyglot.builtins import iteritems, itervalues

Dictionary = namedtuple('Dictionary', 'primary_locale locales dicpath affpath builtin name id')
LoadedDictionary = namedtuple('Dictionary', 'primary_locale locales obj builtin name id')
dprefs = JSONConfig('dictionaries/prefs.json')
dprefs.defaults['preferred_dictionaries'] = {}
dprefs.defaults['preferred_locales'] = {}
dprefs.defaults['user_dictionaries'] = [{'name':_('Default'), 'is_active':True, 'words':[]}]
not_present = object()


class UserDictionary:

    __slots__ = ('name', 'is_active', 'words')

    def __init__(self, **kwargs):
        self.name = kwargs['name']
        self.is_active = kwargs['is_active']
        self.words = {(w, langcode) for w, langcode in kwargs['words']}

    def serialize(self):
        return {'name':self.name, 'is_active': self.is_active, 'words':[
            (w, l) for w, l in self.words]}


_builtins = _custom = None


def builtin_dictionaries():
    global _builtins
    if _builtins is None:
        dics = []
        for lc in glob.glob(os.path.join(P('dictionaries', allow_user_override=False), '*/locales')):
            with open(lc, 'rb') as lcf:
                locales = list(filter(None, lcf.read().decode('utf-8').splitlines()))
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
            with open(lc, 'rb') as cdf:
                locales = list(filter(None, cdf.read().decode('utf-8').splitlines()))
            try:
                name, locale, locales = locales[0], locales[1], locales[1:]
            except IndexError:
                continue
            base = os.path.dirname(lc)
            ploc = parse_lang_code(locale)
            if ploc.countrycode is None:
                continue
            dics.append(Dictionary(
                ploc, frozenset(filter(lambda x:x.countrycode is not None, map(parse_lang_code, locales))), os.path.join(base, '%s.dic' % locale),
                os.path.join(base, '%s.aff' % locale), False, name, os.path.basename(base)))
        _custom = frozenset(dics)
    return _custom


default_en_locale = 'en-US'
try:
    ul = parse_lang_code(get_system_locale() or 'en-US')
except ValueError:
    ul = None
if ul is not None and ul.langcode == 'eng' and ul.countrycode in 'GB BS BZ GH IE IN JM NZ TT'.split():
    default_en_locale = 'en-' + ul.countrycode
default_preferred_locales = {'eng':default_en_locale, 'deu':'de-DE', 'spa':'es-ES', 'fra':'fr-FR'}


def best_locale_for_language(langcode):
    best_locale = dprefs['preferred_locales'].get(langcode, default_preferred_locales.get(langcode, None))
    if best_locale is not None:
        return parse_lang_code(best_locale)


def preferred_dictionary(locale):
    return {parse_lang_code(k):v for k, v in iteritems(dprefs['preferred_dictionaries'])}.get(locale, None)


def remove_dictionary(dictionary):
    if dictionary.builtin:
        raise ValueError('Cannot remove builtin dictionaries')
    base = os.path.dirname(dictionary.dicpath)
    shutil.rmtree(base)
    dprefs['preferred_dictionaries'] = {k:v for k, v in iteritems(dprefs['preferred_dictionaries']) if v != dictionary.id}


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
        for d in sorted(collection, key=lambda d: d.name or ''):
            if d.primary_locale.langcode == locale.langcode:
                return d


def load_dictionary(dictionary):

    def fix_path(path):
        if isinstance(path, bytes):
            path = path.decode(filesystem_encoding)
        path = os.path.abspath(path)
        if iswindows:
            path = fr'\\?\{path}'
        return path

    obj = hunspell.Dictionary(fix_path(dictionary.dicpath), fix_path(dictionary.affpath))
    return LoadedDictionary(dictionary.primary_locale, dictionary.locales, obj, dictionary.builtin, dictionary.name, dictionary.id)


class Dictionaries:

    def __init__(self):
        self.remove_hyphenation = re.compile('[\u2010-]+')
        self.negative_pat = re.compile(r'-[.\d+]')
        self.fix_punctuation_pat = re.compile(r'''[:.]''')
        self.dictionaries = {}
        self.word_cache = {}
        self.ignored_words = set()
        self.added_user_words = {}
        try:
            self.default_locale = parse_lang_code(get_lang())
        except ValueError:
            self.default_locale = parse_lang_code('en-US')
        self.ui_locale = self.default_locale

    def initialize(self, force=False):
        if force or not hasattr(self, 'active_user_dictionaries'):
            self.read_user_dictionaries()

    def clear_caches(self):
        self.dictionaries.clear(), self.word_cache.clear()

    def clear_ignored(self):
        self.ignored_words.clear()

    def dictionary_for_locale(self, locale):
        ans = self.dictionaries.get(locale, not_present)
        if ans is not_present:
            ans = get_dictionary(locale)
            if ans is not None:
                ans = load_dictionary(ans)
                for ud in self.active_user_dictionaries:
                    for word, langcode in ud.words:
                        if langcode == locale.langcode:
                            try:
                                ans.obj.add(word)
                            except Exception:
                                # not critical since all it means is that the word won't show up in suggestions
                                prints(f'Failed to add the word {word!r} to the dictionary for {locale}', file=sys.stderr)
            self.dictionaries[locale] = ans
        return ans

    def ignore_word(self, word, locale):
        self.ignored_words.add((word, locale.langcode))
        self.word_cache[(word, locale)] = True

    def unignore_word(self, word, locale):
        self.ignored_words.discard((word, locale.langcode))
        self.word_cache.pop((word, locale), None)

    def is_word_ignored(self, word, locale):
        return (word, locale.langcode) in self.ignored_words

    @property
    def all_user_dictionaries(self):
        return chain(self.active_user_dictionaries, self.inactive_user_dictionaries)

    def user_dictionary(self, name):
        for ud in self.all_user_dictionaries:
            if ud.name == name:
                return ud

    def read_user_dictionaries(self):
        self.active_user_dictionaries = []
        self.inactive_user_dictionaries = []
        for d in dprefs['user_dictionaries'] or dprefs.defaults['user_dictionaries']:
            d = UserDictionary(**d)
            (self.active_user_dictionaries if d.is_active else self.inactive_user_dictionaries).append(d)

    def mark_user_dictionary_as_active(self, name, is_active=True):
        d = self.user_dictionary(name)
        if d is not None:
            d.is_active = is_active
            self.save_user_dictionaries()
            return True
        return False

    def save_user_dictionaries(self):
        dprefs['user_dictionaries'] = [d.serialize() for d in self.all_user_dictionaries]

    def add_user_words(self, words, langcode):
        for d in itervalues(self.dictionaries):
            if d and getattr(d.primary_locale, 'langcode', None) == langcode:
                for word in words:
                    d.obj.add(word)

    def remove_user_words(self, words, langcode):
        for d in itervalues(self.dictionaries):
            if d and d.primary_locale.langcode == langcode:
                for word in words:
                    d.obj.remove(word)

    def add_to_user_dictionary(self, name, word, locale):
        ud = self.user_dictionary(name)
        if ud is None:
            raise ValueError('Cannot add to the dictionary named: %s as no such dictionary exists' % name)
        wl = len(ud.words)
        if isinstance(word, (set, frozenset)):
            ud.words |= word
            self.add_user_words(word, locale.langcode)
        else:
            ud.words.add((word, locale.langcode))
            self.add_user_words((word,), locale.langcode)
        if len(ud.words) > wl:
            self.save_user_dictionaries()
            try:
                self.word_cache.pop((word, locale), None)
            except TypeError:
                pass  # word is a set, ignore
            return True
        return False

    def remove_from_user_dictionaries(self, word, locale):
        key = (word, locale.langcode)
        changed = False
        for ud in self.active_user_dictionaries:
            if key in ud.words:
                changed = True
                ud.words.discard(key)
        if changed:
            self.word_cache.pop((word, locale), None)
            self.save_user_dictionaries()
            self.remove_user_words((word,), locale.langcode)
        return changed

    def remove_from_user_dictionary(self, name, words):
        changed = False
        removals = defaultdict(set)
        keys = [(w, l.langcode) for w, l in words]
        for d in self.all_user_dictionaries:
            if d.name == name:
                for key in keys:
                    if key in d.words:
                        d.words.discard(key)
                        removals[key[1]].add(key[0])
                        changed = True
        if changed:
            for key in words:
                self.word_cache.pop(key, None)
            for langcode, words in iteritems(removals):
                self.remove_user_words(words, langcode)
            self.save_user_dictionaries()
        return changed

    def word_in_user_dictionary(self, word, locale):
        key = (word, locale.langcode)
        for ud in self.active_user_dictionaries:
            if key in ud.words:
                return ud.name

    def create_user_dictionary(self, name):
        if name in {d.name for d in self.all_user_dictionaries}:
            raise ValueError('A dictionary named %s already exists' % name)
        d = UserDictionary(name=name, is_active=True, words=())
        self.active_user_dictionaries.append(d)
        self.save_user_dictionaries()

    def remove_user_dictionary(self, name):
        changed = False
        for x in (self.active_user_dictionaries, self.inactive_user_dictionaries):
            for d in tuple(x):
                if d.name == name:
                    x.remove(d)
                    changed = True
        if changed:
            self.save_user_dictionaries()
            self.clear_caches()
        return changed

    def rename_user_dictionary(self, name, new_name):
        changed = False
        for d in self.all_user_dictionaries:
            if d.name == name:
                d.name = new_name
                changed = True
        if changed:
            self.save_user_dictionaries()
        return changed

    def recognized(self, word, locale=None):
        locale = locale or self.default_locale
        key = (word, locale)
        ans = self.word_cache.get(key, None)
        if ans is None:
            lkey = (word, locale.langcode)
            ans = False
            if lkey in self.ignored_words:
                ans = True
            else:
                for ud in self.active_user_dictionaries:
                    if lkey in ud.words:
                        ans = True
                        break
                else:
                    d = self.dictionary_for_locale(locale)
                    if d is not None:
                        try:
                            ans = d.obj.recognized(word.replace('\u2010', '-'))
                        except ValueError:
                            pass
                    else:
                        ans = True
            if ans is False and self.negative_pat.match(word) is not None:
                ans = True
            self.word_cache[key] = ans
        return ans

    def suggestions(self, word, locale=None):
        locale = locale or self.default_locale
        d = self.dictionary_for_locale(locale)
        has_unicode_hyphen = '\u2010' in word
        ans = ()

        def add_suggestion(w, ans):
            return (w,) + tuple(x for x in ans if x != w)

        if d is not None:
            try:
                ans = d.obj.suggest(str(word).replace('\u2010', '-'))
            except ValueError:
                pass
            else:
                dehyphenated_word = self.remove_hyphenation.sub('', word)
                if len(dehyphenated_word) != len(word) and self.recognized(dehyphenated_word, locale):
                    # Ensure the de-hyphenated word is present and is the first suggestion
                    ans = add_suggestion(dehyphenated_word, ans)
                else:
                    m = self.fix_punctuation_pat.search(word)
                    if m is not None:
                        w1, w2 = word[:m.start()], word[m.end():]
                        if self.recognized(w1) and self.recognized(w2):
                            fw = w1 + m.group() + ' ' + w2
                            ans = add_suggestion(fw, ans)
                            if capitalize(w2) != w2:
                                fw = w1 + m.group() + ' ' + capitalize(w2)
                                ans = add_suggestion(fw, ans)

        if has_unicode_hyphen:
            ans = tuple(w.replace('-', '\u2010') for w in ans)
        return ans


def build_test():
    dictionaries = Dictionaries()
    dictionaries.initialize()
    eng = parse_lang_code('en')
    if not dictionaries.recognized('recognized', locale=eng):
        raise AssertionError('The word recognized was not recognized')


def find_tests():
    import unittest

    class TestDictionaries(unittest.TestCase):

        def setUp(self):
            dictionaries = Dictionaries()
            dictionaries.initialize()
            eng = parse_lang_code('en-GB')
            self.recognized = partial(dictionaries.recognized, locale=eng)
            self.suggestions = partial(dictionaries.suggestions, locale=eng)

        def ar(self, w):
            if not self.recognized(w):
                raise AssertionError('The word %r was not recognized' % w)

        def test_dictionaries(self):
            for w in 'recognized one-half one\u2010half'.split():
                self.ar(w)
            d = load_dictionary(get_dictionary(parse_lang_code('es-ES'))).obj
            self.assertTrue(d.recognized('Ahí'))
            self.assertIn('one\u2010half', self.suggestions('oone\u2010half'))
            d = load_dictionary(get_dictionary(parse_lang_code('es'))).obj
            self.assertIn('adequately', self.suggestions('ade-quately'))
            self.assertIn('magic. Wand', self.suggestions('magic.wand'))
            self.assertIn('List', self.suggestions('Lis𝑘t'))

    return unittest.TestLoader().loadTestsFromTestCase(TestDictionaries)
