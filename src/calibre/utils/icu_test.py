#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import unittest, sys
from contextlib import contextmanager

import calibre.utils.icu as icu


@contextmanager
def make_collation_func(name, locale, numeric=True, template='_sort_key_template', func='strcmp'):
    c = icu._icu.Collator(locale)
    cname = '%s_test_collator%s' % (name, template)
    setattr(icu, cname, c)
    c.numeric = numeric
    yield icu._make_func(getattr(icu, template), name, collator=cname, collator_func='not_used_xxx', func=func)
    delattr(icu, cname)

class TestICU(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def setUp(self):
        icu.change_locale('en')

    def test_sorting(self):
        ' Test the various sorting APIs '
        german = '''Sonntag Montag Dienstag Januar Februar März Fuße Fluße Flusse flusse fluße flüße flüsse'''.split()
        german_good = '''Dienstag Februar flusse Flusse fluße Fluße flüsse flüße Fuße Januar März Montag Sonntag'''.split()
        french = '''dimanche lundi mardi janvier février mars déjà Meme deja même dejà bpef bœg Boef Mémé bœf boef bnef pêche pèché pêché pêche pêché'''.split()
        french_good = '''bnef boef Boef bœf bœg bpef deja dejà déjà dimanche février janvier lundi mardi mars Meme Mémé même pèché pêche pêche pêché pêché'''.split()  # noqa

        # Test corner cases
        sort_key = icu.sort_key
        s = '\U0001f431'
        self.ae(sort_key(s), sort_key(s.encode(sys.getdefaultencoding())), 'UTF-8 encoded object not correctly decoded to generate sort key')
        self.ae(s.encode('utf-16'), s.encode('utf-16'), 'Undecodable bytestring not returned as itself')
        self.ae(b'', sort_key(None))
        self.ae(0, icu.strcmp(None, b''))
        self.ae(0, icu.strcmp(s, s.encode(sys.getdefaultencoding())))

        # Test locales
        with make_collation_func('dsk', 'de', func='sort_key') as dsk:
            self.ae(german_good, sorted(german, key=dsk))
            with make_collation_func('dcmp', 'de', template='_strcmp_template') as dcmp:
                for x in german:
                    for y in german:
                        self.ae(cmp(dsk(x), dsk(y)), dcmp(x, y))

        with make_collation_func('fsk', 'fr', func='sort_key') as fsk:
            self.ae(french_good, sorted(french, key=fsk))
            with make_collation_func('fcmp', 'fr', template='_strcmp_template') as fcmp:
                for x in french:
                    for y in french:
                        self.ae(cmp(fsk(x), fsk(y)), fcmp(x, y))

        with make_collation_func('ssk', 'es', func='sort_key') as ssk:
            self.assertNotEqual(ssk('peña'), ssk('pena'))
            with make_collation_func('scmp', 'es', template='_strcmp_template') as scmp:
                self.assertNotEqual(0, scmp('pena', 'peña'))

        for k, v in {u'pèché': u'peche', u'flüße':u'Flusse', u'Štepánek':u'ŠtepaneK'}.iteritems():
            self.ae(0, icu.primary_strcmp(k, v))

        # Test different types of collation
        self.ae(icu.primary_sort_key('Aä'), icu.primary_sort_key('aa'))
        self.assertLess(icu.numeric_sort_key('something 2'), icu.numeric_sort_key('something 11'))
        self.assertLess(icu.case_sensitive_sort_key('A'), icu.case_sensitive_sort_key('a'))
        self.ae(0, icu.strcmp('a', 'A'))
        self.ae(cmp('a', 'A'), icu.case_sensitive_strcmp('a', 'A'))
        self.ae(0, icu.primary_strcmp('ä', 'A'))

    def test_change_case(self):
        ' Test the various ways of changing the case '
        from calibre.utils.titlecase import titlecase
        # Test corner cases
        self.ae('A', icu.upper(b'a'))

        for x in ('a', 'Alice\'s code', 'macdonald\'s machIne', '02 the wars'):
            self.ae(icu.upper(x), x.upper())
            self.ae(icu.lower(x), x.lower())
            # ICU's title case algorithm is different from ours, when there are
            # capitals inside words
            self.ae(icu.title_case(x), titlecase(x).replace('machIne', 'Machine'))
            self.ae(icu.capitalize(x), x[0].upper() + x[1:].lower())

    def test_find(self):
        ' Test searching for substrings '
        self.ae((1, 1), icu.find(b'a', b'1ab'))
        self.ae((1, 1 if sys.maxunicode >= 0x10ffff else 2), icu.find('\U0001f431', 'x\U0001f431x'))
        self.ae((1 if sys.maxunicode >= 0x10ffff else 2, 1), icu.find('y', '\U0001f431y'))
        self.ae((0, 4), icu.primary_find('pena', 'peña'))
        for k, v in {u'pèché': u'peche', u'flüße':u'Flusse', u'Štepánek':u'ŠtepaneK'}.iteritems():
            self.ae((1, len(k)), icu.primary_find(v, ' ' + k), 'Failed to find %s in %s' % (v, k))
        self.assertTrue(icu.startswith(b'abc', b'ab'))
        self.assertTrue(icu.startswith('abc', 'abc'))
        self.assertFalse(icu.startswith('xyz', 'a'))
        self.assertTrue(icu.startswith('xxx', ''))
        self.assertTrue(icu.primary_startswith('pena', 'peña'))
        self.assertTrue(icu.contains('\U0001f431', '\U0001f431'))
        self.assertTrue(icu.contains('something', 'some other something else'))
        self.assertTrue(icu.contains('', 'a'))
        self.assertTrue(icu.contains('', ''))
        self.assertFalse(icu.contains('xxx', 'xx'))
        self.assertTrue(icu.primary_contains('pena', 'peña'))

    def test_collation_order(self):
        'Testing collation ordering'
        for group in [
            ('Šaa', 'Smith', 'Solženicyn', 'Štepánek'),
            ('01', '1'),
            ('1', '11', '13'),
        ]:
            last = None
            for x in group:
                order, length = icu.numeric_collator().collation_order(x)
                if last is not None:
                    self.ae(last, order)
                last = order

    def test_roundtrip(self):
        for r in (u'xxx\0\u2219\U0001f431xxx', u'\0', u'', u'simple'):
            self.ae(r, icu._icu.roundtrip(r))

    def test_character_name(self):
        self.ae(icu.character_name('\U0001f431'), 'CAT FACE')

    def test_contractions(self):
        c = icu._icu.Collator('cs')
        self.ae(icu.contractions(c), frozenset({u'Z\u030c', u'z\u030c', u'Ch',
            u'C\u030c', u'ch', u'cH', u'c\u030c', u's\u030c', u'r\u030c', u'CH',
            u'S\u030c', u'R\u030c'}))

class TestRunner(unittest.main):

    def createTests(self):
        tl = unittest.TestLoader()
        self.test = tl.loadTestsFromTestCase(TestICU)

def run(verbosity=4):
    TestRunner(verbosity=verbosity, exit=False)

def test_build():
    result = TestRunner(verbosity=0, buffer=True, catchbreak=True, failfast=True, argv=sys.argv[:1], exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)

if __name__ == '__main__':
    run(verbosity=4)

