#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from tinycss.page3 import CSSPage3Parser
from tinycss.tests import BaseTest

class TestPage3(BaseTest):

    def test_selectors(self):
        for css, expected_selector, expected_specificity, expected_errors in [
            ('@page {}', (None, None), (0, 0, 0), []),

            ('@page :first {}', (None, 'first'), (0, 1, 0), []),
            ('@page:left{}', (None, 'left'), (0, 0, 1), []),
            ('@page :right {}', (None, 'right'), (0, 0, 1), []),
            ('@page  :blank{}', (None, 'blank'), (0, 1, 0), []),
            ('@page :last {}', None, None, ['invalid @page selector']),
            ('@page : first {}', None, None, ['invalid @page selector']),

            ('@page foo:first {}', ('foo', 'first'), (1, 1, 0), []),
            ('@page bar :left {}', ('bar', 'left'), (1, 0, 1), []),
            (r'@page \26:right {}', ('&', 'right'), (1, 0, 1), []),

            ('@page foo {}', ('foo', None), (1, 0, 0), []),
            (r'@page \26 {}', ('&', None), (1, 0, 0), []),

            ('@page foo fist {}', None, None, ['invalid @page selector']),
            ('@page foo, bar {}', None, None, ['invalid @page selector']),
            ('@page foo&first {}', None, None, ['invalid @page selector']),
        ]:
            stylesheet = CSSPage3Parser().parse_stylesheet(css)
            self.assert_errors(stylesheet.errors, expected_errors)

            if stylesheet.rules:
                self.ae(len(stylesheet.rules), 1)
                rule = stylesheet.rules[0]
                self.ae(rule.at_keyword, '@page')
                selector = rule.selector
                self.ae(rule.specificity, expected_specificity)
            else:
                selector = None
            self.ae(selector, expected_selector)

    def test_content(self):
        for css, expected_declarations, expected_rules, expected_errors in [
            ('@page {}', [], [], []),
            ('@page { foo: 4; bar: z }',
                [('foo', [('INTEGER', 4)]), ('bar', [('IDENT', 'z')])], [], []),
            ('''@page { foo: 4;
                        @top-center { content: "Awesome Title" }
                        @bottom-left { content: counter(page) }
                        bar: z
                }''',
                [('foo', [('INTEGER', 4)]), ('bar', [('IDENT', 'z')])],
                [('@top-center', [('content', [('STRING', 'Awesome Title')])]),
                ('@bottom-left', [('content', [
                    ('FUNCTION', 'counter', [('IDENT', 'page')])])])],
                []),
            ('''@page { foo: 4;
                        @bottom-top { content: counter(page) }
                        bar: z
                }''',
                [('foo', [('INTEGER', 4)]), ('bar', [('IDENT', 'z')])],
                [],
                ['unknown at-rule in @page context: @bottom-top']),

            ('@page{} @top-right{}', [], [], [
                '@top-right rule not allowed in stylesheet']),
            ('@page{ @top-right 4 {} }', [], [], [
                'unexpected INTEGER token in @top-right rule header']),
            # Not much error recovery tests here. This should be covered in test_css21
        ]:
            stylesheet = CSSPage3Parser().parse_stylesheet(css)
            self.assert_errors(stylesheet.errors, expected_errors)

            self.ae(len(stylesheet.rules), 1)
            rule = stylesheet.rules[0]
            self.ae(rule.at_keyword, '@page')
            self.ae(self.jsonify_declarations(rule), expected_declarations)
            rules = [(margin_rule.at_keyword, self.jsonify_declarations(margin_rule))
                    for margin_rule in rule.at_rules]
            self.ae(rules, expected_rules)
