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


def test_translator(self: TestTranslator, lang: str, data: bytes) -> None:
    n = Translator(data)
    o = gettext.GNUTranslations(io.BytesIO(data))
    for i in range(1, 100):
        self.assertEqual(o.plural(i), n.plural(i), f'plural() not equal for language: {lang}')


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestTranslator)
