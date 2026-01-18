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
        test_translator(self, 'und', b'')
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
    n = Translator(data) if data else Translator()
    o = gettext.GNUTranslations(io.BytesIO(data)) if data else gettext.NullTranslations()
    which = f'{lang} - {q}'
    self.assertEqual(o.info(), n.info(), f'info() not equal for language: {which}')
    self.assertEqual(o.charset(), n.charset(), f'charset() not equal for language: {which}')
    if hasattr(o, 'plural'):
        pf = o.info().get('plural-forms')
        for i in range(1, 100):
            self.assertEqual(o.plural(i), n.plural(i), f'plural({i}) not equal for language: {which} and plural-form: {pf}')
    if q == 'messages.mo':
        og, ng = o.gettext, n.gettext
        for x in ('Add books', 'Series', 'Tags', 'Folder'):
            if lang == 'ar' and x == 'Folder':
                # this is a bug in the python stdlib implementation of gettext() where it
                # returns msgstr[plural(1)] instead of msgstr[0] for gettext().
                # In the Arabic translation plural(1) == 1 instead of 0
                continue
            self.assertEqual(og(x), ng(x), f'gettext({x!r}) not equal for language: {which}')
        og, ng = o.ngettext, n.ngettext
        for singular, plural in (('Series', 'Series'), ('Folder', 'Folders')):
            for i in range(1, 10):
                self.assertEqual(og(singular, plural, i), ng(singular, plural, i), f'ngettext({singular!r}, {plural!r}, {i}) not equal for language: {which}')
        og, ng = o.pgettext, n.pgettext
        for context, msg in (('edit book actions', 'Miscellaneous'), ('edit book file type', 'Miscellaneous')):
            self.assertEqual(og(context, msg), ng(context, msg), f'pgettext({context!r}, {msg!r}) not equal for language: {which}')


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestTranslator)
