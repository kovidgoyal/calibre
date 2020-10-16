# coding: utf8
"""
    tinycss.token_data
    ------------------

    Shared data for both implementations (Cython and Python) of the tokenizer.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


import re
import sys
import operator
import functools
import string


# * Raw strings with the r'' notation are used so that \ do not need
#   to be escaped.
# * Names and regexps are separated by a tabulation.
# * Macros are re-ordered so that only previous definitions are needed.
# * {} are used for macro substitution with ``string.Formatter``,
#   so other uses of { or } have been doubled.
# * The syntax is otherwise compatible with re.compile.
# * Some parentheses were added to add capturing groups.
#   (in unicode, DIMENSION and URI)

# *** Willful violation: ***
# Numbers can take a + or - sign, but the sign is a separate DELIM token.
# Since comments are allowed anywhere between tokens, this makes
# the following this is valid. It means 10 negative pixels:
#    margin-top: -/**/10px

# This makes parsing numbers a pain, so instead we’ll do the same is Firefox
# and make the sign part as of the 'num' macro. The above CSS will be invalid.
# See discussion:
# http://lists.w3.org/Archives/Public/www-style/2011Oct/0028.html
MACROS = r'''
    nl	\n|\r\n|\r|\f
    w	[ \t\r\n\f]*
    nonascii	[^\0-\237]
    unicode	\\([0-9a-f]{{1,6}})(\r\n|[ \n\r\t\f])?
    simple_escape	[^\n\r\f0-9a-f]
    escape	{unicode}|\\{simple_escape}
    nmstart	[_a-z]|{nonascii}|{escape}
    nmchar	[_a-z0-9-]|{nonascii}|{escape}
    name	{nmchar}+
    ident	[-]?{nmstart}{nmchar}*
    num	[-+]?(?:[0-9]*\.[0-9]+|[0-9]+)
    string1	\"([^\n\r\f\\"]|\\{nl}|{escape})*\"
    string2	\'([^\n\r\f\\']|\\{nl}|{escape})*\'
    string	{string1}|{string2}
    badstring1	\"([^\n\r\f\\"]|\\{nl}|{escape})*\\?
    badstring2	\'([^\n\r\f\\']|\\{nl}|{escape})*\\?
    badstring	{badstring1}|{badstring2}
    badcomment1	\/\*[^*]*\*+([^/*][^*]*\*+)*
    badcomment2	\/\*[^*]*(\*+[^/*][^*]*)*
    badcomment	{badcomment1}|{badcomment2}
    baduri1	url\({w}([!#$%&*-~]|{nonascii}|{escape})*{w}
    baduri2	url\({w}{string}{w}
    baduri3	url\({w}{badstring}
    baduri	{baduri1}|{baduri2}|{baduri3}
'''.replace(r'\0', '\0').replace(r'\237', '\237')

# Removed these tokens. Instead, they’re tokenized as two DELIM each.
#    INCLUDES	~=
#    DASHMATCH	|=
# They are only used in selectors but selectors3 also have ^=, *= and $=.
# We don’t actually parse selectors anyway

# Re-ordered so that the longest match is always the first.
# For example, "url('foo')" matches URI, BAD_URI, FUNCTION and IDENT,
# but URI would always be a longer match than the others.
TOKENS = r'''
    S	[ \t\r\n\f]+

    URI	url\({w}({string}|([!#$%&*-\[\]-~]|{nonascii}|{escape})*){w}\)
    BAD_URI	{baduri}
    FUNCTION	{ident}\(
    UNICODE-RANGE	u\+[0-9a-f?]{{1,6}}(-[0-9a-f]{{1,6}})?
    IDENT	{ident}

    ATKEYWORD	@{ident}
    HASH	#{name}

    DIMENSION	({num})({ident})
    PERCENTAGE	{num}%
    NUMBER	{num}

    STRING	{string}
    BAD_STRING	{badstring}

    COMMENT	\/\*[^*]*\*+([^/*][^*]*\*+)*\/
    BAD_COMMENT	{badcomment}

    :	:
    ;	;
    {	\{{
    }	\}}
    (	\(
    )	\)
    [	\[
    ]	\]
    CDO	<!--
    CDC	-->
'''


# Strings with {macro} expanded
COMPILED_MACROS = {}


COMPILED_TOKEN_REGEXPS = []  # [(name, regexp.match)]  ordered
COMPILED_TOKEN_INDEXES = {}  # {name: i}  helper for the C speedups


# Indexed by codepoint value of the first character of a token.
# Codepoints >= 160 (aka nonascii) all use the index 160.
# values are (i, name, regexp.match)
TOKEN_DISPATCH = []


try:
    unichr
except NameError:
    # Python 3
    unichr = chr
    unicode = str


def _init():
    """Import-time initialization."""
    COMPILED_MACROS.clear()
    for line in MACROS.splitlines():
        if line.strip():
            name, value = line.split('\t')
            COMPILED_MACROS[name.strip()] = '(?:%s)' \
                % value.format(**COMPILED_MACROS)

    COMPILED_TOKEN_REGEXPS[:] = (
        (
            name.strip(),
            re.compile(
                value.format(**COMPILED_MACROS),
                # Case-insensitive when matching eg. uRL(foo)
                # but preserve the case in extracted groups
                re.I
            ).match
        )
        for line in TOKENS.splitlines()
        if line.strip()
        for name, value in [line.split('\t')]
    )

    COMPILED_TOKEN_INDEXES.clear()
    for i, (name, regexp) in enumerate(COMPILED_TOKEN_REGEXPS):
        COMPILED_TOKEN_INDEXES[name] = i

    dispatch = [[] for i in range(161)]
    for chars, names in [
        (' \t\r\n\f', ['S']),
        ('uU', ['URI', 'BAD_URI', 'UNICODE-RANGE']),
        # \ is an escape outside of another token
        (string.ascii_letters + '\\_-' + unichr(160), ['FUNCTION', 'IDENT']),
        (string.digits + '.+-', ['DIMENSION', 'PERCENTAGE', 'NUMBER']),
        ('@', ['ATKEYWORD']),
        ('#', ['HASH']),
        ('\'"', ['STRING', 'BAD_STRING']),
        ('/', ['COMMENT', 'BAD_COMMENT']),
        ('<', ['CDO']),
        ('-', ['CDC']),
    ]:
        for char in chars:
            dispatch[ord(char)].extend(names)
    for char in ':;{}()[]':
        dispatch[ord(char)] = [char]

    TOKEN_DISPATCH[:] = (
        [
            (index,) + COMPILED_TOKEN_REGEXPS[index]
            for name in names
            for index in [COMPILED_TOKEN_INDEXES[name]]
        ]
        for names in dispatch
    )


_init()


def _unicode_replace(match, int=int, unichr=unichr, maxunicode=sys.maxunicode):
    codepoint = int(match.group(1), 16)
    if codepoint <= maxunicode:
        return unichr(codepoint)
    else:
        return '\N{REPLACEMENT CHARACTER}'  # U+FFFD


UNICODE_UNESCAPE = functools.partial(
    re.compile(COMPILED_MACROS['unicode'], re.I).sub,
    _unicode_replace)

NEWLINE_UNESCAPE = functools.partial(
    re.compile(r'()\\' + COMPILED_MACROS['nl']).sub,
    '')


SIMPLE_UNESCAPE = functools.partial(
    re.compile(r'\\(%s)' % COMPILED_MACROS['simple_escape'], re.I).sub,
    # Same as r'\1', but faster on CPython
    operator.methodcaller('group', 1))


def FIND_NEWLINES(x):
    return list(re.compile(COMPILED_MACROS['nl']).finditer(x))


class Token(object):
    r"""A single atomic token.

    .. attribute:: is_container

        Always ``False``.
        Helps to tell :class:`Token` apart from :class:`ContainerToken`.

    .. attribute:: type

        The type of token as a string:

        ``S``
            A sequence of white space

        ``IDENT``
            An identifier: a name that does not start with a digit.
            A name is a sequence of letters, digits, ``_``, ``-``, escaped
            characters and non-ASCII characters. Eg: ``margin-left``

        ``HASH``
            ``#`` followed immediately by a name. Eg: ``#ff8800``

        ``ATKEYWORD``
            ``@`` followed immediately by an identifier. Eg: ``@page``

        ``URI``
            Eg: ``url(foo)`` The content may or may not be quoted.

        ``UNICODE-RANGE``
            ``U+`` followed by one or two hexadecimal
            Unicode codepoints. Eg: ``U+20-00FF``

        ``INTEGER``
            An integer with an optional ``+`` or ``-`` sign

        ``NUMBER``
            A non-integer number  with an optional ``+`` or ``-`` sign

        ``DIMENSION``
            An integer or number followed immediately by an
            identifier (the unit). Eg: ``12px``

        ``PERCENTAGE``
            An integer or number followed immediately by ``%``

        ``STRING``
            A string, quoted with ``"`` or ``'``

        ``:`` or ``;``
            That character.

        ``DELIM``
            A single character not matched in another token. Eg: ``,``

        See the source of the :mod:`.token_data` module for the precise
        regular expressions that match various tokens.

        Note that other token types exist in the early tokenization steps,
        but these are ignored, are syntax errors, or are later transformed
        into :class:`ContainerToken` or :class:`FunctionToken`.

    .. attribute:: value

        The parsed value:

        * INTEGER, NUMBER, PERCENTAGE or DIMENSION tokens: the numeric value
          as an int or float.
        * STRING tokens: the unescaped string without quotes
        * URI tokens: the unescaped URI without quotes or
          ``url(`` and ``)`` markers.
        * IDENT, ATKEYWORD or HASH tokens: the unescaped token,
          with ``@`` or ``#`` markers left as-is
        * Other tokens: same as :attr:`as_css`

        *Unescaped* refers to the various escaping methods based on the
        backslash ``\`` character in CSS syntax.

    .. attribute:: unit

        * DIMENSION tokens: the normalized (unescaped, lower-case)
          unit name as a string. eg. ``'px'``
        * PERCENTAGE tokens: the string ``'%'``
        * Other tokens: ``None``

    .. attribute:: line

        The line number in the CSS source of the start of this token.

    .. attribute:: column

        The column number (inside a source line) of the start of this token.

    """
    is_container = False
    __slots__ = 'type', '_as_css', 'value', 'unit', 'line', 'column'

    def __init__(self, type_, css_value, value, unit, line, column):
        self.type = type_
        self._as_css = css_value
        self.value = value
        self.unit = unit
        self.line = line
        self.column = column

    def as_css(self):
        """
        Return as an Unicode string the CSS representation of the token,
        as parsed in the source.
        """
        return self._as_css

    def __repr__(self):
        return ('<Token {0.type} at {0.line}:{0.column} {0.value!r}{1}>'
                .format(self, self.unit or ''))


class ContainerToken(object):
    """A token that contains other (nested) tokens.

    .. attribute:: is_container

        Always ``True``.
        Helps to tell :class:`ContainerToken` apart from :class:`Token`.

    .. attribute:: type

        The type of token as a string. One of ``{``, ``(``, ``[`` or
        ``FUNCTION``. For ``FUNCTION``, the object is actually a
        :class:`FunctionToken`.

    .. attribute:: unit

        Always ``None``. Included to make :class:`ContainerToken` behave
        more like :class:`Token`.

    .. attribute:: content

        A list of :class:`Token` or nested :class:`ContainerToken`,
        not including the opening or closing token.

    .. attribute:: line

        The line number in the CSS source of the start of this token.

    .. attribute:: column

        The column number (inside a source line) of the start of this token.

    """
    is_container = True
    unit = None
    __slots__ = 'type', '_css_start', '_css_end', 'content', 'line', 'column'

    def __init__(self, type_, css_start, css_end, content, line, column):
        self.type = type_
        self._css_start = css_start
        self._css_end = css_end
        self.content = content
        self.line = line
        self.column = column

    def as_css(self):
        """
        Return as an Unicode string the CSS representation of the token,
        as parsed in the source.
        """
        parts = [self._css_start]
        parts.extend(token.as_css() for token in self.content)
        parts.append(self._css_end)
        return ''.join(parts)

    format_string = '<ContainerToken {0.type} at {0.line}:{0.column}>'

    def __repr__(self):
        return (self.format_string + ' {0.content}').format(self)


class FunctionToken(ContainerToken):
    """A specialized :class:`ContainerToken` for a ``FUNCTION`` group.
    Has an additional attribute:

    .. attribute:: function_name

        The unescaped name of the function, with the ``(`` marker removed.

    """
    __slots__ = 'function_name',

    def __init__(self, type_, css_start, css_end, function_name, content,
                 line, column):
        super(FunctionToken, self).__init__(
            type_, css_start, css_end, content, line, column)
        # Remove the ( marker:
        self.function_name = function_name[:-1]

    format_string = ('<FunctionToken {0.function_name}() at '
                     '{0.line}:{0.column}>')


class TokenList(list):
    """
    A mixed list of :class:`~.token_data.Token` and
    :class:`~.token_data.ContainerToken` objects.

    This is a subclass of the builtin :class:`~builtins.list` type.
    It can be iterated, indexed and sliced as usual, but also has some
    additional API:

    """
    @property
    def line(self):
        """The line number in the CSS source of the first token."""
        return self[0].line

    @property
    def column(self):
        """The column number (inside a source line) of the first token."""
        return self[0].column

    def as_css(self):
        """
        Return as an Unicode string the CSS representation of the tokens,
        as parsed in the source.
        """
        return ''.join(token.as_css() for token in self)


def load_c_tokenizer():
    from calibre_extensions import tokenizer
    tokens = list(':;(){}[]') + ['DELIM', 'INTEGER', 'STRING']
    tokenizer.init(
        COMPILED_TOKEN_REGEXPS, UNICODE_UNESCAPE, NEWLINE_UNESCAPE,
        SIMPLE_UNESCAPE, FIND_NEWLINES, TOKEN_DISPATCH, COMPILED_TOKEN_INDEXES,
        *tokens)
    return tokenizer
