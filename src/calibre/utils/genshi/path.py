# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2008 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Basic support for evaluating XPath expressions against streams.

>>> from genshi.input import XML
>>> doc = XML('''<doc>
...  <items count="4">
...       <item status="new">
...         <summary>Foo</summary>
...       </item>
...       <item status="closed">
...         <summary>Bar</summary>
...       </item>
...       <item status="closed" resolution="invalid">
...         <summary>Baz</summary>
...       </item>
...       <item status="closed" resolution="fixed">
...         <summary>Waz</summary>
...       </item>
...   </items>
... </doc>''')
>>> print doc.select('items/item[@status="closed" and '
...     '(@resolution="invalid" or not(@resolution))]/summary/text()')
BarBaz

Because the XPath engine operates on markup streams (as opposed to tree
structures), it only implements a subset of the full XPath 1.0 language.
"""

from math import ceil, floor
import operator
import re

from calibre.utils.genshi.core import Stream, Attrs, Namespace, QName
from calibre.utils.genshi.core import START, END, TEXT, START_NS, END_NS, COMMENT, PI, \
                        START_CDATA, END_CDATA

__all__ = ['Path', 'PathSyntaxError']
__docformat__ = 'restructuredtext en'


class Axis(object):
    """Defines constants for the various supported XPath axes."""

    ATTRIBUTE = 'attribute'
    CHILD = 'child'
    DESCENDANT = 'descendant'
    DESCENDANT_OR_SELF = 'descendant-or-self'
    SELF = 'self'

    def forname(cls, name):
        """Return the axis constant for the given name, or `None` if no such
        axis was defined.
        """
        return getattr(cls, name.upper().replace('-', '_'), None)
    forname = classmethod(forname)


ATTRIBUTE = Axis.ATTRIBUTE
CHILD = Axis.CHILD
DESCENDANT = Axis.DESCENDANT
DESCENDANT_OR_SELF = Axis.DESCENDANT_OR_SELF
SELF = Axis.SELF


class Path(object):
    """Implements basic XPath support on streams.
    
    Instances of this class represent a "compiled" XPath expression, and provide
    methods for testing the path against a stream, as well as extracting a
    substream matching that path.
    """

    def __init__(self, text, filename=None, lineno=-1):
        """Create the path object from a string.
        
        :param text: the path expression
        :param filename: the name of the file in which the path expression was
                         found (used in error messages)
        :param lineno: the line on which the expression was found
        """
        self.source = text
        self.paths = PathParser(text, filename, lineno).parse()

    def __repr__(self):
        paths = []
        for path in self.paths:
            steps = []
            for axis, nodetest, predicates in path:
                steps.append('%s::%s' % (axis, nodetest))
                for predicate in predicates:
                    steps[-1] += '[%s]' % predicate
            paths.append('/'.join(steps))
        return '<%s "%s">' % (self.__class__.__name__, '|'.join(paths))

    def select(self, stream, namespaces=None, variables=None):
        """Returns a substream of the given stream that matches the path.
        
        If there are no matches, this method returns an empty stream.
        
        >>> from genshi.input import XML
        >>> xml = XML('<root><elem><child>Text</child></elem></root>')
        
        >>> print Path('.//child').select(xml)
        <child>Text</child>
        
        >>> print Path('.//child/text()').select(xml)
        Text
        
        :param stream: the stream to select from
        :param namespaces: (optional) a mapping of namespace prefixes to URIs
        :param variables: (optional) a mapping of variable names to values
        :return: the substream matching the path, or an empty stream
        :rtype: `Stream`
        """
        if namespaces is None:
            namespaces = {}
        if variables is None:
            variables = {}
        stream = iter(stream)
        def _generate():
            test = self.test()
            for event in stream:
                result = test(event, namespaces, variables)
                if result is True:
                    yield event
                    if event[0] is START:
                        depth = 1
                        while depth > 0:
                            subevent = stream.next()
                            if subevent[0] is START:
                                depth += 1
                            elif subevent[0] is END:
                                depth -= 1
                            yield subevent
                            test(subevent, namespaces, variables,
                                 updateonly=True)
                elif result:
                    yield result
        return Stream(_generate(),
                      serializer=getattr(stream, 'serializer', None))

    def test(self, ignore_context=False):
        """Returns a function that can be used to track whether the path matches
        a specific stream event.
        
        The function returned expects the positional arguments ``event``,
        ``namespaces`` and ``variables``. The first is a stream event, while the
        latter two are a mapping of namespace prefixes to URIs, and a mapping
        of variable names to values, respectively. In addition, the function
        accepts an ``updateonly`` keyword argument that default to ``False``. If
        it is set to ``True``, the function only updates its internal state,
        but does not perform any tests or return a result.
        
        If the path matches the event, the function returns the match (for
        example, a `START` or `TEXT` event.) Otherwise, it returns ``None``.
        
        >>> from genshi.input import XML
        >>> xml = XML('<root><elem><child id="1"/></elem><child id="2"/></root>')
        >>> test = Path('child').test()
        >>> for event in xml:
        ...     if test(event, {}, {}):
        ...         print event[0], repr(event[1])
        START (QName(u'child'), Attrs([(QName(u'id'), u'2')]))
        
        :param ignore_context: if `True`, the path is interpreted like a pattern
                               in XSLT, meaning for example that it will match
                               at any depth
        :return: a function that can be used to test individual events in a
                 stream against the path
        :rtype: ``function``
        """
        paths = [(p, len(p), [0], [], [0] * len(p)) for p in [
            (ignore_context and [_DOTSLASHSLASH] or []) + p for p in self.paths
        ]]

        def _test(event, namespaces, variables, updateonly=False):
            kind, data, pos = event[:3]
            retval = None
            for steps, size, cursors, cutoff, counter in paths:
                # Manage the stack that tells us "where we are" in the stream
                if kind is END:
                    if cursors:
                        cursors.pop()
                    continue
                elif kind is START:
                    cursors.append(cursors and cursors[-1] or 0)
                elif kind is START_NS or kind is END_NS \
                        or kind is START_CDATA or kind is END_CDATA:
                    continue

                if updateonly or retval or not cursors:
                    continue
                cursor = cursors[-1]
                depth = len(cursors)

                if cutoff and depth + int(kind is not START) > cutoff[0]:
                    continue

                ctxtnode = not ignore_context and kind is START \
                                              and depth == 2
                matched = None
                while 1:
                    # Fetch the next location step
                    axis, nodetest, predicates = steps[cursor]

                    # If this is the start event for the context node, and the
                    # axis of the location step doesn't include the current
                    # element, skip the test
                    if ctxtnode and (axis is CHILD or axis is DESCENDANT):
                        break

                    # Is this the last step of the location path?
                    last_step = cursor + 1 == size

                    # Perform the actual node test
                    matched = nodetest(kind, data, pos, namespaces, variables)

                    # The node test matched
                    if matched:

                        # Check all the predicates for this step
                        if predicates:
                            for predicate in predicates:
                                pretval = predicate(kind, data, pos, namespaces,
                                                    variables)
                                if type(pretval) is float: # FIXME <- need to
                                                           # check this for
                                                           # other types that
                                                           # can be coerced to
                                                           # float
                                    counter[cursor] += 1
                                    if counter[cursor] != int(pretval):
                                        pretval = False
                                if not pretval:
                                    matched = None
                                    break

                        # Both the node test and the predicates matched
                        if matched:
                            if last_step:
                                if not ctxtnode or kind is not START \
                                        or axis is ATTRIBUTE or axis is SELF:
                                    retval = matched
                            elif not ctxtnode or axis is SELF \
                                              or axis is DESCENDANT_OR_SELF:
                                cursor += 1
                                cursors[-1] = cursor
                            cutoff[:] = []

                    if kind is START:
                        if last_step and not (axis is DESCENDANT or
                                              axis is DESCENDANT_OR_SELF):
                            cutoff[:] = [depth]

                        elif steps[cursor][0] is ATTRIBUTE:
                            # If the axis of the next location step is the
                            # attribute axis, we need to move on to processing
                            # that step without waiting for the next markup
                            # event
                            continue

                    # We're done with this step if it's the last step or the
                    # axis isn't "self"
                    if not matched or last_step or not (
                            axis is SELF or axis is DESCENDANT_OR_SELF):
                        break
                    if ctxtnode and axis is DESCENDANT_OR_SELF:
                        ctxtnode = False

                if (retval or not matched) and kind is START and \
                        not (axis is DESCENDANT or axis is DESCENDANT_OR_SELF):
                    # If this step is not a closure, it cannot be matched until
                    # the current element is closed... so we need to move the
                    # cursor back to the previous closure and retest that
                    # against the current element
                    backsteps = [(i, k, d, p) for i, (k, d, p)
                                 in enumerate(steps[:cursor])
                                 if k is DESCENDANT or k is DESCENDANT_OR_SELF]
                    backsteps.reverse()
                    for cursor, axis, nodetest, predicates in backsteps:
                        if nodetest(kind, data, pos, namespaces, variables):
                            cutoff[:] = []
                            break
                    cursors[-1] = cursor

            return retval

        return _test


class PathSyntaxError(Exception):
    """Exception raised when an XPath expression is syntactically incorrect."""

    def __init__(self, message, filename=None, lineno=-1, offset=-1):
        if filename:
            message = '%s (%s, line %d)' % (message, filename, lineno)
        Exception.__init__(self, message)
        self.filename = filename
        self.lineno = lineno
        self.offset = offset


class PathParser(object):
    """Tokenizes and parses an XPath expression."""

    _QUOTES = (("'", "'"), ('"', '"'))
    _TOKENS = ('::', ':', '..', '.', '//', '/', '[', ']', '()', '(', ')', '@',
               '=', '!=', '!', '|', ',', '>=', '>', '<=', '<', '$')
    _tokenize = re.compile('("[^"]*")|(\'[^\']*\')|((?:\d+)?\.\d+)|(%s)|([^%s\s]+)|\s+' % (
                           '|'.join([re.escape(t) for t in _TOKENS]),
                           ''.join([re.escape(t[0]) for t in _TOKENS]))).findall

    def __init__(self, text, filename=None, lineno=-1):
        self.filename = filename
        self.lineno = lineno
        self.tokens = filter(None, [dqstr or sqstr or number or token or name
                                    for dqstr, sqstr, number, token, name in
                                    self._tokenize(text)])
        self.pos = 0

    # Tokenizer

    at_end = property(lambda self: self.pos == len(self.tokens) - 1)
    cur_token = property(lambda self: self.tokens[self.pos])

    def next_token(self):
        self.pos += 1
        return self.tokens[self.pos]

    def peek_token(self):
        if not self.at_end:
            return self.tokens[self.pos + 1]
        return None

    # Recursive descent parser

    def parse(self):
        """Parses the XPath expression and returns a list of location path
        tests.
        
        For union expressions (such as `*|text()`), this function returns one
        test for each operand in the union. For patch expressions that don't
        use the union operator, the function always returns a list of size 1.
        
        Each path test in turn is a sequence of tests that correspond to the
        location steps, each tuples of the form `(axis, testfunc, predicates)`
        """
        paths = [self._location_path()]
        while self.cur_token == '|':
            self.next_token()
            paths.append(self._location_path())
        if not self.at_end:
            raise PathSyntaxError('Unexpected token %r after end of expression'
                                  % self.cur_token, self.filename, self.lineno)
        return paths

    def _location_path(self):
        steps = []
        while True:
            if self.cur_token.startswith('/'):
                if self.cur_token == '//':
                    steps.append((DESCENDANT_OR_SELF, NodeTest(), []))
                elif not steps:
                    raise PathSyntaxError('Absolute location paths not '
                                          'supported', self.filename,
                                          self.lineno)
                self.next_token()

            axis, nodetest, predicates = self._location_step()
            if not axis:
                axis = CHILD
            steps.append((axis, nodetest, predicates))

            if self.at_end or not self.cur_token.startswith('/'):
                break

        return steps

    def _location_step(self):
        if self.cur_token == '@':
            axis = ATTRIBUTE
            self.next_token()
        elif self.cur_token == '.':
            axis = SELF
        elif self.cur_token == '..':
            raise PathSyntaxError('Unsupported axis "parent"', self.filename,
                                  self.lineno)
        elif self.peek_token() == '::':
            axis = Axis.forname(self.cur_token)
            if axis is None:
                raise PathSyntaxError('Unsupport axis "%s"' % axis,
                                      self.filename, self.lineno)
            self.next_token()
            self.next_token()
        else:
            axis = None
        nodetest = self._node_test(axis or CHILD)
        predicates = []
        while self.cur_token == '[':
            predicates.append(self._predicate())
        return axis, nodetest, predicates

    def _node_test(self, axis=None):
        test = prefix = None
        next_token = self.peek_token()
        if next_token in ('(', '()'): # Node type test
            test = self._node_type()

        elif next_token == ':': # Namespace prefix
            prefix = self.cur_token
            self.next_token()
            localname = self.next_token()
            if localname == '*':
                test = QualifiedPrincipalTypeTest(axis, prefix)
            else:
                test = QualifiedNameTest(axis, prefix, localname)

        else: # Name test
            if self.cur_token == '*':
                test = PrincipalTypeTest(axis)
            elif self.cur_token == '.':
                test = NodeTest()
            else:
                test = LocalNameTest(axis, self.cur_token)

        if not self.at_end:
            self.next_token()
        return test

    def _node_type(self):
        name = self.cur_token
        self.next_token()

        args = []
        if self.cur_token != '()':
            # The processing-instruction() function optionally accepts the
            # name of the PI as argument, which must be a literal string
            self.next_token() # (
            if self.cur_token != ')':
                string = self.cur_token
                if (string[0], string[-1]) in self._QUOTES:
                    string = string[1:-1]
                args.append(string)

        cls = _nodetest_map.get(name)
        if not cls:
            raise PathSyntaxError('%s() not allowed here' % name, self.filename,
                                  self.lineno)
        return cls(*args)

    def _predicate(self):
        assert self.cur_token == '['
        self.next_token()
        expr = self._or_expr()
        if self.cur_token != ']':
            raise PathSyntaxError('Expected "]" to close predicate, '
                                  'but found "%s"' % self.cur_token,
                                  self.filename, self.lineno)
        if not self.at_end:
            self.next_token()
        return expr

    def _or_expr(self):
        expr = self._and_expr()
        while self.cur_token == 'or':
            self.next_token()
            expr = OrOperator(expr, self._and_expr())
        return expr

    def _and_expr(self):
        expr = self._equality_expr()
        while self.cur_token == 'and':
            self.next_token()
            expr = AndOperator(expr, self._equality_expr())
        return expr

    def _equality_expr(self):
        expr = self._relational_expr()
        while self.cur_token in ('=', '!='):
            op = _operator_map[self.cur_token]
            self.next_token()
            expr = op(expr, self._relational_expr())
        return expr

    def _relational_expr(self):
        expr = self._sub_expr()
        while self.cur_token in ('>', '>=', '<', '>='):
            op = _operator_map[self.cur_token]
            self.next_token()
            expr = op(expr, self._sub_expr())
        return expr

    def _sub_expr(self):
        token = self.cur_token
        if token != '(':
            return self._primary_expr()
        self.next_token()
        expr = self._or_expr()
        if self.cur_token != ')':
            raise PathSyntaxError('Expected ")" to close sub-expression, '
                                  'but found "%s"' % self.cur_token,
                                  self.filename, self.lineno)
        self.next_token()
        return expr

    def _primary_expr(self):
        token = self.cur_token
        if len(token) > 1 and (token[0], token[-1]) in self._QUOTES:
            self.next_token()
            return StringLiteral(token[1:-1])
        elif token[0].isdigit() or token[0] == '.':
            self.next_token()
            return NumberLiteral(as_float(token))
        elif token == '$':
            token = self.next_token()
            self.next_token()
            return VariableReference(token)
        elif not self.at_end and self.peek_token().startswith('('):
            return self._function_call()
        else:
            axis = None
            if token == '@':
                axis = ATTRIBUTE
                self.next_token()
            return self._node_test(axis)

    def _function_call(self):
        name = self.cur_token
        if self.next_token() == '()':
            args = []
        else:
            assert self.cur_token == '('
            self.next_token()
            args = [self._or_expr()]
            while self.cur_token == ',':
                self.next_token()
                args.append(self._or_expr())
            if not self.cur_token == ')':
                raise PathSyntaxError('Expected ")" to close function argument '
                                      'list, but found "%s"' % self.cur_token,
                                      self.filename, self.lineno)
        self.next_token()
        cls = _function_map.get(name)
        if not cls:
            raise PathSyntaxError('Unsupported function "%s"' % name,
                                  self.filename, self.lineno)
        return cls(*args)


# Type coercion

def as_scalar(value):
    """Convert value to a scalar. If a single element Attrs() object is passed
    the value of the single attribute will be returned."""
    if isinstance(value, Attrs):
        assert len(value) == 1
        return value[0][1]
    else:
        return value

def as_float(value):
    # FIXME - if value is a bool it will be coerced to 0.0 and consequently
    # compared as a float. This is probably not ideal.
    return float(as_scalar(value))

def as_long(value):
    return long(as_scalar(value))

def as_string(value):
    value = as_scalar(value)
    if value is False:
        return u''
    return unicode(value)

def as_bool(value):
    return bool(as_scalar(value))


# Node tests

class PrincipalTypeTest(object):
    """Node test that matches any event with the given principal type."""
    __slots__ = ['principal_type']
    def __init__(self, principal_type):
        self.principal_type = principal_type
    def __call__(self, kind, data, pos, namespaces, variables):
        if kind is START:
            if self.principal_type is ATTRIBUTE:
                return data[1] or None
            else:
                return True
    def __repr__(self):
        return '*'

class QualifiedPrincipalTypeTest(object):
    """Node test that matches any event with the given principal type in a
    specific namespace."""
    __slots__ = ['principal_type', 'prefix']
    def __init__(self, principal_type, prefix):
        self.principal_type = principal_type
        self.prefix = prefix
    def __call__(self, kind, data, pos, namespaces, variables):
        namespace = Namespace(namespaces.get(self.prefix))
        if kind is START:
            if self.principal_type is ATTRIBUTE and data[1]:
                return Attrs([(name, value) for name, value in data[1]
                              if name in namespace]) or None
            else:
                return data[0] in namespace
    def __repr__(self):
        return '%s:*' % self.prefix

class LocalNameTest(object):
    """Node test that matches any event with the given principal type and
    local name.
    """
    __slots__ = ['principal_type', 'name']
    def __init__(self, principal_type, name):
        self.principal_type = principal_type
        self.name = name
    def __call__(self, kind, data, pos, namespaces, variables):
        if kind is START:
            if self.principal_type is ATTRIBUTE and self.name in data[1]:
                return Attrs([(self.name, data[1].get(self.name))])
            else:
                return data[0].localname == self.name
    def __repr__(self):
        return self.name

class QualifiedNameTest(object):
    """Node test that matches any event with the given principal type and
    qualified name.
    """
    __slots__ = ['principal_type', 'prefix', 'name']
    def __init__(self, principal_type, prefix, name):
        self.principal_type = principal_type
        self.prefix = prefix
        self.name = name
    def __call__(self, kind, data, pos, namespaces, variables):
        qname = QName('%s}%s' % (namespaces.get(self.prefix), self.name))
        if kind is START:
            if self.principal_type is ATTRIBUTE and qname in data[1]:
                return Attrs([(self.name, data[1].get(self.name))])
            else:
                return data[0] == qname
    def __repr__(self):
        return '%s:%s' % (self.prefix, self.name)

class CommentNodeTest(object):
    """Node test that matches any comment events."""
    __slots__ = []
    def __call__(self, kind, data, pos, namespaces, variables):
        return kind is COMMENT
    def __repr__(self):
        return 'comment()'

class NodeTest(object):
    """Node test that matches any node."""
    __slots__ = []
    def __call__(self, kind, data, pos, namespaces, variables):
        if kind is START:
            return True
        return kind, data, pos
    def __repr__(self):
        return 'node()'

class ProcessingInstructionNodeTest(object):
    """Node test that matches any processing instruction event."""
    __slots__ = ['target']
    def __init__(self, target=None):
        self.target = target
    def __call__(self, kind, data, pos, namespaces, variables):
        return kind is PI and (not self.target or data[0] == self.target)
    def __repr__(self):
        arg = ''
        if self.target:
            arg = '"' + self.target + '"'
        return 'processing-instruction(%s)' % arg

class TextNodeTest(object):
    """Node test that matches any text event."""
    __slots__ = []
    def __call__(self, kind, data, pos, namespaces, variables):
        return kind is TEXT
    def __repr__(self):
        return 'text()'

_nodetest_map = {'comment': CommentNodeTest, 'node': NodeTest,
                 'processing-instruction': ProcessingInstructionNodeTest,
                 'text': TextNodeTest}

# Functions

class Function(object):
    """Base class for function nodes in XPath expressions."""

class BooleanFunction(Function):
    """The `boolean` function, which converts its argument to a boolean
    value.
    """
    __slots__ = ['expr']
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos, namespaces, variables):
        val = self.expr(kind, data, pos, namespaces, variables)
        return as_bool(val)
    def __repr__(self):
        return 'boolean(%r)' % self.expr

class CeilingFunction(Function):
    """The `ceiling` function, which returns the nearest lower integer number
    for the given number.
    """
    __slots__ = ['number']
    def __init__(self, number):
        self.number = number
    def __call__(self, kind, data, pos, namespaces, variables):
        number = self.number(kind, data, pos, namespaces, variables)
        return ceil(as_float(number))
    def __repr__(self):
        return 'ceiling(%r)' % self.number

class ConcatFunction(Function):
    """The `concat` function, which concatenates (joins) the variable number of
    strings it gets as arguments.
    """
    __slots__ = ['exprs']
    def __init__(self, *exprs):
        self.exprs = exprs
    def __call__(self, kind, data, pos, namespaces, variables):
        strings = []
        for item in [expr(kind, data, pos, namespaces, variables)
                     for expr in self.exprs]:
            strings.append(as_string(item))
        return u''.join(strings)
    def __repr__(self):
        return 'concat(%s)' % ', '.join([repr(expr) for expr in self.exprs])

class ContainsFunction(Function):
    """The `contains` function, which returns whether a string contains a given
    substring.
    """
    __slots__ = ['string1', 'string2']
    def __init__(self, string1, string2):
        self.string1 = string1
        self.string2 = string2
    def __call__(self, kind, data, pos, namespaces, variables):
        string1 = self.string1(kind, data, pos, namespaces, variables)
        string2 = self.string2(kind, data, pos, namespaces, variables)
        return as_string(string2) in as_string(string1)
    def __repr__(self):
        return 'contains(%r, %r)' % (self.string1, self.string2)

class MatchesFunction(Function):
    """The `matches` function, which returns whether a string matches a regular
    expression.
    """
    __slots__ = ['string1', 'string2']
    flag_mapping = {'s': re.S, 'm': re.M, 'i': re.I, 'x': re.X}

    def __init__(self, string1, string2, flags=''):
        self.string1 = string1
        self.string2 = string2
        self.flags = self._map_flags(flags)
    def __call__(self, kind, data, pos, namespaces, variables):
        string1 = as_string(self.string1(kind, data, pos, namespaces, variables))
        string2 = as_string(self.string2(kind, data, pos, namespaces, variables))
        return re.search(string2, string1, self.flags)
    def _map_flags(self, flags):
        return reduce(operator.or_,
                      [self.flag_map[flag] for flag in flags], re.U)
    def __repr__(self):
        return 'contains(%r, %r)' % (self.string1, self.string2)

class FalseFunction(Function):
    """The `false` function, which always returns the boolean `false` value."""
    __slots__ = []
    def __call__(self, kind, data, pos, namespaces, variables):
        return False
    def __repr__(self):
        return 'false()'

class FloorFunction(Function):
    """The `ceiling` function, which returns the nearest higher integer number
    for the given number.
    """
    __slots__ = ['number']
    def __init__(self, number):
        self.number = number
    def __call__(self, kind, data, pos, namespaces, variables):
        number = self.number(kind, data, pos, namespaces, variables)
        return floor(as_float(number))
    def __repr__(self):
        return 'floor(%r)' % self.number

class LocalNameFunction(Function):
    """The `local-name` function, which returns the local name of the current
    element.
    """
    __slots__ = []
    def __call__(self, kind, data, pos, namespaces, variables):
        if kind is START:
            return data[0].localname
    def __repr__(self):
        return 'local-name()'

class NameFunction(Function):
    """The `name` function, which returns the qualified name of the current
    element.
    """
    __slots__ = []
    def __call__(self, kind, data, pos, namespaces, variables):
        if kind is START:
            return data[0]
    def __repr__(self):
        return 'name()'

class NamespaceUriFunction(Function):
    """The `namespace-uri` function, which returns the namespace URI of the
    current element.
    """
    __slots__ = []
    def __call__(self, kind, data, pos, namespaces, variables):
        if kind is START:
            return data[0].namespace
    def __repr__(self):
        return 'namespace-uri()'

class NotFunction(Function):
    """The `not` function, which returns the negated boolean value of its
    argument.
    """
    __slots__ = ['expr']
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos, namespaces, variables):
        return not as_bool(self.expr(kind, data, pos, namespaces, variables))
    def __repr__(self):
        return 'not(%s)' % self.expr

class NormalizeSpaceFunction(Function):
    """The `normalize-space` function, which removes leading and trailing
    whitespace in the given string, and replaces multiple adjacent whitespace
    characters inside the string with a single space.
    """
    __slots__ = ['expr']
    _normalize = re.compile(r'\s{2,}').sub
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos, namespaces, variables):
        string = self.expr(kind, data, pos, namespaces, variables)
        return self._normalize(' ', as_string(string).strip())
    def __repr__(self):
        return 'normalize-space(%s)' % repr(self.expr)

class NumberFunction(Function):
    """The `number` function that converts its argument to a number."""
    __slots__ = ['expr']
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos, namespaces, variables):
        val = self.expr(kind, data, pos, namespaces, variables)
        return as_float(val)
    def __repr__(self):
        return 'number(%r)' % self.expr

class RoundFunction(Function):
    """The `round` function, which returns the nearest integer number for the
    given number.
    """
    __slots__ = ['number']
    def __init__(self, number):
        self.number = number
    def __call__(self, kind, data, pos, namespaces, variables):
        number = self.number(kind, data, pos, namespaces, variables)
        return round(as_float(number))
    def __repr__(self):
        return 'round(%r)' % self.number

class StartsWithFunction(Function):
    """The `starts-with` function that returns whether one string starts with
    a given substring.
    """
    __slots__ = ['string1', 'string2']
    def __init__(self, string1, string2):
        self.string1 = string1
        self.string2 = string2
    def __call__(self, kind, data, pos, namespaces, variables):
        string1 = self.string1(kind, data, pos, namespaces, variables)
        string2 = self.string2(kind, data, pos, namespaces, variables)
        return as_string(string1).startswith(as_string(string2))
    def __repr__(self):
        return 'starts-with(%r, %r)' % (self.string1, self.string2)

class StringLengthFunction(Function):
    """The `string-length` function that returns the length of the given
    string.
    """
    __slots__ = ['expr']
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos, namespaces, variables):
        string = self.expr(kind, data, pos, namespaces, variables)
        return len(as_string(string))
    def __repr__(self):
        return 'string-length(%r)' % self.expr

class SubstringFunction(Function):
    """The `substring` function that returns the part of a string that starts
    at the given offset, and optionally limited to the given length.
    """
    __slots__ = ['string', 'start', 'length']
    def __init__(self, string, start, length=None):
        self.string = string
        self.start = start
        self.length = length
    def __call__(self, kind, data, pos, namespaces, variables):
        string = self.string(kind, data, pos, namespaces, variables)
        start = self.start(kind, data, pos, namespaces, variables)
        length = 0
        if self.length is not None:
            length = self.length(kind, data, pos, namespaces, variables)
        return string[as_long(start):len(as_string(string)) - as_long(length)]
    def __repr__(self):
        if self.length is not None:
            return 'substring(%r, %r, %r)' % (self.string, self.start,
                                              self.length)
        else:
            return 'substring(%r, %r)' % (self.string, self.start)

class SubstringAfterFunction(Function):
    """The `substring-after` function that returns the part of a string that
    is found after the given substring.
    """
    __slots__ = ['string1', 'string2']
    def __init__(self, string1, string2):
        self.string1 = string1
        self.string2 = string2
    def __call__(self, kind, data, pos, namespaces, variables):
        string1 = as_string(self.string1(kind, data, pos, namespaces, variables))
        string2 = as_string(self.string2(kind, data, pos, namespaces, variables))
        index = string1.find(string2)
        if index >= 0:
            return string1[index + len(string2):]
        return u''
    def __repr__(self):
        return 'substring-after(%r, %r)' % (self.string1, self.string2)

class SubstringBeforeFunction(Function):
    """The `substring-before` function that returns the part of a string that
    is found before the given substring.
    """
    __slots__ = ['string1', 'string2']
    def __init__(self, string1, string2):
        self.string1 = string1
        self.string2 = string2
    def __call__(self, kind, data, pos, namespaces, variables):
        string1 = as_string(self.string1(kind, data, pos, namespaces, variables))
        string2 = as_string(self.string2(kind, data, pos, namespaces, variables))
        index = string1.find(string2)
        if index >= 0:
            return string1[:index]
        return u''
    def __repr__(self):
        return 'substring-after(%r, %r)' % (self.string1, self.string2)

class TranslateFunction(Function):
    """The `translate` function that translates a set of characters in a
    string to target set of characters.
    """
    __slots__ = ['string', 'fromchars', 'tochars']
    def __init__(self, string, fromchars, tochars):
        self.string = string
        self.fromchars = fromchars
        self.tochars = tochars
    def __call__(self, kind, data, pos, namespaces, variables):
        string = as_string(self.string(kind, data, pos, namespaces, variables))
        fromchars = as_string(self.fromchars(kind, data, pos, namespaces, variables))
        tochars = as_string(self.tochars(kind, data, pos, namespaces, variables))
        table = dict(zip([ord(c) for c in fromchars],
                         [ord(c) for c in tochars]))
        return string.translate(table)
    def __repr__(self):
        return 'translate(%r, %r, %r)' % (self.string, self.fromchars,
                                          self.tochars)

class TrueFunction(Function):
    """The `true` function, which always returns the boolean `true` value."""
    __slots__ = []
    def __call__(self, kind, data, pos, namespaces, variables):
        return True
    def __repr__(self):
        return 'true()'

_function_map = {'boolean': BooleanFunction, 'ceiling': CeilingFunction,
                 'concat': ConcatFunction, 'contains': ContainsFunction,
                 'matches': MatchesFunction, 'false': FalseFunction, 'floor':
                 FloorFunction, 'local-name': LocalNameFunction, 'name':
                 NameFunction, 'namespace-uri': NamespaceUriFunction,
                 'normalize-space': NormalizeSpaceFunction, 'not': NotFunction,
                 'number': NumberFunction, 'round': RoundFunction,
                 'starts-with': StartsWithFunction, 'string-length':
                 StringLengthFunction, 'substring': SubstringFunction,
                 'substring-after': SubstringAfterFunction, 'substring-before':
                 SubstringBeforeFunction, 'translate': TranslateFunction,
                 'true': TrueFunction}

# Literals & Variables

class Literal(object):
    """Abstract base class for literal nodes."""

class StringLiteral(Literal):
    """A string literal node."""
    __slots__ = ['text']
    def __init__(self, text):
        self.text = text
    def __call__(self, kind, data, pos, namespaces, variables):
        return self.text
    def __repr__(self):
        return '"%s"' % self.text

class NumberLiteral(Literal):
    """A number literal node."""
    __slots__ = ['number']
    def __init__(self, number):
        self.number = number
    def __call__(self, kind, data, pos, namespaces, variables):
        return self.number
    def __repr__(self):
        return str(self.number)

class VariableReference(Literal):
    """A variable reference node."""
    __slots__ = ['name']
    def __init__(self, name):
        self.name = name
    def __call__(self, kind, data, pos, namespaces, variables):
        return variables.get(self.name)
    def __repr__(self):
        return str(self.name)

# Operators

class AndOperator(object):
    """The boolean operator `and`."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos, namespaces, variables):
        lval = as_bool(self.lval(kind, data, pos, namespaces, variables))
        if not lval:
            return False
        rval = self.rval(kind, data, pos, namespaces, variables)
        return as_bool(rval)
    def __repr__(self):
        return '%s and %s' % (self.lval, self.rval)

