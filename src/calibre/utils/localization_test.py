#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import unittest

from calibre.utils.localization import bcp47_locale_name, locale_fallbacks, sanitize_lang


class TestLocaleNames(unittest.TestCase):
    ae = unittest.TestCase.assertEqual

    def test_sanitize_lang(self):
        for raw, expected in {
            'de_DE.utf8': 'de_DE',
            'de': 'de',
            'zh': 'zh_CN',
            # the script modifier must survive, the encoding must not
            'sr@latin': 'sr@latin',
            'sr_RS@latin': 'sr_RS@latin',
            'sr_RS.UTF-8@latin': 'sr_RS@latin',
            '': 'en',
            None: 'en',
        }.items():
            self.ae(sanitize_lang(raw), expected, f'Failed for: {raw!r}')

    def test_locale_fallbacks(self):
        for raw, expected in {
            'de': ['de'],
            'pt_BR': ['pt_BR', 'pt'],
            # a script variant is more significant than a country
            'sr@latin': ['sr@latin', 'sr'],
            'sr_RS@latin': ['sr_RS@latin', 'sr@latin', 'sr_RS', 'sr'],
        }.items():
            self.ae(locale_fallbacks(raw), expected, f'Failed for: {raw!r}')

    def test_bcp47_locale_name(self):
        for raw, expected in {
            'de_DE': 'de_DE',
            'sr': 'sr',
            'sr@latin': 'sr_Latn',
            'sr_RS@latin': 'sr_Latn_RS',
            'sr@cyrillic': 'sr_Cyrl',
            # a modifier that does not name a script is not a subtag
            'ca@valencia': 'ca',
        }.items():
            self.ae(bcp47_locale_name(raw), expected, f'Failed for: {raw!r}')

    def test_qt_understands_script_variants(self):
        # Qt truncates a locale name at the @, so it must be given the script
        # as a subtag, otherwise sr@latin displays Cyrillic month names.
        try:
            from qt.core import QLocale
        except ImportError:
            self.skipTest('Qt not available')
        self.ae(QLocale(bcp47_locale_name('sr@latin')).bcp47Name(), 'sr-Latn')
        self.ae(QLocale(bcp47_locale_name('sr_RS@latin')).bcp47Name(), 'sr-Latn')
        self.ae(QLocale(bcp47_locale_name('sr')).bcp47Name(), 'sr')


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestLocaleNames)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_tests

    run_tests(find_tests)
