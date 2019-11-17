# coding: utf8
"""
    tinycss.css21
    -------------

    Parser for CSS 2.1
    http://www.w3.org/TR/CSS21/syndata.html

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from itertools import chain, islice

from tinycss.decoding import decode
from tinycss.token_data import TokenList
from tinycss.tokenizer import tokenize_grouped
from tinycss.parsing import (
    strip_whitespace, remove_whitespace, split_on_comma, validate_value,
    validate_any, ParseError)


#  stylesheet  : [ CDO | CDC | S | statement ]*;
#  statement   : ruleset | at-rule;
#  at-rule     : ATKEYWORD S* any* [ block | ';' S* ];
#  block       : '{' S* [ any | block | ATKEYWORD S* | ';' S* ]* '}' S*;
#  ruleset     : selector? '{' S* declaration? [ ';' S* declaration? ]* '}' S*;
#  selector    : any+;
#  declaration : property S* ':' S* value;
#  property    : IDENT;
#  value       : [ any | block | ATKEYWORD S* ]+;
#  any         : [ IDENT | NUMBER | PERCENTAGE | DIMENSION | STRING
#                | DELIM | URI | HASH | UNICODE-RANGE | INCLUDES
#                | DASHMATCH | ':' | FUNCTION S* [any|unused]* ')'
#                | '(' S* [any|unused]* ')' | '[' S* [any|unused]* ']'
#                ] S*;
#  unused      : block | ATKEYWORD S* | ';' S* | CDO S* | CDC S*;


class Stylesheet(object):
    """
    A parsed CSS stylesheet.

    .. attribute:: rules

        A mixed list, in source order, of :class:`RuleSet` and various
        at-rules such as :class:`ImportRule`, :class:`MediaRule`
        and :class:`PageRule`.
        Use their :obj:`at_keyword` attribute to distinguish them.

    .. attribute:: errors

        A list of :class:`~.parsing.ParseError`. Invalid rules and declarations
        are ignored, with the details logged in this list.

    .. attribute:: encoding

        The character encoding that was used to decode the stylesheet
        from bytes, or ``None`` for Unicode stylesheets.

    """
    def __init__(self, rules, errors, encoding):
        self.rules = rules
        self.errors = errors
        self.encoding = encoding

    def __repr__(self):
        return '<{0.__class__.__name__} {1} rules {2} errors>'.format(
            self, len(self.rules), len(self.errors))


class AtRule(object):
    """
    An unparsed at-rule.

    .. attribute:: at_keyword

        The normalized (lower-case) at-keyword as a string. Eg: ``'@page'``

    .. attribute:: head

        The part of the at-rule between the at-keyword and the ``{``
        marking the body, or the ``;`` marking the end of an at-rule without
        a body.  A :class:`~.token_data.TokenList`.

    .. attribute:: body

        The content of the body between ``{`` and ``}`` as a
        :class:`~.token_data.TokenList`, or ``None`` if there is no body
        (ie. if the rule ends with ``;``).

    The head was validated against the core grammar but **not** the body,
    as the body might contain declarations. In case of an error in a
    declaration, parsing should continue from the next declaration.
    The whole rule should not be ignored as it would be for an error
    in the head.

    These at-rules are expected to be parsed further before reaching
    the user API.

    """

    __slots__ = 'at_keyword', 'head', 'body', 'line', 'column'

    def __init__(self, at_keyword, head, body, line, column):
        self.at_keyword = at_keyword
        self.head = TokenList(head)
        self.body = TokenList(body) if body is not None else body
        self.line = line
        self.column = column

    def __repr__(self):
        return ('<{0.__class__.__name__} {0.line}:{0.column} {0.at_keyword}>'
                .format(self))


class RuleSet(object):
    """A ruleset.

    .. attribute:: at_keyword

        Always ``None``. Helps to tell rulesets apart from at-rules.

    .. attribute:: selector

        The selector as a :class:`~.token_data.TokenList`.
        In CSS 3, this is actually called a selector group.

        ``rule.selector.as_css()`` gives the selector as a string.
        This string can be used with *cssselect*, see :ref:`selectors3`.

    .. attribute:: declarations

        The list of :class:`Declaration`, in source order.

    """

    at_keyword = None
    __slots__ = 'selector', 'declarations', 'line', 'column'

    def __init__(self, selector, declarations, line, column):
        self.selector = TokenList(selector)
        self.declarations = declarations
        self.line = line
        self.column = column

    def __repr__(self):
        return ('<{0.__class__.__name__} at {0.line}:{0.column} {1}>'
                .format(self, self.selector.as_css()))


class Declaration(object):
    """A property declaration.

    .. attribute:: name

        The property name as a normalized (lower-case) string.

    .. attribute:: value

        The property value as a :class:`~.token_data.TokenList`.

        The value is not parsed. UAs using tinycss may only support
        some properties or some values and tinycss does not know which.
        They need to parse values themselves and ignore declarations with
        unknown or unsupported properties or values, and fall back
        on any previous declaration.

        :mod:`tinycss.color3` parses color values, but other values
        will need specific parsing/validation code.

    .. attribute:: priority

        Either the string ``'important'`` or ``None``.

    """
    __slots__ = 'name', 'value', 'priority', 'line', 'column'

    def __init__(self, name, value, priority, line, column):
        self.name = name
        self.value = TokenList(value)
        self.priority = priority
        self.line = line
        self.column = column

    def __repr__(self):
        priority = ' !' + self.priority if self.priority else ''
        return ('<{0.__class__.__name__} {0.line}:{0.column}'
                ' {0.name}: {1}{2}>'.format(
                    self, self.value.as_css(), priority))


class PageRule(object):
    """A parsed CSS 2.1 @page rule.

    .. attribute:: at_keyword

        Always ``'@page'``

    .. attribute:: selector

        The page selector.
        In CSS 2.1 this is either ``None`` (no selector), or the string
        ``'first'``, ``'left'`` or ``'right'`` for the pseudo class
        of the same name.

    .. attribute:: specificity

        Specificity of the page selector. This is a tuple of four integers,
        but these tuples are mostly meant to be compared to each other.

    .. attribute:: declarations

        A list of :class:`Declaration`, in source order.

    .. attribute:: at_rules

        The list of parsed at-rules inside the @page block, in source order.
        Always empty for CSS 2.1.

    """
    at_keyword = '@page'
    __slots__ = 'selector', 'specificity', 'declarations', 'at_rules', 'line', 'column'

    def __init__(self, selector, specificity, declarations, at_rules,
                 line, column):
        self.selector = selector
        self.specificity = specificity
        self.declarations = declarations
        self.at_rules = at_rules
        self.line = line
        self.column = column

    def __repr__(self):
        return ('<{0.__class__.__name__} {0.line}:{0.column}'
                ' {0.selector}>'.format(self))


class MediaRule(object):
    """A parsed @media rule.

    .. attribute:: at_keyword

        Always ``'@media'``

    .. attribute:: media

        For CSS 2.1 without media queries: the media types
        as a list of strings.

    .. attribute:: rules

        The list :class:`RuleSet` and various at-rules inside the @media
        block, in source order.

    """
    at_keyword = '@media'
    __slots__ = 'media', 'rules', 'line', 'column'

    def __init__(self, media, rules, line, column):
        self.media = media
        self.rules = rules
        self.line = line
        self.column = column

    def __repr__(self):
        return ('<{0.__class__.__name__} {0.line}:{0.column}'
                ' {0.media}>'.format(self))


class ImportRule(object):
    """A parsed @import rule.

    .. attribute:: at_keyword

        Always ``'@import'``

    .. attribute:: uri

        The URI to be imported, as read from the stylesheet.
        (URIs are not made absolute.)

    .. attribute:: media

        For CSS 2.1 without media queries: the media types
        as a list of strings.
        This attribute is explicitly ``['all']`` if the media was omitted
        in the source.

    """
    at_keyword = '@import'
    __slots__ = 'uri', 'media', 'line', 'column'

    def __init__(self, uri, media, line, column):
        self.uri = uri
        self.media = media
        self.line = line
        self.column = column

    def __repr__(self):
        return ('<{0.__class__.__name__} {0.line}:{0.column}'
                ' {0.uri}>'.format(self))


def _remove_at_charset(tokens):
    """Remove any valid @charset at the beggining of a token stream.

    :param tokens:
        An iterable of tokens
    :returns:
        A possibly truncated iterable of tokens

    """
    tokens = iter(tokens)
    header = list(islice(tokens, 4))
    if [t.type for t in header] == ['ATKEYWORD', 'S', 'STRING', ';']:
        atkw, space, string, semicolon = header
        if ((atkw.value, space.value) == ('@charset', ' ')
                and string.as_css()[0] == '"'):
            # Found a valid @charset rule, only keep what’s after it.
            return tokens
    return chain(header, tokens)


class CSS21Parser(object):
    """Parser for CSS 2.1

    This parser supports the core CSS syntax as well as @import, @media,
    @page and !important.

    Note that property values are still not parsed, as UAs using this
    parser may only support some properties or some values.

    Currently the parser holds no state. It being a class only allows
    subclassing and overriding its methods.

    """

    def __init__(self):
        self.at_parsers = {
            '@' + x:getattr(self, 'parse_%s_rule' % x) for x in ('media', 'page', 'import', 'charset')}

    # User API:

    def parse_stylesheet_file(self, css_file, protocol_encoding=None,
                             linking_encoding=None, document_encoding=None):
        """Parse a stylesheet from a file or filename.

        Character encoding-related parameters and behavior are the same
        as in :meth:`parse_stylesheet_bytes`.

        :param css_file:
            Either a file (any object with a :meth:`~file.read` method)
            or a filename.
        :return:
            A :class:`Stylesheet`.

        """
        if hasattr(css_file, 'read'):
            css_bytes = css_file.read()
        else:
            with open(css_file, 'rb') as fd:
                css_bytes = fd.read()
        return self.parse_stylesheet_bytes(css_bytes, protocol_encoding,
                                           linking_encoding, document_encoding)

    def parse_stylesheet_bytes(self, css_bytes, protocol_encoding=None,
                               linking_encoding=None, document_encoding=None):
        """Parse a stylesheet from a byte string.

        The character encoding is determined from the passed metadata and the
        ``@charset`` rule in the stylesheet (if any).
        If no encoding information is available or decoding fails,
        decoding defaults to UTF-8 and then fall back on ISO-8859-1.

        :param css_bytes:
            A CSS stylesheet as a byte string.
        :param protocol_encoding:
            The "charset" parameter of a "Content-Type" HTTP header (if any),
            or similar metadata for other protocols.
        :param linking_encoding:
            ``<link charset="">`` or other metadata from the linking mechanism
            (if any)
        :param document_encoding:
            Encoding of the referring style sheet or document (if any)
        :return:
            A :class:`Stylesheet`.

        """
        css_unicode, encoding = decode(css_bytes, protocol_encoding,
                                       linking_encoding, document_encoding)
        return self.parse_stylesheet(css_unicode, encoding=encoding)

    def parse_stylesheet(self, css_unicode, encoding=None):
        """Parse a stylesheet from an Unicode string.

        :param css_unicode:
            A CSS stylesheet as an unicode string.
        :param encoding:
            The character encoding used to decode the stylesheet from bytes,
            if any.
        :return:
            A :class:`Stylesheet`.

        """
        tokens = tokenize_grouped(css_unicode)
        if encoding:
            tokens = _remove_at_charset(tokens)
        rules, errors = self.parse_rules(tokens, context='stylesheet')
        return Stylesheet(rules, errors, encoding)

    def parse_style_attr(self, css_source):
        """Parse a "style" attribute (eg. of an HTML element).

        This method only accepts Unicode as the source (HTML) document
        is supposed to handle the character encoding.

        :param css_source:
            The attribute value, as an unicode string.
        :return:
            A tuple of the list of valid :class:`Declaration` and
            a list of :class:`~.parsing.ParseError`.
        """
        return self.parse_declaration_list(tokenize_grouped(css_source))

    # API for subclasses:

    def parse_rules(self, tokens, context):
        """Parse a sequence of rules (rulesets and at-rules).

        :param tokens:
            An iterable of tokens.
        :param context:
            Either ``'stylesheet'`` or an at-keyword such as ``'@media'``.
            (Most at-rules are only allowed in some contexts.)
        :return:
            A tuple of a list of parsed rules and a list of
            :class:`~.parsing.ParseError`.

        """
        rules = []
        errors = []
        tokens = iter(tokens)
        for token in tokens:
            if token.type not in ('S', 'CDO', 'CDC'):
                try:
                    if token.type == 'ATKEYWORD':
                        rule = self.read_at_rule(token, tokens)
                        result = self.parse_at_rule(
                            rule, rules, errors, context)
                        rules.append(result)
                    else:
                        rule, rule_errors = self.parse_ruleset(token, tokens)
                        rules.append(rule)
                        errors.extend(rule_errors)
                except ParseError as exc:
                    errors.append(exc)
                    # Skip the entire rule
        return rules, errors

    def read_at_rule(self, at_keyword_token, tokens):
        """Read an at-rule from a token stream.

        :param at_keyword_token:
            The ATKEYWORD token that starts this at-rule
            You may have read it already to distinguish the rule
            from a ruleset.
        :param tokens:
            An iterator of subsequent tokens. Will be consumed just enough
            for one at-rule.
        :return:
            An unparsed :class:`AtRule`.
        :raises:
            :class:`~.parsing.ParseError` if the head is invalid for the core
            grammar. The body is **not** validated. See :class:`AtRule`.

        """
        # CSS syntax is case-insensitive
        at_keyword = at_keyword_token.value.lower()
        head = []
        # For the ParseError in case `tokens` is empty:
        token = at_keyword_token
        for token in tokens:
            if token.type in '{;':
                break
            # Ignore white space just after the at-keyword.
            else:
                head.append(token)
        # On unexpected end of stylesheet, pretend that a ';' was there
        head = strip_whitespace(head)
        for head_token in head:
            validate_any(head_token, 'at-rule head')
        body = token.content if token.type == '{' else None
        return AtRule(at_keyword, head, body,
                      at_keyword_token.line, at_keyword_token.column)

    def parse_at_rule(self, rule, previous_rules, errors, context):
        """Parse an at-rule.

        Subclasses that override this method must use ``super()`` and
        pass its return value for at-rules they do not know.

        In CSS 2.1, this method handles @charset, @import, @media and @page
        rules.

        :param rule:
            An unparsed :class:`AtRule`.
        :param previous_rules:
            The list of at-rules and rulesets that have been parsed so far
            in this context. This list can be used to decide if the current
            rule is valid. (For example, @import rules are only allowed
            before anything but a @charset rule.)
        :param context:
            Either ``'stylesheet'`` or an at-keyword such as ``'@media'``.
            (Most at-rules are only allowed in some contexts.)
        :raises:
            :class:`~.parsing.ParseError` if the rule is invalid.
        :return:
            A parsed at-rule

        """
        try:
            parser = self.at_parsers[rule.at_keyword]
        except KeyError:
            raise ParseError(rule, 'unknown at-rule in {0} context: {1}'
                                    .format(context, rule.at_keyword))
        else:
            return parser(rule, previous_rules, errors, context)

    def parse_page_rule(self, rule, previous_rules, errors, context):
        if context != 'stylesheet':
            raise ParseError(rule, '@page rule not allowed in ' + context)
        selector, specificity = self.parse_page_selector(rule.head)
        if rule.body is None:
            raise ParseError(rule,
                'invalid {0} rule: missing block'.format(rule.at_keyword))
        declarations, at_rules, rule_errors = \
            self.parse_declarations_and_at_rules(rule.body, '@page')
        errors.extend(rule_errors)
        return PageRule(selector, specificity, declarations, at_rules,
                        rule.line, rule.column)

    def parse_media_rule(self, rule, previous_rules, errors, context):
        if context != 'stylesheet':
            raise ParseError(rule, '@media rule not allowed in ' + context)
        media = self.parse_media(rule.head, errors)
        if rule.body is None:
            raise ParseError(rule,
                'invalid {0} rule: missing block'.format(rule.at_keyword))
        rules, rule_errors = self.parse_rules(rule.body, '@media')
        errors.extend(rule_errors)
        return MediaRule(media, rules, rule.line, rule.column)

    def parse_import_rule(self, rule, previous_rules, errors, context):
        if context != 'stylesheet':
            raise ParseError(rule,
                '@import rule not allowed in ' + context)
        for previous_rule in previous_rules:
            if previous_rule.at_keyword not in ('@charset', '@import'):
                if previous_rule.at_keyword:
                    type_ = 'an {0} rule'.format(previous_rule.at_keyword)
                else:
                    type_ = 'a ruleset'
                raise ParseError(previous_rule,
                    '@import rule not allowed after ' + type_)
        head = rule.head
        if not head:
            raise ParseError(rule,
                'expected URI or STRING for @import rule')
        if head[0].type not in ('URI', 'STRING'):
            raise ParseError(rule,
                'expected URI or STRING for @import rule, got '
                + head[0].type)
        uri = head[0].value
        media = self.parse_media(strip_whitespace(head[1:]), errors)
        if rule.body is not None:
            # The position of the ';' token would be best, but we don’t
            # have it anymore here.
            raise ParseError(head[-1], "expected ';', got a block")
        return ImportRule(uri, media, rule.line, rule.column)

    def parse_charset_rule(self, rule, previous_rules, errors, context):
        raise ParseError(rule, 'mis-placed or malformed @charset rule')

    def parse_media(self, tokens, errors):
        """For CSS 2.1, parse a list of media types.

        Media Queries are expected to override this.

        :param tokens:
            A list of tokens
        :raises:
            :class:`~.parsing.ParseError` on invalid media types/queries
        :returns:
            For CSS 2.1, a list of media types as strings
        """
        if not tokens:
            return ['all']
        media_types = []
        for part in split_on_comma(remove_whitespace(tokens)):
            types = [token.type for token in part]
            if types == ['IDENT']:
                media_types.append(part[0].value)
            else:
                raise ParseError(tokens[0], 'expected a media type'
                    + ((', got ' + ', '.join(types)) if types else ''))
        return media_types

    def parse_page_selector(self, tokens):
        """Parse an @page selector.

        :param tokens:
            An iterable of token, typically from the  ``head`` attribute of
            an unparsed :class:`AtRule`.
        :returns:
            A page selector. For CSS 2.1, this is ``'first'``, ``'left'``,
            ``'right'`` or ``None``.
        :raises:
            :class:`~.parsing.ParseError` on invalid selectors

        """
        if not tokens:
            return None, (0, 0)
        if (len(tokens) == 2 and tokens[0].type == ':'
                and tokens[1].type == 'IDENT'):
            pseudo_class = tokens[1].value
            specificity = {
                'first': (1, 0), 'left': (0, 1), 'right': (0, 1),
            }.get(pseudo_class)
            if specificity:
                return pseudo_class, specificity
        raise ParseError(tokens[0], 'invalid @page selector')

    def parse_declarations_and_at_rules(self, tokens, context):
        """Parse a mixed list of declarations and at rules, as found eg.
        in the body of an @page rule.

        Note that to add supported at-rules inside @page,
        :class:`~.page3.CSSPage3Parser` extends :meth:`parse_at_rule`,
        not this method.

        :param tokens:
            An iterable of token, typically from the  ``body`` attribute of
            an unparsed :class:`AtRule`.
        :param context:
            An at-keyword such as ``'@page'``.
            (Most at-rules are only allowed in some contexts.)
        :returns:
            A tuple of:

            * A list of :class:`Declaration`
            * A list of parsed at-rules (empty for CSS 2.1)
            * A list of :class:`~.parsing.ParseError`

        """
        at_rules = []
        declarations = []
        errors = []
        tokens = iter(tokens)
        for token in tokens:
            if token.type == 'ATKEYWORD':
                try:
                    rule = self.read_at_rule(token, tokens)
                    result = self.parse_at_rule(
                        rule, at_rules, errors, context)
                    at_rules.append(result)
                except ParseError as err:
                    errors.append(err)
            elif token.type != 'S':
                declaration_tokens = []
                while token and token.type != ';':
                    declaration_tokens.append(token)
                    token = next(tokens, None)
                if declaration_tokens:
                    try:
                        declarations.append(
                            self.parse_declaration(declaration_tokens))
                    except ParseError as err:
                        errors.append(err)
        return declarations, at_rules, errors

    def parse_ruleset(self, first_token, tokens):
        """Parse a ruleset: a selector followed by declaration block.

        :param first_token:
            The first token of the ruleset (probably of the selector).
            You may have read it already to distinguish the rule
            from an at-rule.
        :param tokens:
            an iterator of subsequent tokens. Will be consumed just enough
            for one ruleset.
        :return:
            a tuple of a :class:`RuleSet` and an error list.
            The errors are recovered :class:`~.parsing.ParseError` in declarations.
            (Parsing continues from the next declaration on such errors.)
        :raises:
            :class:`~.parsing.ParseError` if the selector is invalid for the
            core grammar.
            Note a that a selector can be valid for the core grammar but
            not for CSS 2.1 or another level.

        """
        selector = []
        for token in chain([first_token], tokens):
            if token.type == '{':
                # Parse/validate once we’ve read the whole rule
                selector = strip_whitespace(selector)
                if not selector:
                    raise ParseError(first_token, 'empty selector')
                for selector_token in selector:
                    validate_any(selector_token, 'selector')
                declarations, errors = self.parse_declaration_list(
                    token.content)
                ruleset = RuleSet(selector, declarations,
                                  first_token.line, first_token.column)
                return ruleset, errors
            else:
                selector.append(token)
        raise ParseError(token, 'no declaration block found for ruleset')

    def parse_declaration_list(self, tokens):
        """Parse a ``;`` separated declaration list.

        You may want to use :meth:`parse_declarations_and_at_rules` (or
        some other method that uses :func:`parse_declaration` directly)
        instead if you have not just declarations in the same context.

        :param tokens:
            an iterable of tokens. Should stop at (before) the end
            of the block, as marked by ``}``.
        :return:
            a tuple of the list of valid :class:`Declaration` and a list
            of :class:`~.parsing.ParseError`

        """
        # split at ';'
        parts = []
        this_part = []
        for token in tokens:
            if token.type == ';':
                parts.append(this_part)
                this_part = []
            else:
                this_part.append(token)
        parts.append(this_part)

        declarations = []
        errors = []
        for tokens in parts:
            tokens = strip_whitespace(tokens)
            if tokens:
                try:
                    declarations.append(self.parse_declaration(tokens))
                except ParseError as exc:
                    errors.append(exc)
                    # Skip the entire declaration
        return declarations, errors

    def parse_declaration(self, tokens):
        """Parse a single declaration.

        :param tokens:
            an iterable of at least one token. Should stop at (before)
            the end of the declaration, as marked by a ``;`` or ``}``.
            Empty declarations (ie. consecutive ``;`` with only white space
            in-between) should be skipped earlier and not passed to
            this method.
        :returns:
            a :class:`Declaration`
        :raises:
            :class:`~.parsing.ParseError` if the tokens do not match the
            'declaration' production of the core grammar.

        """
        tokens = iter(tokens)

        name_token = next(tokens)  # assume there is at least one
        if name_token.type == 'IDENT':
            # CSS syntax is case-insensitive
            property_name = name_token.value.lower()
        else:
            raise ParseError(name_token,
                'expected a property name, got {0}'.format(name_token.type))

        token = name_token  # In case ``tokens`` is now empty
        for token in tokens:
            if token.type == ':':
                break
            elif token.type != 'S':
                raise ParseError(
                    token, "expected ':', got {0}".format(token.type))
        else:
            raise ParseError(token, "expected ':'")

        value = strip_whitespace(list(tokens))
        if not value:
            raise ParseError(token, 'expected a property value')
        validate_value(value)
        value, priority = self.parse_value_priority(value)
        return Declaration(
            property_name, value, priority, name_token.line, name_token.column)

    def parse_value_priority(self, tokens):
        """Separate any ``!important`` marker at the end of a property value.

        :param tokens:
            A list of tokens for the property value.
        :returns:
            A tuple of the actual property value (a list of tokens)
            and the :attr:`~Declaration.priority`.
        """
        value = list(tokens)
        # Walk the token list from the end
        token = value.pop()
        if token.type == 'IDENT' and token.value.lower() == 'important':
            while value:
                token = value.pop()
                if token.type == 'DELIM' and token.value == '!':
                    # Skip any white space before the '!'
                    while value and value[-1].type == 'S':
                        value.pop()
                    if not value:
                        raise ParseError(
                            token, 'expected a value before !important')
                    return value, 'important'
                # Skip white space between '!' and 'important'
                elif token.type != 'S':
                    break
        return tokens, None
