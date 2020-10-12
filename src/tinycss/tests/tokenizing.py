#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from tinycss.tests import BaseTest, jsonify
from tinycss.tokenizer import python_tokenize_flat, c_tokenize_flat, regroup

if c_tokenize_flat is None:
    tokenizers = (python_tokenize_flat,)
else:
    tokenizers = (python_tokenize_flat, c_tokenize_flat)

def token_api(self, tokenize):
    for css_source in [
            '(8, foo, [z])', '[8, foo, (z)]', '{8, foo, [z]}', 'func(8, foo, [z])'
    ]:
        tokens = list(regroup(tokenize(css_source)))
        self.ae(len(tokens), 1)
        self.ae(len(tokens[0].content), 7)

def token_serialize_css(self, tokenize):
    for tokenize in tokenizers:
        for css_source in [
r'''p[example="\
foo(int x) {\
    this.x = x;\
}\
"]''',
            '"Lorem\\26Ipsum\ndolor" sit',
            '/* Lorem\nipsum */\fa {\n    color: red;\tcontent: "dolor\\\fsit" }',
            'not([[lorem]]{ipsum (42)})',
            'a[b{d]e}',
            'a[b{"d',
        ]:
            for _regroup in (regroup, lambda x: x):
                tokens = _regroup(tokenize(css_source, ignore_comments=False))
                result = ''.join(token.as_css() for token in tokens)
                self.ae(result, css_source)

def comments(self, tokenize):
    for ignore_comments, expected_tokens in [
        (False, [
            ('COMMENT', '/* lorem */'),
            ('S', ' '),
            ('IDENT', 'ipsum'),
            ('[', [
                ('IDENT', 'dolor'),
                ('COMMENT', '/* sit */'),
            ]),
            ('BAD_COMMENT', '/* amet')
        ]),
        (True, [
            ('S', ' '),
            ('IDENT', 'ipsum'),
            ('[', [
                ('IDENT', 'dolor'),
            ]),
        ]),
    ]:
        css_source = '/* lorem */ ipsum[dolor/* sit */]/* amet'
        tokens = regroup(tokenize(css_source, ignore_comments))
        result = list(jsonify(tokens))
        self.ae(result, expected_tokens)

def token_grouping(self, tokenize):
    for css_source, expected_tokens in [
        ('', []),
        (r'Lorem\26 "i\psum"4px', [
            ('IDENT', 'Lorem&'), ('STRING', 'ipsum'), ('DIMENSION', 4)]),

        ('not([[lorem]]{ipsum (42)})', [
            ('FUNCTION', 'not', [
                ('[', [
                    ('[', [
                        ('IDENT', 'lorem'),
                    ]),
                ]),
                ('{', [
                    ('IDENT', 'ipsum'),
                    ('S', ' '),
                    ('(', [
                        ('INTEGER', 42),
                    ])
                ])
            ])]),

        # Close everything at EOF, no error
        ('a[b{"d', [
            ('IDENT', 'a'),
            ('[', [
                ('IDENT', 'b'),
                ('{', [
                    ('STRING', 'd'),
                ]),
            ]),
        ]),

        # Any remaining ), ] or } token is a nesting error
        ('a[b{d]e}', [
            ('IDENT', 'a'),
            ('[', [
                ('IDENT', 'b'),
                ('{', [
                    ('IDENT', 'd'),
                    (']', ']'),  # The error is visible here
                    ('IDENT', 'e'),
                ]),
            ]),
        ]),
        # ref:
        ('a[b{d}e]', [
            ('IDENT', 'a'),
            ('[', [
                ('IDENT', 'b'),
                ('{', [
                    ('IDENT', 'd'),
                ]),
                ('IDENT', 'e'),
            ]),
        ]),
    ]:
        tokens = regroup(tokenize(css_source, ignore_comments=False))
        result = list(jsonify(tokens))
        self.ae(result, expected_tokens)

def positions(self, tokenize):
    css = '/* Lorem\nipsum */\fa {\n    color: red;\tcontent: "dolor\\\fsit" }'
    tokens = tokenize(css, ignore_comments=False)
    result = [(token.type, token.line, token.column) for token in tokens]
    self.ae(result, [
        ('COMMENT', 1, 1), ('S', 2, 9),
        ('IDENT', 3, 1), ('S', 3, 2), ('{', 3, 3),
        ('S', 3, 4), ('IDENT', 4, 5), (':', 4, 10),
        ('S', 4, 11), ('IDENT', 4, 12), (';', 4, 15), ('S', 4, 16),
        ('IDENT', 4, 17), (':', 4, 24), ('S', 4, 25), ('STRING', 4, 26),
        ('S', 5, 5), ('}', 5, 6)])

