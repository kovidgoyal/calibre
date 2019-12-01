#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import unittest
from calibre.utils.hyphenation.dictionaries import dictionary_name_for_locale


class TestHyphenation(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def test_locale_to_hyphen_dictionary(self):
        def t(x, expected=None):
            self.ae(dictionary_name_for_locale(x), 'hyph_{}.dic'.format(expected) if expected else None)
        t('en', 'en_US')
        t('en_IN', 'en_GB')
        t('de', 'de_DE')
        t('fr', 'fr')
        t('XXX')


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestHyphenation)
