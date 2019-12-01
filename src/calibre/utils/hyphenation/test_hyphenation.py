#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import shutil, os
import unittest

from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.hyphenation.dictionaries import (
    dictionary_name_for_locale, path_to_dictionary
)


class TestHyphenation(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    @classmethod
    def setUpClass(cls):
        tdir = PersistentTemporaryDirectory()
        path_to_dictionary.cache_dir = tdir

    @classmethod
    def tearDownClass(cls):
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


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestHyphenation)
