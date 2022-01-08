#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import unittest

from calibre.ebooks.metadata import author_to_author_sort, remove_bracketed_text
from calibre.utils.config_base import Tweak, tweaks


class TestRemoveBracketedText(unittest.TestCase):
    def test_brackets(self):
        self.assertEqual(remove_bracketed_text('a[b]c(d)e{f}g<h>i'), 'aceg<h>i')

    def test_nested(self):
        self.assertEqual(remove_bracketed_text('a[[b]c(d)e{f}]g(h(i)j[k]l{m})n{{{o}}}p'), 'agnp')

    def test_mismatched(self):
        self.assertEqual(remove_bracketed_text('a[b(c]d)e'), 'ae')
        self.assertEqual(remove_bracketed_text('a{b(c}d)e'), 'ae')

    def test_extra_closed(self):
        self.assertEqual(remove_bracketed_text('a]b}c)d'), 'abcd')
        self.assertEqual(remove_bracketed_text('a[b]c]d(e)f{g)h}i}j)k]l'), 'acdfijkl')

    def test_unclosed(self):
        self.assertEqual(remove_bracketed_text('a]b[c'), 'ab')
        self.assertEqual(remove_bracketed_text('a(b[c]d{e}f'), 'a')
        self.assertEqual(remove_bracketed_text('a{b}c{d[e]f(g)h'), 'ac')


class TestAuthorToAuthorSort(unittest.TestCase):
    def check_all_methods(self, name, invert=None, comma=None,
                            nocomma=None, copy=None):
        methods = ('invert', 'copy', 'comma', 'nocomma')
        if invert is None:
            invert = name
        if comma is None:
            comma = invert
        if nocomma is None:
            nocomma = comma
        if copy is None:
            copy = name
        results = (invert, copy, comma, nocomma)
        for method, result in zip(methods, results):
            self.assertEqual(author_to_author_sort(name, method), result)

    def test_single(self):
        self.check_all_methods('Aristotle')

    def test_all_prefix(self):
        self.check_all_methods('Mr. Dr Prof.')

    def test_all_suffix(self):
        self.check_all_methods('Senior Inc')

    def test_copywords(self):
        self.check_all_methods('Don "Team" Smith',
                                invert='Smith, Don "Team"',
                                nocomma='Smith Don "Team"')
        self.check_all_methods('Don Team Smith')

    def test_national(self):
        c = tweaks['author_name_copywords']
        try:
            # Assume that 'author_name_copywords' is a common sequence type
            i = c.index('National')
        except ValueError:
            # If "National" not found, check first without, then temporarily add
            self.check_all_methods('National Lampoon',
                                    invert='Lampoon, National',
                                    nocomma='Lampoon National')
            t = type(c)
            with Tweak('author_name_copywords', c + t(['National'])):
                self.check_all_methods('National Lampoon')
        else:
            # If "National" found, check with, then temporarily remove
            self.check_all_methods('National Lampoon')
            with Tweak('author_name_copywords', c[:i] + c[i + 1:]):
                self.check_all_methods('National Lampoon',
                                        invert='Lampoon, National',
                                        nocomma='Lampoon National')

    def test_method(self):
        self.check_all_methods('Jane Doe',
                                invert='Doe, Jane',
                                nocomma='Doe Jane')

    def test_invalid_methos(self):
        # Invalid string defaults to invert
        name = 'Jane, Q. van Doe[ed] Jr.'
        self.assertEqual(author_to_author_sort(name, 'invert'),
                            author_to_author_sort(name, '__unknown__!(*T^U$'))

    def test_prefix_suffix(self):
        self.check_all_methods('Mrs. Jane Q. Doe III',
                                invert='Doe, Jane Q. III',
                                nocomma='Doe Jane Q. III')

    def test_surname_prefix(self):
        with Tweak('author_use_surname_prefixes', True):
            self.check_all_methods('Leonardo Da Vinci',
                                    invert='Da Vinci, Leonardo',
                                    nocomma='Da Vinci Leonardo')
            self.check_all_methods('Van Gogh')
            self.check_all_methods('Van')
        with Tweak('author_use_surname_prefixes', False):
            self.check_all_methods('Leonardo Da Vinci',
                                    invert='Vinci, Leonardo Da',
                                    nocomma='Vinci Leonardo Da')
            self.check_all_methods('Van Gogh',
                                    invert='Gogh, Van',
                                    nocomma='Gogh Van')

    def test_comma(self):
        self.check_all_methods('James Wesley, Rawles',
                                invert='Rawles, James Wesley,',
                                comma='James Wesley, Rawles',
                                nocomma='Rawles James Wesley,')

    def test_brackets(self):
        self.check_all_methods('Seventh Author [7]',
                                invert='Author, Seventh',
                                nocomma='Author Seventh')
        self.check_all_methods('John [x]von Neumann (III)',
                                invert='Neumann, John von',
                                nocomma='Neumann John von')

    def test_falsy(self):
        self.check_all_methods('')
        self.check_all_methods(None, '', '', '', '')
        self.check_all_methods([], '', '', '', '')


def find_tests():
    ans = unittest.defaultTestLoader.loadTestsFromTestCase(TestRemoveBracketedText)
    ans.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestAuthorToAuthorSort))
    return ans
