#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import shutil
import unittest

from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.hyphenation.dictionaries import (
    dictionary_name_for_locale, get_cache_path, path_to_dictionary
)
from calibre.utils.hyphenation.hyphenate import (
    add_soft_hyphens, dictionary_for_locale, remove_punctuation
)


class TestHyphenation(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def setUp(cls):
        tdir = PersistentTemporaryDirectory()
        path_to_dictionary.cache_dir = tdir
        dictionary_name_for_locale.cache_clear()
        dictionary_for_locale.cache_clear()
        get_cache_path.cache_clear()

    def tearDown(self):
        dictionary_name_for_locale.cache_clear()
        dictionary_for_locale.cache_clear()
        get_cache_path.cache_clear()
        try:
            shutil.rmtree(path_to_dictionary.cache_dir)
        except EnvironmentError:
            pass
        path_to_dictionary.cache_dir = None

    def test_locale_to_hyphen_dictionary(self):

        def t(x, expected=None):
            self.ae(
                dictionary_name_for_locale(x),
                'hyph_{}.dic'.format(expected) if expected else None
            )

        t('en', 'en_US')
        t('en_IN', 'en_GB')
        t('de', 'de_DE')
        t('es', 'es_ANY')
        t('nl', 'nl_NL')
        t('fr', 'fr')
        t('XXX')

        cache = [False]

        def cache_callback():
            cache[0] = True

        self.assertTrue(
            os.path.exists(path_to_dictionary(dictionary_name_for_locale('en'), cache_callback))
        )
        self.assertTrue(cache[0])
        cache[0] = False
        self.assertTrue(
            os.path.exists(path_to_dictionary(dictionary_name_for_locale('es'), cache_callback))
        )
        self.assertFalse(cache[0])

    def test_add_soft_hyphens(self):
        self.ae(remove_punctuation('word'), ('', 'word', ''))
        self.ae(remove_punctuation('wo.rd.'), ('', 'wo.rd', '.'))
        self.ae(remove_punctuation('"«word!!'), ('"«', 'word', '!!'))

        dictionary = dictionary_for_locale('en')

        def t(word, expected):
            self.ae(add_soft_hyphens(word, dictionary, '='), expected)

        t('beautiful', 'beau=ti=ful')
        t('beautiful.', 'beau=ti=ful.')
        t('"beautiful.', '"beau=ti=ful.')
        t('BeauTiful', 'Beau=Ti=ful')

        dictionary = dictionary_for_locale('hu')
        t('asszonnyal', 'asszonnyal')


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestHyphenation)
