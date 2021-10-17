#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'


import re
from tinycss.css21 import CSS21Parser, ParseError
from .tokenizer import tokenize_grouped


def parse_font_family_tokens(tokens):
    families = []
    current_family = ''

    def commit():
        val = current_family.strip()
        if val:
            families.append(val)

    for token in tokens:
        if token.type == 'STRING':
            if current_family:
                commit()
            current_family = token.value
        elif token.type == 'DELIM':
            if token.value == ',':
                if current_family:
                    commit()
                current_family = ''
        elif token.type == 'IDENT':
            current_family += ' ' + token.value
    if current_family:
        commit()
    return families


def parse_font_family(css_string):
    return parse_font_family_tokens(tokenize_grouped(type('')(css_string).strip()))


def serialize_single_font_family(x):
    xl = x.lower()
    if xl in GENERIC_FAMILIES:
        if xl == 'sansserif':
            xl = 'sans-serif'
        return xl
    if SIMPLE_NAME_PAT.match(x) is not None and not x.lower().startswith('and'):
        # css_parser dies if a font name starts with and
        return x
    return '"%s"' % x.replace('"', r'\"')


def serialize_font_family(families):
    return ', '.join(map(serialize_single_font_family, families))


GLOBAL_IDENTS = frozenset('inherit initial unset normal'.split())
STYLE_IDENTS = frozenset('italic oblique'.split())
VARIANT_IDENTS = frozenset(('small-caps',))
WEIGHT_IDENTS = frozenset('bold bolder lighter'.split())
STRETCH_IDENTS = frozenset('ultra-condensed extra-condensed condensed semi-condensed semi-expanded expanded extra-expanded ultra-expanded'.split())
BEFORE_SIZE_IDENTS = STYLE_IDENTS | VARIANT_IDENTS | WEIGHT_IDENTS | STRETCH_IDENTS
SIZE_IDENTS = frozenset('xx-small x-small small medium large x-large xx-large larger smaller'.split())
WEIGHT_SIZES = frozenset(map(int, '100 200 300 400 500 600 700 800 900'.split()))
LEGACY_FONT_SPEC = frozenset('caption icon menu message-box small-caption status-bar'.split())
GENERIC_FAMILIES = frozenset('serif sans-serif sansserif cursive fantasy monospace'.split())
SIMPLE_NAME_PAT = re.compile(r'[a-zA-Z][a-zA-Z0-9_-]*$')


def serialize_font(font_dict):
    ans = []
    for x in 'style variant weight stretch'.split():
        val = font_dict.get('font-' + x)
        if val is not None:
            ans.append(val)
    val = font_dict.get('font-size')
    if val is not None:
        fs = val
        val = font_dict.get('line-height')
        if val is not None:
            fs += '/' + val
        ans.append(fs)
    val = font_dict.get('font-family')
    if val:
        ans.append(serialize_font_family(val))
    return ' '.join(ans)


def parse_font(css_string):
    # See https://www.w3.org/TR/css-fonts-3/#font-prop
    style = variant = weight = stretch = size = height = None
    tokens = list(reversed(tuple(tokenize_grouped(type('')(css_string).strip()))))
    if tokens and tokens[-1].value in LEGACY_FONT_SPEC:
        return {'font-family':['sans-serif']}
    while tokens:
        tok = tokens.pop()
        if tok.type == 'STRING':
            tokens.append(tok)
            break
        if tok.type == 'INTEGER':
            if size is None:
                if weight is None and tok.value in WEIGHT_SIZES:
                    weight = tok.as_css()
                    continue
                break
            if height is None:
                height = tok.as_css()
                break
            break
        if tok.type == 'NUMBER':
            if size is not None and height is None:
                height = tok.as_css()
            break
        if tok.type == 'DELIM':
            if tok.value == '/' and size is not None and height is None:
                continue
            break
        if tok.type in ('DIMENSION', 'PERCENTAGE'):
            if size is None:
                size = tok.as_css()
                continue
            if height is None:
                height = tok.as_css()
            break
        if tok.type == 'IDENT':
            if tok.value in GLOBAL_IDENTS:
                if size is not None:
                    if height is None:
                        height = tok.value
                    else:
                        tokens.append(tok)
                    break
                if style is None:
                    style = tok.value
                elif variant is None:
                    variant = tok.value
                elif weight is None:
                    weight = tok.value
                elif stretch is None:
                    stretch = tok.value
                elif size is None:
                    size = tok.value
                elif height is None:
                    height = tok.value
                    break
                else:
                    tokens.append(tok)
                    break
                continue
            if tok.value in BEFORE_SIZE_IDENTS:
                if size is not None:
                    break
                if tok.value in STYLE_IDENTS:
                    style = tok.value
                elif tok.value in VARIANT_IDENTS:
                    variant = tok.value
                elif tok.value in WEIGHT_IDENTS:
                    weight = tok.value
                elif tok.value in STRETCH_IDENTS:
                    stretch = tok.value
            elif tok.value in SIZE_IDENTS:
                size = tok.value
            else:
                tokens.append(tok)
                break
    families = parse_font_family_tokens(reversed(tokens))
    ans = {}
    if style is not None:
        ans['font-style'] = style
    if variant is not None:
        ans['font-variant'] = variant
    if weight is not None:
        ans['font-weight'] = weight
    if stretch is not None:
        ans['font-stretch'] = stretch
    if size is not None:
        ans['font-size'] = size
    if height is not None:
        ans['line-height'] = height
    if families:
        ans['font-family'] = families
    return ans


class FontFaceRule:

    at_keyword = '@font-face'
    __slots__ = 'declarations', 'line', 'column'

    def __init__(self, declarations, line, column):
        self.declarations = declarations
        self.line = line
        self.column = column

    def __repr__(self):
        return ('<{0.__class__.__name__} at {0.line}:{0.column}>'
                .format(self))


class CSSFonts3Parser(CSS21Parser):

    ''' Parse @font-face rules from the CSS 3 fonts module '''

    ALLOWED_CONTEXTS_FOR_FONT_FACE = {'stylesheet', '@media', '@page'}

    def __init__(self):
        super(CSSFonts3Parser, self).__init__()
        self.at_parsers['@font-face'] = self.parse_font_face_rule

    def parse_font_face_rule(self, rule, previous_rules, errors, context):
        if context not in self.ALLOWED_CONTEXTS_FOR_FONT_FACE:
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
