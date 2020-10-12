# coding: utf8
"""
    tinycss.parsing
    ---------------

    Utilities for parsing lists of tokens.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


# TODO: unit tests

def split_on_comma(tokens):
    """Split a list of tokens on commas, ie ``,`` DELIM tokens.

    Only "top-level" comma tokens are splitting points, not commas inside a
    function or other :class:`ContainerToken`.

    :param tokens:
        An iterable of :class:`~.token_data.Token` or
        :class:`~.token_data.ContainerToken`.
    :returns:
        A list of lists of tokens

    """
    parts = []
    this_part = []
    for token in tokens:
        if token.type == 'DELIM' and token.value == ',':
            parts.append(this_part)
            this_part = []
        else:
            this_part.append(token)
    parts.append(this_part)
    return parts


def strip_whitespace(tokens):
    """Remove whitespace at the beggining and end of a token list.

    Whitespace tokens in-between other tokens in the list are preserved.

    :param tokens:
        A list of :class:`~.token_data.Token` or
        :class:`~.token_data.ContainerToken`.
    :return:
        A new sub-sequence of the list.

    """
    for i, token in enumerate(tokens):
        if token.type != 'S':
            break
    else:
        return []  # only whitespace
    tokens = tokens[i:]
    while tokens and tokens[-1].type == 'S':
        tokens.pop()
    return tokens


def remove_whitespace(tokens):
    """Remove any top-level whitespace in a token list.

    Whitespace tokens inside recursive :class:`~.token_data.ContainerToken`
    are preserved.

    :param tokens:
        A list of :class:`~.token_data.Token` or
        :class:`~.token_data.ContainerToken`.
    :return:
        A new sub-sequence of the list.

    """
    return [token for token in tokens if token.type != 'S']


def validate_value(tokens):
    """Validate a property value.

    :param tokens:
        an iterable of tokens
    :raises:
        :class:`ParseError` if there is any invalid token for the 'value'
        production of the core grammar.

    """
    for token in tokens:
        type_ = token.type
        if type_ == '{':
            validate_block(token.content, 'property value')
        else:
            validate_any(token, 'property value')

def validate_block(tokens, context):
    """
    :raises:
        :class:`ParseError` if there is any invalid token for the 'block'
        production of the core grammar.
    :param tokens: an iterable of tokens
    :param context: a string for the 'unexpected in ...' message

    """
    for token in tokens:
        type_ = token.type
        if type_ == '{':
            validate_block(token.content, context)
        elif type_ not in (';', 'ATKEYWORD'):
            validate_any(token, context)


def validate_any(token, context):
    """
    :raises:
        :class:`ParseError` if this is an invalid token for the
        'any' production of the core grammar.
    :param token: a single token
    :param context: a string for the 'unexpected in ...' message

    """
    type_ = token.type
    if type_ in ('FUNCTION', '(', '['):
        for token in token.content:
            validate_any(token, type_)
    elif type_ not in ('S', 'IDENT', 'DIMENSION', 'PERCENTAGE', 'NUMBER',
                       'INTEGER', 'URI', 'DELIM', 'STRING', 'HASH', ':',
                       'UNICODE-RANGE'):
        if type_ in ('}', ')', ']'):
            adjective = 'unmatched'
        else:
            adjective = 'unexpected'
        raise ParseError(token,
            '{0} {1} token in {2}'.format(adjective, type_, context))


class ParseError(ValueError):
    """Details about a CSS syntax error. Usually indicates that something
    (a rule or a declaration) was ignored and will not appear as a parsed
    object.

    This exception is typically logged in a list rather than being propagated
    to the user API.

    .. attribute:: line

        Source line where the error occured.

    .. attribute:: column

        Column in the source line where the error occured.

    .. attribute:: reason

        What happend (a string).

    """
    def __init__(self, subject, reason):
        self.line = subject.line
        self.column = subject.column
        self.reason = reason
        super(ParseError, self).__init__(
            'Parse error at {0.line}:{0.column}, {0.reason}'.format(self))
