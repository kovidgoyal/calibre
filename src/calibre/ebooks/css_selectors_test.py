#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""Tests for the css_selectors compatibility module, used by recipes and plugins"""

import unittest

from html5_parser import parse
from lxml import etree


class TestCSSSelectorsCompat(unittest.TestCase):
    def setUp(self) -> None:
        self.root = parse(
            '<html><body><ul>'
            '<li class="BookLink" id="First"><a class="link" href="/1">One</a><span class="title">T1</span></li>'
            '<li class="booklink"><a class="link" href="/2">Two</a></li>'
            '</ul><p lang="en-GB">x</p></body></html>',
            namespace_elements=False,
        )

    def test_select(self) -> None:
        from css_selectors import Select

        select = Select(self.root)
        # Ids and classes match case-insensitively, as they did in css_selectors
        self.assertEqual(len(tuple(select('li.booklink'))), 2)
        self.assertEqual(next(select('#first')).get('class'), 'BookLink')
        self.assertTrue(select.has_matches('LI.BOOKLINK > A.LINK'))
        # Selecting under an element, as the store plugins do
        lis = tuple(select('li.booklink'))
        self.assertEqual([a.get('href') for li in lis for a in select('a.link', li)], ['/1', '/2'])
        self.assertEqual([a.get('href') for a in select('a.link', root=lis[1])], ['/2'])
        self.assertEqual(etree.tostring(next(select('span.title', lis[0])), method='text', encoding='unicode'), 'T1')
        with self.assertRaises(StopIteration):
            next(select('span.title', lis[1]))
        self.assertEqual(len(tuple(select('p:lang(en)'))), 1)

    def test_signature(self) -> None:
        from css_selectors import ExpressionError, Select

        # The arguments of css_selectors' Select, by position and name
        select = Select(self.root, None, True)
        self.assertEqual(len(tuple(select('a:hover'))), 2)
        select = Select(self.root, default_lang='en', ignore_inappropriate_pseudo_classes=True, dispatch_map={}, trace=True)
        self.assertEqual(len(tuple(select('a:hover'))), 2)
        select = Select(self.root)
        with self.assertRaises(ExpressionError):
            tuple(select('a:hover'))

    def test_errors(self) -> None:
        from css_selectors import INAPPROPRIATE_PSEUDO_CLASSES, ExpressionError, Select, SelectorError, SelectorSyntaxError

        self.assertTrue(issubclass(SelectorSyntaxError, SelectorError))
        self.assertTrue(issubclass(ExpressionError, SelectorError))
        self.assertTrue(issubclass(SelectorError, ValueError))
        self.assertIn('hover', INAPPROPRIATE_PSEUDO_CLASSES)
        it = Select(self.root)('a[x!=y]')
        # Errors are raised when the generator is first advanced
        with self.assertRaises(SelectorSyntaxError):
            next(it)

    def test_parse(self) -> None:
        from css_selectors import SelectorSyntaxError, parse

        self.assertEqual([s.specificity for s in parse('#a .b c, p::before')], [(1, 1, 1), (0, 0, 2)])
        with self.assertRaises(SelectorSyntaxError):
            parse('p..x')


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCSSSelectorsCompat)