class EqualsOperator(object):
    """The equality operator `=`."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos, namespaces, variables):
        lval = as_scalar(self.lval(kind, data, pos, namespaces, variables))
        rval = as_scalar(self.rval(kind, data, pos, namespaces, variables))
        return lval == rval
    def __repr__(self):
        return '%s=%s' % (self.lval, self.rval)

class NotEqualsOperator(object):
    """The equality operator `!=`."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos, namespaces, variables):
        lval = as_scalar(self.lval(kind, data, pos, namespaces, variables))
        rval = as_scalar(self.rval(kind, data, pos, namespaces, variables))
        return lval != rval
    def __repr__(self):
        return '%s!=%s' % (self.lval, self.rval)

class OrOperator(object):
    """The boolean operator `or`."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos, namespaces, variables):
        lval = as_bool(self.lval(kind, data, pos, namespaces, variables))
        if lval:
            return True
        rval = self.rval(kind, data, pos, namespaces, variables)
        return as_bool(rval)
    def __repr__(self):
        return '%s or %s' % (self.lval, self.rval)

class GreaterThanOperator(object):
    """The relational operator `>` (greater than)."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos, namespaces, variables):
        lval = self.lval(kind, data, pos, namespaces, variables)
        rval = self.rval(kind, data, pos, namespaces, variables)
        return as_float(lval) > as_float(rval)
    def __repr__(self):
        return '%s>%s' % (self.lval, self.rval)

