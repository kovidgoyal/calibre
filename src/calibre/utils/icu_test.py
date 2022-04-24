#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import unittest, sys
from contextlib import contextmanager

import calibre.utils.icu as icu
from polyglot.builtins import iteritems, cmp


@contextmanager
def make_collation_func(name, locale, numeric=True, maker=icu.make_sort_key_func, func='strcmp'):
    def coll():
        ans = icu._icu.Collator(locale)
        ans.numeric = numeric
        return ans

    yield maker(coll, func)


class TestICU(unittest.TestCase):

    ae = unittest.TestCase.assertEqual
    ane= unittest.TestCase.assertNotEqual

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
        with make_collation_func('dsk', 'de', maker=icu.make_sort_key_func, func='sort_key') as dsk:
            self.ae(german_good, sorted(german, key=dsk))
            with make_collation_func('dcmp', 'de', maker=icu.make_two_arg_func, func='strcmp') as dcmp:
                for x in german:
                    for y in german:
                        self.ae(cmp(dsk(x), dsk(y)), dcmp(x, y))

        with make_collation_func('fsk', 'fr', maker=icu.make_sort_key_func, func='sort_key') as fsk:
            self.ae(french_good, sorted(french, key=fsk))
            with make_collation_func('fcmp', 'fr', maker=icu.make_two_arg_func) as fcmp:
                for x in french:
                    for y in french:
                        self.ae(cmp(fsk(x), fsk(y)), fcmp(x, y))

        with make_collation_func('ssk', 'es', maker=icu.make_sort_key_func, func='sort_key') as ssk:
            self.assertNotEqual(ssk('peña'), ssk('pena'))
            with make_collation_func('scmp', 'es', maker=icu.make_two_arg_func) as scmp:
                self.assertNotEqual(0, scmp('pena', 'peña'))

        for k, v in iteritems({'pèché': 'peche', 'flüße':'Flusse', 'Štepánek':'ŠtepaneK'}):
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
        for x in ('', None, False, 1):
            self.ae(x, icu.capitalize(x))

        for x in ('a', 'Alice\'s code', 'macdonald\'s machIne', '02 the wars'):
            self.ae(icu.upper(x), x.upper())
            self.ae(icu.lower(x), x.lower())
            # ICU's title case algorithm is different from ours, when there are
            # capitals inside words
            self.ae(icu.title_case(x), titlecase(x).replace('machIne', 'Machine'))
            self.ae(icu.capitalize(x), x[0].upper() + x[1:].lower())
            self.ae(icu.swapcase(x), x.swapcase())

    def test_find(self):
        ' Test searching for substrings '
        self.ae((1, 1), icu.find(b'a', b'1ab'))
        self.ae((1, 1), icu.find('\U0001f431', 'x\U0001f431x'))
        self.ae((1, 1), icu.find('y', '\U0001f431y'))
        self.ae((0, 4), icu.primary_find('pena', 'peña'))
        for k, v in iteritems({'pèché': 'peche', 'flüße':'Flusse', 'Štepánek':'ŠtepaneK'}):
            self.ae((1, len(k)), icu.primary_find(v, ' ' + k), f'Failed to find {v} in {k}')
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
        x = icu.primary_collator()
        self.ae(x.get_attribute(icu._icu.UCOL_STRENGTH), icu._icu.UCOL_PRIMARY),
        self.ae((0, 4), icu.primary_no_punc_find('pena"', 'peña'))
        self.ae((0, 13), icu.primary_no_punc_find("typographers", 'typographer’s'))
        self.ae((0, 7), icu.primary_no_punc_find('abcd', 'a\u00adb\u200cc\u200dd'))
        self.ae((0, 5), icu.primary_no_punc_find('abcd', 'ab cd'))
        # test find all
        m = []
        a = lambda p,l : m.append((p, l))
        icu.primary_collator_without_punctuation().find_all('a', 'a a🐱a', a)
        self.ae(m, [(0, 1), (2, 1), (5, 1)])
        # test find whole words
        c = icu.primary_collator_without_punctuation()
        self.ae(c.find('a', 'abc a bc'), (0, 1))
        self.ae(c.find('a', 'abc a bc', True), (4, 1))
        self.ae(c.find('pena', 'a peñaabc peña', True), (10, 4))

    def test_collation_order(self):
        'Testing collation ordering'
        for group in [
            (self.ae,  ('Šaa', 'Smith', 'Solženicyn', 'Štepánek')),
            (self.ae,  ('11', '011')),
            (self.ane, ('2', '1')),
            (self.ae,  ('100 Smith', '0100 Smith')),
        ]:
            last = None
            assert_func = group[0]
            for x in group[1]:
                order, _ = icu.numeric_collator().collation_order(x)
                if last is not None:
                    assert_func(last, order, f'Order for {x} not correct: {last} != {order}')
                last = order

        self.ae(dict(icu.partition_by_first_letter(['A1', '', 'a1', '\U0001f431', '\U0001f431x'])),
                {' ':[''], 'A':['A1', 'a1'], '\U0001f431':['\U0001f431', '\U0001f431x']})

    def test_collation_order_for_partitioning(self):
        'Testing collation ordering for partitioning'
        for group in [
            (self.ae, ('Smith', 'Šaa', 'Solženicyn', 'Štepánek')),
            (self.ane, ('11', '011')),
            (self.ae, ('102 Smith', '100 Smith')),
            (self.ane, ('100 Smith', '0100 Smith')),
        ]:
            last = None
            assert_func = group[0]
            for x in group[1]:
                order, _ = icu.non_numeric_sort_collator().collation_order(x)
                if last is not None:
                    assert_func(last, order, f'Order for {x} not correct: {last} != {order}')
                last = order

        self.ae(dict(icu.partition_by_first_letter(['A1', '', 'a1', '\U0001f431', '\U0001f431x'])),
                {' ':[''], 'A':['A1', 'a1'], '\U0001f431':['\U0001f431', '\U0001f431x']})

    def test_roundtrip(self):
        ' Test roundtripping '
        for r in ('xxx\0\u2219\U0001f431xxx', '\0', '', 'simple'):
            self.ae(r, icu._icu.roundtrip(r))
        self.ae(icu._icu.roundtrip('\ud8e81'), '\ufffd1')
        self.ae(icu._icu.roundtrip('\udc01\ud8e8'), '\ufffd\ufffd')
        for x, l in [('', 0), ('a', 1), ('\U0001f431', 1)]:
            self.ae(icu._icu.string_length(x), l)
        for x, l in [('', 0), ('a', 1), ('\U0001f431', 2)]:
            self.ae(icu._icu.utf16_length(x), l)
        self.ae(icu._icu.chr(0x1f431), '\U0001f431')
        self.ae(icu._icu.ord_string('abc'*100), tuple(map(ord, 'abc'*100)))
        self.ae(icu._icu.ord_string('\U0001f431'), (0x1f431,))

    def test_character_name(self):
        ' Test character naming '
        from calibre.utils.unicode_names import character_name_from_code
        for q, e in {
                '\U0001f431': 'CAT FACE'
                }.items():
            self.ae(icu.character_name(q), e)
            self.ae(character_name_from_code(icu.ord_string(q)[0]), e)

    def test_contractions(self):
        ' Test contractions '
        self.skipTest('Skipping as this depends too much on ICU version')
        c = icu._icu.Collator('cs')
        self.ae(icu.contractions(c), frozenset({'Z\u030c', 'z\u030c', 'Ch',
            'C\u030c', 'ch', 'cH', 'c\u030c', 's\u030c', 'r\u030c', 'CH',
            'S\u030c', 'R\u030c'}))

    def test_break_iterator(self):
        ' Test the break iterator '
        from calibre.spell.break_iterator import split_into_words as split, index_of, split_into_words_and_positions, count_words
        for q in ('one two three', ' one two three', 'one\ntwo  three ', ):
            self.ae(split(str(q)), ['one', 'two', 'three'], 'Failed to split: %r' % q)
        self.ae(split('I I\'m'), ['I', "I'm"])
        self.ae(split('out-of-the-box'), ['out-of-the-box'])
        self.ae(split('-one two-'), ['-one', 'two-'])
        self.ae(split('-one a-b-c-d e'), ['-one', 'a-b-c-d', 'e'])
        self.ae(split('-one -a-b-c-d- e'), ['-one', '-a-b-c-d-', 'e'])
        self.ae(split_into_words_and_positions('one \U0001f431 three'), [(0, 3), (6, 5)])
        self.ae(count_words('a b c d e f'), 6)
        for needle, haystack, pos in (
                ('word', 'a word b', 2),
                ('word', 'a word', 2),
                ('one-two', 'a one-two punch', 2),
                ('one-two', 'one-two punch', 0),
                ('one-two', 'one-two', 0),
                ('one', 'one-two one', 8),
                ('one-two', 'one-two-three one-two', 14),
                ('one', 'onet one', 5),
                ('two', 'one-two two', 8),
                ('two', 'two-one two', 8),
                ('-two', 'one-two -two', 8),
                ('-two', 'two', -1),
                ('i', 'i', 0),
                ('i', 'six i', 4),
                ('i', '', -1), ('', '', -1), ('', 'i', -1),
                ('i', 'six clicks', -1),
                ('i', '\U0001f431 i', 2),
                ('-a', 'b -a', 2),
                ('a-', 'a-b a- d', 4),
                ('-a-', 'b -a -a-', 5),
                ('-a-', '-a-', 0),
                ('-a-', 'a-', -1),
                ('-a-', '-a', -1),
                ('-a-', 'a', -1),
                ('a-', 'a-', 0),
                ('-a', '-a', 0),
                ('a-b-c-', 'a-b-c-d', -1),
                ('a-b-c-', 'a-b-c-.', 0),
                ('a-b-c-', 'a-b-c-d a-b-c- d', 8),
        ):
            fpos = index_of(needle, haystack)
            self.ae(pos, fpos, 'Failed to find index of %r in %r (%d != %d)' % (needle, haystack, pos, fpos))

    def test_remove_accents(self):
        for func in (icu.remove_accents_icu, icu.remove_accents_regex):
            for q, expected in {
                'MännÄr': 'MannAr', 'Peña': 'Pena', 'Kátia': 'Katia',
                'Málaga': 'Malaga', 'François': 'Francois', 'Phút Hơn': 'Phut Hon',
                '中文':'中文'
            }.items():
                self.ae(expected, func(q))


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestICU)


class TestRunner(unittest.main):

    def createTests(self):
        self.test = find_tests()


def run(verbosity=4):
    TestRunner(verbosity=verbosity, exit=False)


def test_build():
    result = TestRunner(verbosity=0, buffer=True, catchbreak=True, failfast=True, argv=sys.argv[:1], exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    run(verbosity=4)
