#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import gettext
import io
import unittest
import zipfile

from calibre.utils.localization import available_translations, get_lc_messages_path
from calibre_extensions.translator import Translator


class TestTranslator(unittest.TestCase):

    def test_translator(self):
        with zipfile.ZipFile(P('localization/locales.zip', allow_user_override=False), 'r') as zf:
            for lang in available_translations():
                mpath = get_lc_messages_path(lang)
                if mpath is not None:
                    data = zf.read(mpath + '/messages.mo')
                    test_translator(self, lang, data)
                    for q in ('iso639.mo', 'iso3166.mo'):
                        try:
                            data = zf.read(mpath + '/' + q)
                        except KeyError:
                            continue
                        test_translator(self, lang, data, q)


def test_translator(self: TestTranslator, lang: str, data: bytes, q: str = 'messages.mo') -> None:
    n = Translator(data)
    o = gettext.GNUTranslations(io.BytesIO(data))
    which = f'{lang} - {q}'
    self.assertEqual(o.info(), n.info(), f'info() not equal for language: {which}')
    self.assertEqual(o.charset(), n.charset(), f'charset() not equal for language: {which}')
    pf = o.info().get('plural-forms')
    for i in range(1, 100):
        self.assertEqual(o.plural(i), n.plural(i), f'plural({i}) not equal for language: {which} and plural-form: {pf}')


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestTranslator)
