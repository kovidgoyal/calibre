#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import unittest, sys, argparse

from css_selectors.errors import SelectorSyntaxError
from css_selectors.parse import tokenize, parse

class TestCSSSelectors(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def test_tokenizer(self):  # {{{
        tokens = [
            type('')(item) for item in tokenize(
                r'E\ é > f [a~="y\"x"]:nth(/* fu /]* */-3.7)')]
        self.ae(tokens, [
            "<IDENT 'E é' at 0>",
            "<S ' ' at 4>",
            "<DELIM '>' at 5>",
            "<S ' ' at 6>",
            # the no-break space is not whitespace in CSS
            "<IDENT 'f ' at 7>",  # f\xa0
            "<DELIM '[' at 9>",
            "<IDENT 'a' at 10>",
            "<DELIM '~' at 11>",
            "<DELIM '=' at 12>",
            "<STRING 'y\"x' at 13>",
            "<DELIM ']' at 19>",
            "<DELIM ':' at 20>",
            "<IDENT 'nth' at 21>",
            "<DELIM '(' at 24>",
            "<NUMBER '-3.7' at 37>",
            "<DELIM ')' at 41>",
            "<EOF at 42>",
        ])
    # }}}

    def test_parser(self):  # {{{
        def repr_parse(css):
            selectors = parse(css)
            for selector in selectors:
                assert selector.pseudo_element is None
            return [repr(selector.parsed_tree).replace("(u'", "('")
                    for selector in selectors]

        def parse_many(first, *others):
            result = repr_parse(first)
            for other in others:
                assert repr_parse(other) == result
            return result

        assert parse_many('*') == ['Element[*]']
        assert parse_many('*|*') == ['Element[*]']
        assert parse_many('*|foo') == ['Element[foo]']
        assert parse_many('foo|*') == ['Element[foo|*]']
        assert parse_many('foo|bar') == ['Element[foo|bar]']
        # This will never match, but it is valid:
        assert parse_many('#foo#bar') == ['Hash[Hash[Element[*]#foo]#bar]']
        assert parse_many(
            'div>.foo',
            'div> .foo',
            'div >.foo',
            'div > .foo',
            'div \n>  \t \t .foo', 'div\r>\n\n\n.foo', 'div\f>\f.foo'
        ) == ['CombinedSelector[Element[div] > Class[Element[*].foo]]']
        assert parse_many('td.foo,.bar',
            'td.foo, .bar',
            'td.foo\t\r\n\f ,\t\r\n\f .bar'
        ) == [
            'Class[Element[td].foo]',
            'Class[Element[*].bar]'
        ]
        assert parse_many('div, td.foo, div.bar span') == [
            'Element[div]',
            'Class[Element[td].foo]',
            'CombinedSelector[Class[Element[div].bar] '
            '<followed> Element[span]]']
        assert parse_many('div > p') == [
            'CombinedSelector[Element[div] > Element[p]]']
        assert parse_many('td:first') == [
            'Pseudo[Element[td]:first]']
        assert parse_many('td:first') == [
            'Pseudo[Element[td]:first]']
        assert parse_many('td :first') == [
            'CombinedSelector[Element[td] '
            '<followed> Pseudo[Element[*]:first]]']
        assert parse_many('td :first') == [
            'CombinedSelector[Element[td] '
            '<followed> Pseudo[Element[*]:first]]']
        assert parse_many('a[name]', 'a[ name\t]') == [
            'Attrib[Element[a][name]]']
        assert parse_many('a [name]') == [
            'CombinedSelector[Element[a] <followed> Attrib[Element[*][name]]]']
        self.ae(parse_many('a[rel="include"]', 'a[rel = include]'), [
            "Attrib[Element[a][rel = 'include']]"])
        assert parse_many("a[hreflang |= 'en']", "a[hreflang|=en]") == [
            "Attrib[Element[a][hreflang |= 'en']]"]
        self.ae(parse_many('div:nth-child(10)'), [
            "Function[Element[div]:nth-child(['10'])]"])
        assert parse_many(':nth-child(2n+2)') == [
            "Function[Element[*]:nth-child(['2', 'n', '+2'])]"]
        assert parse_many('div:nth-of-type(10)') == [
            "Function[Element[div]:nth-of-type(['10'])]"]
        assert parse_many('div div:nth-of-type(10) .aclass') == [
            'CombinedSelector[CombinedSelector[Element[div] <followed> '
            "Function[Element[div]:nth-of-type(['10'])]] "
            '<followed> Class[Element[*].aclass]]']
        assert parse_many('label:only') == [
            'Pseudo[Element[label]:only]']
        assert parse_many('a:lang(fr)') == [
            "Function[Element[a]:lang(['fr'])]"]
        assert parse_many('div:contains("foo")') == [
            "Function[Element[div]:contains(['foo'])]"]
        assert parse_many('div#foobar') == [
            'Hash[Element[div]#foobar]']
        assert parse_many('div:not(div.foo)') == [
            'Negation[Element[div]:not(Class[Element[div].foo])]']
        assert parse_many('td ~ th') == [
            'CombinedSelector[Element[td] ~ Element[th]]']
    # }}}

    def test_pseudo_elements(self):  # {{{
        def parse_pseudo(css):
            result = []
            for selector in parse(css):
                pseudo = selector.pseudo_element
                pseudo = type('')(pseudo) if pseudo else pseudo
                # No Symbol here
                assert pseudo is None or isinstance(pseudo, type(''))
                selector = repr(selector.parsed_tree).replace("(u'", "('")
                result.append((selector, pseudo))
            return result

        def parse_one(css):
            result = parse_pseudo(css)
            assert len(result) == 1
            return result[0]

        assert parse_one('foo') == ('Element[foo]', None)
        assert parse_one('*') == ('Element[*]', None)
        assert parse_one(':empty') == ('Pseudo[Element[*]:empty]', None)

        # Special cases for CSS 2.1 pseudo-elements
        assert parse_one(':BEfore') == ('Element[*]', 'before')
        assert parse_one(':aftER') == ('Element[*]', 'after')
        assert parse_one(':First-Line') == ('Element[*]', 'first-line')
        assert parse_one(':First-Letter') == ('Element[*]', 'first-letter')

        assert parse_one('::befoRE') == ('Element[*]', 'before')
        assert parse_one('::AFter') == ('Element[*]', 'after')
        assert parse_one('::firsT-linE') == ('Element[*]', 'first-line')
        assert parse_one('::firsT-letteR') == ('Element[*]', 'first-letter')

        assert parse_one('::text-content') == ('Element[*]', 'text-content')
        self.ae(parse_one('::attr(name)'), (
            "Element[*]", "FunctionalPseudoElement[::attr(['name'])]"))

        assert parse_one('::Selection') == ('Element[*]', 'selection')
        assert parse_one('foo:after') == ('Element[foo]', 'after')
        assert parse_one('foo::selection') == ('Element[foo]', 'selection')
        assert parse_one('lorem#ipsum ~ a#b.c[href]:empty::selection') == (
            'CombinedSelector[Hash[Element[lorem]#ipsum] ~ '
            'Pseudo[Attrib[Class[Hash[Element[a]#b].c][href]]:empty]]',
            'selection')

        parse_pseudo('foo:before, bar, baz:after') == [
            ('Element[foo]', 'before'),
            ('Element[bar]', None),
            ('Element[baz]', 'after')]
    # }}}

    def test_specificity(self):  # {{{
        def specificity(css):
            selectors = parse(css)
            assert len(selectors) == 1
            return selectors[0].specificity()

        assert specificity('*') == (0, 0, 0)
        assert specificity(' foo') == (0, 0, 1)
        assert specificity(':empty ') == (0, 1, 0)
        assert specificity(':before') == (0, 0, 1)
        assert specificity('*:before') == (0, 0, 1)
        assert specificity(':nth-child(2)') == (0, 1, 0)
        assert specificity('.bar') == (0, 1, 0)
        assert specificity('[baz]') == (0, 1, 0)
        assert specificity('[baz="4"]') == (0, 1, 0)
        assert specificity('[baz^="4"]') == (0, 1, 0)
        assert specificity('#lipsum') == (1, 0, 0)

        assert specificity(':not(*)') == (0, 0, 0)
        assert specificity(':not(foo)') == (0, 0, 1)
        assert specificity(':not(.foo)') == (0, 1, 0)
        assert specificity(':not([foo])') == (0, 1, 0)
        assert specificity(':not(:empty)') == (0, 1, 0)
        assert specificity(':not(#foo)') == (1, 0, 0)

        assert specificity('foo:empty') == (0, 1, 1)
        assert specificity('foo:before') == (0, 0, 2)
        assert specificity('foo::before') == (0, 0, 2)
        assert specificity('foo:empty::before') == (0, 1, 2)

        assert specificity('#lorem + foo#ipsum:first-child > bar:first-line'
            ) == (2, 1, 3)
    # }}}

    def test_parse_errors(self):  # {{{
        def get_error(css):
            try:
                parse(css)
            except SelectorSyntaxError:
                # Py2, Py3, ...
                return str(sys.exc_info()[1]).replace("(u'", "('")

        self.ae(get_error('attributes(href)/html/body/a'), (
            "Expected selector, got <DELIM '(' at 10>"))
        assert get_error('attributes(href)') == (
            "Expected selector, got <DELIM '(' at 10>")
        assert get_error('html/body/a') == (
            "Expected selector, got <DELIM '/' at 4>")
        assert get_error(' ') == (
            "Expected selector, got <EOF at 1>")
        assert get_error('div, ') == (
            "Expected selector, got <EOF at 5>")
        assert get_error(' , div') == (
            "Expected selector, got <DELIM ',' at 1>")
        assert get_error('p, , div') == (
            "Expected selector, got <DELIM ',' at 3>")
        assert get_error('div > ') == (
            "Expected selector, got <EOF at 6>")
        assert get_error('  > div') == (
            "Expected selector, got <DELIM '>' at 2>")
        assert get_error('foo|#bar') == (
            "Expected ident or '*', got <HASH 'bar' at 4>")
        assert get_error('#.foo') == (
            "Expected selector, got <DELIM '#' at 0>")
        assert get_error('.#foo') == (
            "Expected ident, got <HASH 'foo' at 1>")
        assert get_error(':#foo') == (
            "Expected ident, got <HASH 'foo' at 1>")
        assert get_error('[*]') == (
            "Expected '|', got <DELIM ']' at 2>")
        assert get_error('[foo|]') == (
            "Expected ident, got <DELIM ']' at 5>")
        assert get_error('[#]') == (
            "Expected ident or '*', got <DELIM '#' at 1>")
        assert get_error('[foo=#]') == (
            "Expected string or ident, got <DELIM '#' at 5>")
        assert get_error('[href]a') == (
            "Expected selector, got <IDENT 'a' at 6>")
        assert get_error('[rel=stylesheet]') == None
        assert get_error('[rel:stylesheet]') == (
            "Operator expected, got <DELIM ':' at 4>")
        assert get_error('[rel=stylesheet') == (
            "Expected ']', got <EOF at 15>")
        assert get_error(':lang(fr)') == None
        assert get_error(':lang(fr') == (
            "Expected an argument, got <EOF at 8>")
        assert get_error(':contains("foo') == (
            "Unclosed string at 10")
        assert get_error('foo!') == (
            "Expected selector, got <DELIM '!' at 3>")

        # Mis-placed pseudo-elements
        assert get_error('a:before:empty') == (
            "Got pseudo-element ::before not at the end of a selector")
        assert get_error('li:before a') == (
            "Got pseudo-element ::before not at the end of a selector")
        assert get_error(':not(:before)') == (
            "Got pseudo-element ::before inside :not() at 12")
        assert get_error(':not(:not(a))') == (
            "Got nested :not()")
    # }}}

# Run tests {{{
def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCSSSelectors)

def run_tests(find_tests=find_tests, for_build=False):
    if not for_build:
        parser = argparse.ArgumentParser()
        parser.add_argument('name', nargs='?', default=None,
                            help='The name of the test to run')
        args = parser.parse_args()
    if not for_build and args.name and args.name.startswith('.'):
        tests = find_tests()
        q = args.name[1:]
        if not q.startswith('test_'):
            q = 'test_' + q
        ans = None
        try:
            for test in tests:
                if test._testMethodName == q:
                    ans = test
                    raise StopIteration()
        except StopIteration:
            pass
        if ans is None:
            print ('No test named %s found' % args.name)
            raise SystemExit(1)
        tests = ans
    else:
        tests = unittest.defaultTestLoader.loadTestsFromName(args.name) if not for_build and args.name else find_tests()
    r = unittest.TextTestRunner
    if for_build:
        r = r(verbosity=0, buffer=True, failfast=True)
    else:
        r = r(verbosity=4)
    result = r.run(tests)
    if for_build and result.errors or result.failures:
        raise SystemExit(1)

if __name__ == '__main__':
    run_tests()
# }}}