class GreaterThanOrEqualOperator(object):
    """The relational operator `>=` (greater than or equal)."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos, namespaces, variables):
        lval = self.lval(kind, data, pos, namespaces, variables)
        rval = self.rval(kind, data, pos, namespaces, variables)
        return as_float(lval) >= as_float(rval)
    def __repr__(self):
        return '%s>=%s' % (self.lval, self.rval)

class LessThanOperator(object):
    """The relational operator `<` (less than)."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos, namespaces, variables):
        lval = self.lval(kind, data, pos, namespaces, variables)
        rval = self.rval(kind, data, pos, namespaces, variables)
        return as_float(lval) < as_float(rval)
    def __repr__(self):
        return '%s<%s' % (self.lval, self.rval)

class LessThanOrEqualOperator(object):
    """The relational operator `<=` (less than or equal)."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos, namespaces, variables):
        lval = self.lval(kind, data, pos, namespaces, variables)
        rval = self.rval(kind, data, pos, namespaces, variables)
        return as_float(lval) <= as_float(rval)
    def __repr__(self):
        return '%s<=%s' % (self.lval, self.rval)

_operator_map = {'=': EqualsOperator, '!=': NotEqualsOperator,
                 '>': GreaterThanOperator, '>=': GreaterThanOrEqualOperator,
                 '<': LessThanOperator, '>=': LessThanOrEqualOperator}


_DOTSLASHSLASH = (DESCENDANT_OR_SELF, PrincipalTypeTest(None), ())
