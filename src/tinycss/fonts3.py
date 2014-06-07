#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'


from .css21 import CSS21Parser, ParseError

class FontFaceRule(object):

    at_keyword = '@font-face'

    def __init__(self, declarations, line, column):
        self.declarations = declarations
        self.line = line
        self.column = column

class CSSFonts3Parser(CSS21Parser):

    ''' Parse @font-face rules from the CSS 3 fonts module '''

    ALLOWED_CONTEXTS = {'stylesheet', '@media', '@page'}

    def parse_at_rule(self, rule, previous_rules, errors, context):
        if rule.at_keyword != '@font-face':
            return super(CSSFonts3Parser, self).parse_at_rule(
                rule, previous_rules, errors, context)
        if context not in self.ALLOWED_CONTEXTS:
            raise ParseError(rule,
                '@font-face rule not allowed in ' + context)
        if rule.body is None:
            raise ParseError(rule,
                'invalid {0} rule: missing block'.format(rule.at_keyword))
        if rule.head:
            raise ParseError(rule, '{0} rule is not allowed to have content before the descriptor declaration'.format(rule.at_keyword))
        declarations, decerrors = self.parse_declaration_list(rule.body)
        errors.extend(decerrors)
        return FontFaceRule(declarations, rule.line, rule.column)