def tokens(self, tokenize):
    for css_source, expected_tokens in [
        ('', []),
        ('red -->',
            [('IDENT', 'red'), ('S', ' '), ('CDC', '-->')]),
        # Longest match rule: no CDC
        ('red-->',
            [('IDENT', 'red--'), ('DELIM', '>')]),

(r'''p[example="\
foo(int x) {\
    this.x = x;\
}\
"]''', [
            ('IDENT', 'p'),
            ('[', '['),
            ('IDENT', 'example'),
            ('DELIM', '='),
            ('STRING', 'foo(int x) {    this.x = x;}'),
            (']', ']')]),

        # Numbers are parsed
        ('42 .5 -4pX 1.25em 30%',
            [('INTEGER', 42), ('S', ' '),
            ('NUMBER', .5), ('S', ' '),
            # units are normalized to lower-case:
            ('DIMENSION', -4, 'px'), ('S', ' '),
            ('DIMENSION', 1.25, 'em'), ('S', ' '),
            ('PERCENTAGE', 30, '%')]),

        # URLs are extracted
        ('url(foo.png)', [('URI', 'foo.png')]),
        ('url("foo.png")', [('URI', 'foo.png')]),

        # Escaping

        (r'/* Comment with a \ backslash */',
            [('COMMENT', '/* Comment with a \ backslash */')]),  # Unchanged

        # backslash followed by a newline in a string: ignored
        ('"Lorem\\\nIpsum"', [('STRING', 'LoremIpsum')]),

        # backslash followed by a newline outside a string: stands for itself
        ('Lorem\\\nIpsum', [
            ('IDENT', 'Lorem'), ('DELIM', '\\'),
            ('S', '\n'), ('IDENT', 'Ipsum')]),

        # Cancel the meaning of special characters
        (r'"Lore\m Ipsum"', [('STRING', 'Lorem Ipsum')]),  # or not specal
        (r'"Lorem \49psum"', [('STRING', 'Lorem Ipsum')]),
        (r'"Lorem \49 psum"', [('STRING', 'Lorem Ipsum')]),
        (r'"Lorem\"Ipsum"', [('STRING', 'Lorem"Ipsum')]),
        (r'"Lorem\\Ipsum"', [('STRING', r'Lorem\Ipsum')]),
        (r'"Lorem\5c Ipsum"', [('STRING', r'Lorem\Ipsum')]),
        (r'Lorem\+Ipsum', [('IDENT', 'Lorem+Ipsum')]),
        (r'Lorem+Ipsum', [('IDENT', 'Lorem'), ('DELIM', '+'), ('IDENT', 'Ipsum')]),
        (r'url(foo\).png)', [('URI', 'foo).png')]),

        # Unicode and backslash escaping
        ('\\26 B', [('IDENT', '&B')]),
        ('\\&B', [('IDENT', '&B')]),
        ('@\\26\tB', [('ATKEYWORD', '@&B')]),
        ('@\\&B', [('ATKEYWORD', '@&B')]),
        ('#\\26\nB', [('HASH', '#&B')]),
        ('#\\&B', [('HASH', '#&B')]),
        ('\\26\r\nB(', [('FUNCTION', '&B(')]),
        ('\\&B(', [('FUNCTION', '&B(')]),
        (r'12.5\000026B', [('DIMENSION', 12.5, '&b')]),
        (r'12.5\0000263B', [('DIMENSION', 12.5, '&3b')]),  # max 6 digits
        (r'12.5\&B', [('DIMENSION', 12.5, '&b')]),
        (r'"\26 B"', [('STRING', '&B')]),
        (r"'\000026B'", [('STRING', '&B')]),
        (r'"\&B"', [('STRING', '&B')]),
        (r'url("\26 B")', [('URI', '&B')]),
        (r'url(\26 B)', [('URI', '&B')]),
        (r'url("\&B")', [('URI', '&B')]),
        (r'url(\&B)', [('URI', '&B')]),
        (r'Lorem\110000Ipsum', [('IDENT', 'Lorem\uFFFDIpsum')]),

        # Bad strings

        # String ends at EOF without closing: no error, parsed
        ('"Lorem\\26Ipsum', [('STRING', 'Lorem&Ipsum')]),
        # Unescaped newline: ends the string, error, unparsed
        ('"Lorem\\26Ipsum\n', [
            ('BAD_STRING', r'"Lorem\26Ipsum'), ('S', '\n')]),
        # Tokenization restarts after the newline, so the second " starts
        # a new string (which ends at EOF without errors, as above.)
        ('"Lorem\\26Ipsum\ndolor" sit', [
            ('BAD_STRING', r'"Lorem\26Ipsum'), ('S', '\n'),
            ('IDENT', 'dolor'), ('STRING', ' sit')]),

    ]:
        sources = [css_source]
        for css_source in sources:
            tokens = tokenize(css_source, ignore_comments=False)
            result = [
                (token.type, token.value) + (
                    () if token.unit is None else (token.unit,))
                for token in tokens
            ]
            self.ae(result, expected_tokens)


class TestTokenizer(BaseTest):

    def run_test(self, func):
        for tokenize in tokenizers:
            func(self, tokenize)

    def test_token_api(self):
        self.run_test(token_api)

    def test_token_serialize_css(self):
        self.run_test(token_serialize_css)

    def test_comments(self):
        self.run_test(comments)

    def test_token_grouping(self):
        self.run_test(token_grouping)

    def test_positions(self):
        """Test the reported line/column position of each token."""
        self.run_test(positions)

    def test_tokens(self):
        self.run_test(tokens)

