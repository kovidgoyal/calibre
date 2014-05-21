# coding: utf8
"""
    tinycss.tokenizer
    -----------------

    Tokenizer for the CSS core syntax:
    http://www.w3.org/TR/CSS21/syndata.html#tokenization

    This is the pure-python implementation. See also speedups.pyx

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals

from . import token_data


def tokenize_flat(css_source, ignore_comments=True,
    # Make these local variable to avoid global lookups in the loop
    tokens_dispatch=token_data.TOKEN_DISPATCH,
    unicode_unescape=token_data.UNICODE_UNESCAPE,
    newline_unescape=token_data.NEWLINE_UNESCAPE,
    simple_unescape=token_data.SIMPLE_UNESCAPE,
    find_newlines=token_data.FIND_NEWLINES,
    Token=token_data.Token,
    len=len,
    int=int,
    float=float,
    list=list,
    _None=None,
):
    """
    :param css_source:
        CSS as an unicode string
    :param ignore_comments:
        if true (the default) comments will not be included in the
        return value
    :return:
        An iterator of :class:`Token`

    """

    pos = 0
    line = 1
    column = 1
    source_len = len(css_source)
    tokens = []
    while pos < source_len:
        char = css_source[pos]
        if char in ':;{}()[]':
            type_ = char
            css_value = char
        else:
            codepoint = min(ord(char), 160)
            for _index, type_, regexp in tokens_dispatch[codepoint]:
                match = regexp(css_source, pos)
                if match:
                    # First match is the longest. See comments on TOKENS above.
                    css_value = match.group()
                    break
            else:
                # No match.
                # "Any other character not matched by the above rules,
                #  and neither a single nor a double quote."
                # ... but quotes at the start of a token are always matched
                # by STRING or BAD_STRING. So DELIM is any single character.
                type_ = 'DELIM'
                css_value = char
        length = len(css_value)
        next_pos = pos + length

        # A BAD_COMMENT is a comment at EOF. Ignore it too.
        if not (ignore_comments and type_ in ('COMMENT', 'BAD_COMMENT')):
            # Parse numbers, extract strings and URIs, unescape
            unit = _None
            if type_ == 'DIMENSION':
                value = match.group(1)
                value = float(value) if '.' in value else int(value)
                unit = match.group(2)
                unit = simple_unescape(unit)
                unit = unicode_unescape(unit)
                unit = unit.lower()  # normalize
            elif type_ == 'PERCENTAGE':
                value = css_value[:-1]
                value = float(value) if '.' in value else int(value)
                unit = '%'
            elif type_ == 'NUMBER':
                value = css_value
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
                    type_ = 'INTEGER'
            elif type_ in ('IDENT', 'ATKEYWORD', 'HASH', 'FUNCTION'):
                value = simple_unescape(css_value)
                value = unicode_unescape(value)
            elif type_ == 'URI':
                value = match.group(1)
                if value and value[0] in '"\'':
                    value = value[1:-1]  # Remove quotes
                    value = newline_unescape(value)
                value = simple_unescape(value)
                value = unicode_unescape(value)
            elif type_ == 'STRING':
                value = css_value[1:-1]  # Remove quotes
                value = newline_unescape(value)
                value = simple_unescape(value)
                value = unicode_unescape(value)
            # BAD_STRING can only be one of:
            # * Unclosed string at the end of the stylesheet:
            #   Close the string, but this is not an error.
            #   Make it a "good" STRING token.
            # * Unclosed string at the (unescaped) end of the line:
            #   Close the string, but this is an error.
            #   Leave it as a BAD_STRING, don’t bother parsing it.
            # See http://www.w3.org/TR/CSS21/syndata.html#parsing-errors
            elif type_ == 'BAD_STRING' and next_pos == source_len:
                type_ = 'STRING'
                value = css_value[1:]  # Remove quote
                value = newline_unescape(value)
                value = simple_unescape(value)
                value = unicode_unescape(value)
            else:
                value = css_value
            tokens.append(Token(type_, css_value, value, unit, line, column))

        pos = next_pos
        newlines = list(find_newlines(css_value))
        if newlines:
            line += len(newlines)
            # Add 1 to have lines start at column 1, not 0
            column = length - newlines[-1].end() + 1
        else:
            column += length
    return tokens


def regroup(tokens):
    """
    Match pairs of tokens: () [] {} function()
    (Strings in "" or '' are taken care of by the tokenizer.)

    Opening tokens are replaced by a :class:`ContainerToken`.
    Closing tokens are removed. Unmatched closing tokens are invalid
    but left as-is. All nested structures that are still open at
    the end of the stylesheet are implicitly closed.

    :param tokens:
        a *flat* iterable of tokens, as returned by :func:`tokenize_flat`.
    :return:
        A tree of tokens.

    """
    # "global" objects for the inner recursion
    pairs = {'FUNCTION': ')', '(': ')', '[': ']', '{': '}'}
    tokens = iter(tokens)
    eof = [False]

    def _regroup_inner(stop_at=None,
            tokens=tokens, pairs=pairs, eof=eof,
            ContainerToken=token_data.ContainerToken,
            FunctionToken=token_data.FunctionToken):
        for token in tokens:
            type_ = token.type
            if type_ == stop_at:
                return

            end = pairs.get(type_)
            if end is None:
                yield token  # Not a grouping token
            else:
                assert not isinstance(token, ContainerToken), (
                    'Token looks already grouped: {0}'.format(token))
                content = list(_regroup_inner(end))
                if eof[0]:
                    end = ''  # Implicit end of structure at EOF.
                if type_ == 'FUNCTION':
                    yield FunctionToken(token.type, token.as_css(), end,
                                        token.value, content,
                                        token.line, token.column)
                else:
                    yield ContainerToken(token.type, token.as_css(), end,
                                         content,
                                         token.line, token.column)
        else:
            eof[0] = True  # end of file/stylesheet
    return _regroup_inner()


def tokenize_grouped(css_source, ignore_comments=True):
    """
    :param css_source:
        CSS as an unicode string
    :param ignore_comments:
        if true (the default) comments will not be included in the
        return value
    :return:
        An iterator of :class:`Token`

    """
    return regroup(tokenize_flat(css_source, ignore_comments))


# Optional Cython version of tokenize_flat
# Make both versions available with explicit names for tests.
python_tokenize_flat = tokenize_flat
try:
    from . import speedups
except ImportError:
    cython_tokenize_flat = None
else:
    cython_tokenize_flat = speedups.tokenize_flat
    # Default to the Cython version if available
    tokenize_flat = cython_tokenize_flat
