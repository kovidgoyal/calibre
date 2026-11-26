#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""Tests for the css_selectors and css_parser compatibility modules, used by recipes and plugins"""

import os
import shutil
import tempfile
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
        # A Select made from an element returns only elements of its subtree,
        # as in css_selectors, and invalidate_caches() takes changes into account
        sub = Select(lis[0])
        self.assertEqual([a.get('href') for a in sub('a')], ['/1'])
        self.assertTrue(sub.has_matches('span.title'))
        self.assertFalse(sub.has_matches('li + li'))
        lis[0].append(lis[0].makeelement('a', {'href': '/3'}))
        self.assertEqual([a.get('href') for a in sub('a')], ['/1'])
        sub.invalidate_caches()
        self.assertEqual([a.get('href') for a in sub('a')], ['/1', '/3'])
        # An ElementTree works as well as its root
        self.assertEqual(len(tuple(Select(etree.ElementTree(self.root))('li.booklink'))), 2)

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


class TestCSSParserCompat(unittest.TestCase):
    def setUp(self) -> None:
        self.tdir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tdir)

    def test_css_parser(self) -> None:
        import logging

        import css_parser
        from css_parser.css import CSSRule, CSSStyleSheet

        # Code written for css_parser
        css_parser.log.setLevel(logging.CRITICAL)
        css_parser.log.raiseExceptions = False
        sheets = {'base.css': 'b { color: blue }'}
        parser = css_parser.CSSParser(loglevel=logging.CRITICAL, fetcher=lambda url: ('utf-8', sheets[url]) if url in sheets else None)
        sheet = parser.parseString('@import "base.css"; p { font-size: 12pt; background: url(a.png) }', href='main.css')
        self.assertIsInstance(sheet, CSSStyleSheet)
        rules = list(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE))
        self.assertEqual([r.selectorText for r in rules], ['p'])
        rules[0].style.setProperty('font-size', '24pt')
        self.assertEqual(rules[0].style.getPropertyValue('font-size'), '24pt')
        self.assertEqual(list(css_parser.getUrls(sheet)), ['base.css', 'a.png'])
        css_parser.replaceUrls(sheet, lambda url: 'images/' + url, ignoreImportRules=True)
        self.assertEqual(list(css_parser.getUrls(sheet)), ['base.css', 'images/a.png'])
        resolved = css_parser.resolveImports(sheet)
        self.assertIn(b'color: blue', resolved.cssText)
        style = css_parser.parseStyle('color: red; margin: 0')
        self.assertEqual(style.getCssText(separator=' '), 'color: red; margin: 0')

        # Settings that are accepted and ignored
        css_parser.log.setLog(logging.getLogger('x'))
        css_parser.ser.prefs.indent = '\t'
        css_parser.ser.prefs.useMinified()
        css_parser.profile.addProfile('x', {})

        # Other modules and names that plugins used
        from css_parser.css import MarginRule
        from css_parser.css.value import PropertyValue, Value
        from css_parser.stylesheets import MediaList

        self.assertTrue(MarginRule and PropertyValue and Value and MediaList)
        self.assertTrue(css_parser.profile.validate('margin-top', '1em'))
        self.assertFalse(css_parser.profile.validate('margin-top', 'red'))
        # Properties that kgcss has no grammar for are valid
        self.assertTrue(css_parser.profile.validate('color', 'red'))
        self.assertEqual(css_parser.profile.validateWithProfile('border-top-style', 'dotted')[0], True)
        path = os.path.join(self.tdir, 'a.css')
        with open(path, 'w') as f:
            f.write('@import "base.css"; a { color: red }')
        sheet = css_parser.parseFile(path)
        self.assertEqual([r.selectorText for r in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE)], ['a'])


def find_tests() -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    return unittest.TestSuite(loader.loadTestsFromTestCase(x) for x in (TestCSSSelectorsCompat, TestCSSParserCompat))
