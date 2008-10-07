"""productions for CSS 3

CSS3_MACROS and CSS3_PRODUCTIONS are from http://www.w3.org/TR/css3-syntax
"""
__all__ = ['CSSProductions', 'MACROS', 'PRODUCTIONS']
__docformat__ = 'restructuredtext'
__version__ = '$Id: css3productions.py 1116 2008-03-05 13:52:23Z cthedot $'

# a complete list of css3 macros
MACROS = {
    'ident': r'[-]?{nmstart}{nmchar}*',
    'name': r'{nmchar}+',
    'nmstart': r'[_a-zA-Z]|{nonascii}|{escape}',
    'nonascii': r'[^\0-\177]',
    'unicode': r'\\[0-9a-f]{1,6}{wc}?',
    'escape': r'{unicode}|\\[ -~\200-\777]',
    #   'escape': r'{unicode}|\\[ -~\200-\4177777]',
    'nmchar': r'[-_a-zA-Z0-9]|{nonascii}|{escape}',

    # CHANGED TO SPEC: added "-?"
    'num': r'-?[0-9]*\.[0-9]+|[0-9]+', #r'[-]?\d+|[-]?\d*\.\d+',
    'string':  r'''\'({stringchar}|\")*\'|\"({stringchar}|\')*\"''',
    'stringchar':  r'{urlchar}| |\\{nl}',
    'urlchar':  r'[\x09\x21\x23-\x26\x27-\x7E]|{nonascii}|{escape}',
    # what if \r\n, \n matches first?
    'nl': r'\n|\r\n|\r|\f',
    'w': r'{wc}*',
    'wc': r'\t|\r|\n|\f|\x20'
    }

# The following productions are the complete list of tokens in CSS3, the productions are **ordered**:
PRODUCTIONS = [
    ('BOM', r'\xFEFF'),
    ('URI', r'url\({w}({string}|{urlchar}*){w}\)'),
    ('FUNCTION', r'{ident}\('),
    ('ATKEYWORD', r'\@{ident}'),
    ('IDENT', r'{ident}'),
    ('STRING', r'{string}'),
    ('HASH', r'\#{name}'),
    ('PERCENTAGE', r'{num}\%'),
    ('DIMENSION', r'{num}{ident}'),
    ('NUMBER', r'{num}'),
    #???
    ('UNICODE-RANGE', ur'[0-9A-F?]{1,6}(\-[0-9A-F]{1,6})?'),
    ('CDO', r'\<\!\-\-'),
    ('CDC', r'\-\-\>'),
    ('S', r'{wc}+'),
    ('INCLUDES', '\~\='),
    ('DASHMATCH', r'\|\='),
    ('PREFIXMATCH', r'\^\='),
    ('SUFFIXMATCH', r'\$\='),
    ('SUBSTRINGMATCH', r'\*\='),
    ('COMMENT', r'\/\*[^*]*\*+([^/][^*]*\*+)*\/'),
    ('CHAR', r'[^"\']'),
    ]

class CSSProductions(object):
    "has attributes for all PRODUCTIONS"
    pass

for i, t in enumerate(PRODUCTIONS):
    setattr(CSSProductions, t[0].replace('-', '_'), t[0])
