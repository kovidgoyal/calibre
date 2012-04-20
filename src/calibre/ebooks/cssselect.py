"""CSS Selectors based on XPath.

This module supports selecting XML/HTML tags based on CSS selectors.
See the `CSSSelector` class for details.
"""

import re
from lxml import etree

__all__ = ['SelectorSyntaxError', 'ExpressionError',
           'CSSSelector']

try:
    _basestring = basestring
except NameError:
    _basestring = str

class SelectorSyntaxError(SyntaxError):
    pass

class ExpressionError(RuntimeError):
    pass

class CSSSelector(etree.XPath):
    """A CSS selector.

    Usage::

        >>> from lxml import etree, cssselect
        >>> select = cssselect.CSSSelector("a tag > child")

        >>> root = etree.XML("<a><b><c/><tag><child>TEXT</child></tag></b></a>")
        >>> [ el.tag for el in select(root) ]
        ['child']

    To use CSS namespaces, you need to pass a prefix-to-namespace
    mapping as ``namespaces`` keyword argument::

        >>> rdfns = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        >>> select_ns = cssselect.CSSSelector('root > rdf|Description',
        ...                                   namespaces={'rdf': rdfns})

        >>> rdf = etree.XML((
        ...     '<root xmlns:rdf="%s">'
        ...       '<rdf:Description>blah</rdf:Description>'
        ...     '</root>') % rdfns)
        >>> [(el.tag, el.text) for el in select_ns(rdf)]
        [('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description', 'blah')]
    """
    def __init__(self, css, namespaces=None):
        path = css_to_xpath_no_case(css)
        etree.XPath.__init__(self, path, namespaces=namespaces)
        self.css = css

    def __repr__(self):
        return '<%s %s for %r>' % (
            self.__class__.__name__,
            hex(abs(id(self)))[2:],
            self.css)

##############################
## Token objects:

try:
    _unicode = unicode
    _unichr = unichr
except NameError:
    # Python 3
    _unicode = str
    _unichr = chr

class _UniToken(_unicode):
    def __new__(cls, contents, pos):
        obj = _unicode.__new__(cls, contents)
        obj.pos = pos
        return obj

    def __repr__(self):
        return '%s(%s, %r)' % (
            self.__class__.__name__,
            _unicode.__repr__(self),
            self.pos)

class Symbol(_UniToken):
    pass

class String(_UniToken):
    pass

class Token(_UniToken):
    pass

############################################################
## Parsing
############################################################

##############################
## Syntax objects:

class Class(object):
    """
    Represents selector.class_name
    """

    def __init__(self, selector, class_name):
        self.selector = selector
        # Kovid: Lowercased
        self.class_name = class_name.lower()

    def __repr__(self):
        return '%s[%r.%s]' % (
            self.__class__.__name__,
            self.selector,
            self.class_name)

    def xpath(self):
        sel_xpath = self.selector.xpath()
        # Kovid: Lowercased
        sel_xpath.add_condition(
            "contains(concat(' ', normalize-space(%s), ' '), %s)" % (
                lower_case('@class'),
                xpath_literal(' '+self.class_name+' ')))
        return sel_xpath

class Function(object):
    """
    Represents selector:name(expr)
    """

    unsupported = [
        'target', 'lang', 'enabled', 'disabled',]

    def __init__(self, selector, type, name, expr):
        self.selector = selector
        self.type = type
        self.name = name
        self.expr = expr

    def __repr__(self):
        return '%s[%r%s%s(%r)]' % (
            self.__class__.__name__,
            self.selector,
            self.type, self.name, self.expr)

    def xpath(self):
        sel_path = self.selector.xpath()
        if self.name in self.unsupported:
            raise ExpressionError(
                "The pseudo-class %r is not supported" % self.name)
        method = '_xpath_' + self.name.replace('-', '_')
        if not hasattr(self, method):
            raise ExpressionError(
                "The pseudo-class %r is unknown" % self.name)
        method = getattr(self, method)
        return method(sel_path, self.expr)

    def _xpath_nth_child(self, xpath, expr, last=False,
                         add_name_test=True):
        a, b = parse_series(expr)
        if not a and not b and not last:
            # a=0 means nothing is returned...
            xpath.add_condition('false() and position() = 0')
            return xpath
        if add_name_test:
            xpath.add_name_test()
        xpath.add_star_prefix()
        if a == 0:
            if last:
                b = 'last() - %s' % b
            xpath.add_condition('position() = %s' % b)
            return xpath
        if last:
            # FIXME: I'm not sure if this is right
            a = -a
            b = -b
        if b > 0:
            b_neg = str(-b)
        else:
            b_neg = '+%s' % (-b)
        if a != 1:
            expr = ['(position() %s) mod %s = 0' % (b_neg, a)]
        else:
            expr = []
        if b >= 0:
            expr.append('position() >= %s' % b)
        elif b < 0 and last:
            expr.append('position() < (last() %s)' % b)
        expr = ' and '.join(expr)
        if expr:
            xpath.add_condition(expr)
        return xpath
        # FIXME: handle an+b, odd, even
        # an+b means every-a, plus b, e.g., 2n+1 means odd
        # 0n+b means b
        # n+0 means a=1, i.e., all elements
        # an means every a elements, i.e., 2n means even
        # -n means -1n
        # -1n+6 means elements 6 and previous

    def _xpath_nth_last_child(self, xpath, expr):
        return self._xpath_nth_child(xpath, expr, last=True)

    def _xpath_nth_of_type(self, xpath, expr):
        if xpath.element == '*':
            raise NotImplementedError(
                "*:nth-of-type() is not implemented")
        return self._xpath_nth_child(xpath, expr, add_name_test=False)

    def _xpath_nth_last_of_type(self, xpath, expr):
        return self._xpath_nth_child(xpath, expr, last=True, add_name_test=False)

    def _xpath_contains(self, xpath, expr):
        # text content, minus tags, must contain expr
        if isinstance(expr, Element):
            expr = expr._format_element()
        # Kovid: Use ASCII lower case that works
        xpath.add_condition('contains(%s), %s)' % (
                            lower_case('string(.)'),
                            xpath_literal(expr.lower())))
        return xpath

    def _xpath_not(self, xpath, expr):
        # everything for which not expr applies
        expr = expr.xpath()
        cond = expr.condition
        # FIXME: should I do something about element_path?
        xpath.add_condition('not(%s)' % cond)
        return xpath

# Kovid: Python functions dont work in lxml, so use translate()
# instead of the python lowercase function
def lower_case(arg):
    'An ASCII lowercase function'
    return ("translate(%s, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz')")%arg

class Pseudo(object):
    """
    Represents selector:ident
    """

    unsupported = ['indeterminate', 'first-line', 'first-letter',
                   'selection', 'before', 'after', 'link', 'visited',
                   'active', 'focus', 'hover']

    def __init__(self, element, type, ident):
        self.element = element
        assert type in (':', '::')
        self.type = type
        self.ident = ident

    def __repr__(self):
        return '%s[%r%s%s]' % (
            self.__class__.__name__,
            self.element,
            self.type, self.ident)

    def xpath(self):
        el_xpath = self.element.xpath()
        if self.ident in self.unsupported:
            raise ExpressionError(
                "The pseudo-class %r is unsupported" % self.ident)
        method = '_xpath_' + self.ident.replace('-', '_')
        if not hasattr(self, method):
            raise ExpressionError(
                "The pseudo-class %r is unknown" % self.ident)
        method = getattr(self, method)
        el_xpath = method(el_xpath)
        return el_xpath

    def _xpath_checked(self, xpath):
        # FIXME: is this really all the elements?
        xpath.add_condition("(@selected or @checked) and (name(.) = 'input' or name(.) = 'option')")
        return xpath

    def _xpath_root(self, xpath):
        # if this element is the root element
        raise NotImplementedError

    def _xpath_first_child(self, xpath):
        xpath.add_star_prefix()
        xpath.add_name_test()
        xpath.add_condition('position() = 1')
        return xpath

    def _xpath_last_child(self, xpath):
        xpath.add_star_prefix()
        xpath.add_name_test()
        xpath.add_condition('position() = last()')
        return xpath

    def _xpath_first_of_type(self, xpath):
        if xpath.element == '*':
            raise NotImplementedError(
                "*:first-of-type is not implemented")
        xpath.add_star_prefix()
        xpath.add_condition('position() = 1')
        return xpath

    def _xpath_last_of_type(self, xpath):
        if xpath.element == '*':
            raise NotImplementedError(
                "*:last-of-type is not implemented")
        xpath.add_star_prefix()
        xpath.add_condition('position() = last()')
        return xpath

    def _xpath_only_child(self, xpath):
        xpath.add_name_test()
        xpath.add_star_prefix()
        xpath.add_condition('last() = 1')
        return xpath

    def _xpath_only_of_type(self, xpath):
        if xpath.element == '*':
            raise NotImplementedError(
                "*:only-of-type is not implemented")
        xpath.add_condition('last() = 1')
        return xpath

    def _xpath_empty(self, xpath):
        xpath.add_condition("not(*) and not(normalize-space())")
        return xpath

class Attrib(object):
    """
    Represents selector[namespace|attrib operator value]
    """

    def __init__(self, selector, namespace, attrib, operator, value):
        self.selector = selector
        self.namespace = namespace
        self.attrib = attrib
        self.operator = operator
        self.value = value

    def __repr__(self):
        if self.operator == 'exists':
            return '%s[%r[%s]]' % (
                self.__class__.__name__,
                self.selector,
                self._format_attrib())
        else:
            return '%s[%r[%s %s %r]]' % (
                self.__class__.__name__,
                self.selector,
                self._format_attrib(),
                self.operator,
                self.value)

    def _format_attrib(self):
        if self.namespace == '*':
            return self.attrib
        else:
            return '%s|%s' % (self.namespace, self.attrib)

    def _xpath_attrib(self):
        # FIXME: if attrib is *?
        if self.namespace == '*':
            return '@' + self.attrib
        else:
            return '@%s:%s' % (self.namespace, self.attrib)

    def xpath(self):
        path = self.selector.xpath()
        attrib = self._xpath_attrib()
        value = self.value
        if self.operator == 'exists':
            assert not value
            path.add_condition(attrib)
        elif self.operator == '=':
            path.add_condition('%s = %s' % (attrib,
                                            xpath_literal(value)))
        elif self.operator == '!=':
            # FIXME: this seems like a weird hack...
            if value:
                path.add_condition('not(%s) or %s != %s'
                                   % (attrib, attrib, xpath_literal(value)))
            else:
                path.add_condition('%s != %s'
                                   % (attrib, xpath_literal(value)))
            #path.add_condition('%s != %s' % (attrib, xpath_literal(value)))
        elif self.operator == '~=':
            path.add_condition("contains(concat(' ', normalize-space(%s), ' '), %s)" % (attrib, xpath_literal(' '+value+' ')))
        elif self.operator == '|=':
            # Weird, but true...
            path.add_condition('%s = %s or starts-with(%s, %s)' % (
                attrib, xpath_literal(value),
                attrib, xpath_literal(value + '-')))
        elif self.operator == '^=':
            path.add_condition('starts-with(%s, %s)' % (
                attrib, xpath_literal(value)))
        elif self.operator == '$=':
            # Oddly there is a starts-with in XPath 1.0, but not ends-with
            path.add_condition('substring(%s, string-length(%s)-%s) = %s'
                               % (attrib, attrib, len(value)-1, xpath_literal(value)))
        elif self.operator == '*=':
            # FIXME: case sensitive?
            path.add_condition('contains(%s, %s)' % (
                attrib, xpath_literal(value)))
        else:
            assert 0, ("Unknown operator: %r" % self.operator)
        return path

class Element(object):
    """
    Represents namespace|element
    """

    def __init__(self, namespace, element):
        self.namespace = namespace
        self.element = element

    def __repr__(self):
        return '%s[%s]' % (
            self.__class__.__name__,
            self._format_element())

    def _format_element(self):
        if self.namespace == '*':
            return self.element
        else:
            return '%s|%s' % (self.namespace, self.element)

    def xpath(self):
        if self.namespace == '*':
            el = self.element.lower()
        else:
            # Kovid: Lowercased
            el = '%s:%s' % (self.namespace, self.element.lower())
        return XPathExpr(element=el)

class Hash(object):
    """
    Represents selector#id
    """

    def __init__(self, selector, id):
        self.selector = selector
        self.id = id

    def __repr__(self):
        return '%s[%r#%s]' % (
            self.__class__.__name__,
            self.selector, self.id)

    def xpath(self):
        path = self.selector.xpath()
        path.add_condition('@id = %s' % xpath_literal(self.id))
        return path

class Or(object):

    def __init__(self, items):
        self.items = items
    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__,
            self.items)

    def xpath(self):
        paths = [item.xpath() for item in self.items]
        return XPathExprOr(paths)

class CombinedSelector(object):

    _method_mapping = {
        ' ': 'descendant',
        '>': 'child',
        '+': 'direct_adjacent',
        '~': 'indirect_adjacent',
        }

    def __init__(self, selector, combinator, subselector):
        assert selector is not None
        self.selector = selector
        self.combinator = combinator
        self.subselector = subselector

    def __repr__(self):
        if self.combinator == ' ':
            comb = '<followed>'
        else:
            comb = self.combinator
        return '%s[%r %s %r]' % (
            self.__class__.__name__,
            self.selector,
            comb,
            self.subselector)

    def xpath(self):
        if self.combinator not in self._method_mapping:
            raise ExpressionError(
                "Unknown combinator: %r" % self.combinator)
        method = '_xpath_' + self._method_mapping[self.combinator]
        method = getattr(self, method)
        path = self.selector.xpath()
        return method(path, self.subselector)

    def _xpath_descendant(self, xpath, sub):
        # when sub is a descendant in any way of xpath
        xpath.join('/descendant::', sub.xpath())
        return xpath

    def _xpath_child(self, xpath, sub):
        # when sub is an immediate child of xpath
        xpath.join('/', sub.xpath())
        return xpath

    def _xpath_direct_adjacent(self, xpath, sub):
        # when sub immediately follows xpath
        xpath.join('/following-sibling::', sub.xpath())
        xpath.add_name_test()
        xpath.add_condition('position() = 1')
        return xpath

    def _xpath_indirect_adjacent(self, xpath, sub):
        # when sub comes somewhere after xpath as a sibling
        xpath.join('/following-sibling::', sub.xpath())
        return xpath

##############################
## XPathExpr objects:

_el_re = re.compile(r'^\w+\s*$', re.UNICODE)
_id_re = re.compile(r'^(\w*)#(\w+)\s*$', re.UNICODE)
_class_re = re.compile(r'^(\w*)\.(\w+)\s*$', re.UNICODE)


def css_to_xpath_no_case(css_expr, prefix='descendant-or-self::'):
    if isinstance(css_expr, _basestring):
        match = _el_re.search(css_expr)
        if match is not None:
            # Kovid: Lowercased
            return '%s%s' % (prefix, match.group(0).strip().lower())
        match = _id_re.search(css_expr)
        if match is not None:
            return "%s%s[@id = '%s']" % (
                prefix, match.group(1) or '*', match.group(2))
        match = _class_re.search(css_expr)
        if match is not None:
            # Kovid: lowercased
            return "%s%s[contains(concat(' ', normalize-space(%s), ' '), ' %s ')]" % (
                prefix, match.group(1).lower() or '*',
                lower_case('@class'), match.group(2).lower())
        css_expr = parse(css_expr)
    expr = css_expr.xpath()
    assert expr is not None, (
        "Got None for xpath expression from %s" % repr(css_expr))
    if prefix:
        expr.add_prefix(prefix)
    return _unicode(expr)

class XPathExpr(object):

    def __init__(self, prefix=None, path=None, element='*', condition=None,
                 star_prefix=False):
        self.prefix = prefix
        self.path = path
        self.element = element
        self.condition = condition
        self.star_prefix = star_prefix

    def __str__(self):
        path = ''
        if self.prefix is not None:
            path += _unicode(self.prefix)
        if self.path is not None:
            path += _unicode(self.path)
        path += _unicode(self.element)
        if self.condition:
            path += '[%s]' % self.condition
        return path

    def __repr__(self):
        return '%s[%s]' % (
            self.__class__.__name__, self)

    def add_condition(self, condition):
        if self.condition:
            self.condition = '%s and (%s)' % (self.condition, condition)
        else:
            self.condition = condition

    def add_path(self, part):
        if self.path is None:
            self.path = self.element
        else:
            self.path += self.element
        self.element = part

    def add_prefix(self, prefix):
        if self.prefix:
            self.prefix = prefix + self.prefix
        else:
            self.prefix = prefix

    def add_name_test(self):
        if self.element == '*':
            # We weren't doing a test anyway
            return
        self.add_condition("name() = %s" % xpath_literal(self.element))
        self.element = '*'

    def add_star_prefix(self):
        """
        Adds a /* prefix if there is no prefix.  This is when you need
        to keep context's constrained to a single parent.
        """
        if self.path:
            self.path += '*/'
        else:
            self.path = '*/'
        self.star_prefix = True

    def join(self, combiner, other):
        prefix = _unicode(self)
        prefix += combiner
        path = (other.prefix or '') + (other.path or '')
        # We don't need a star prefix if we are joining to this other
        # prefix; so we'll get rid of it
        if other.star_prefix and path == '*/':
            path = ''
        self.prefix = prefix
        self.path = path
        self.element = other.element
        self.condition = other.condition

class XPathExprOr(XPathExpr):
    """
    Represents |'d expressions.  Note that unfortunately it isn't
    the union, it's the sum, so duplicate elements will appear.
    """

    def __init__(self, items, prefix=None):
        for item in items:
            assert item is not None
        self.items = items
        self.prefix = prefix

    def __str__(self):
        prefix = self.prefix or ''
        return ' | '.join(["%s%s" % (prefix,i) for i in self.items])

split_at_single_quotes = re.compile("('+)").split

def xpath_literal(s):
    if isinstance(s, Element):
        # This is probably a symbol that looks like an expression...
        s = s._format_element()
    else:
        s = _unicode(s)
    if "'" not in s:
        s = "'%s'" % s
    elif '"' not in s:
        s = '"%s"' % s
    else:
        s = "concat(%s)" % ','.join([
            (("'" in part) and '"%s"' or "'%s'") % part
            for part in split_at_single_quotes(s) if part
            ])
    return s

##############################
## Parsing functions

def parse(string):
    stream = TokenStream(tokenize(string))
    stream.source = string
    try:
        return parse_selector_group(stream)
    except SelectorSyntaxError:
        import sys
        e = sys.exc_info()[1]
        message = "%s at %s -> %r" % (
            e, stream.used, stream.peek())
        e.msg = message
        if sys.version_info < (2,6):
            e.message = message
        e.args = tuple([message])
        raise

def parse_selector_group(stream):
    result = []
    while 1:
        result.append(parse_selector(stream))
        if stream.peek() == ',':
            stream.next()
        else:
            break
    if len(result) == 1:
        return result[0]
    else:
        return Or(result)

def parse_selector(stream):
    result = parse_simple_selector(stream)
    while 1:
        peek = stream.peek()
        if peek == ',' or peek is None:
            return result
        elif peek in ('+', '>', '~'):
            # A combinator
            combinator = stream.next()
        else:
            combinator = ' '
        consumed = len(stream.used)
        next_selector = parse_simple_selector(stream)
        if consumed == len(stream.used):
            raise SelectorSyntaxError(
                "Expected selector, got '%s'" % stream.peek())
        result = CombinedSelector(result, combinator, next_selector)
    return result

def parse_simple_selector(stream):
    peek = stream.peek()
    if peek != '*' and not isinstance(peek, Symbol):
        element = namespace = '*'
    else:
        next = stream.next()
        if next != '*' and not isinstance(next, Symbol):
            raise SelectorSyntaxError(
                "Expected symbol, got '%s'" % next)
        if stream.peek() == '|':
            namespace = next
            stream.next()
            element = stream.next()
            if element != '*' and not isinstance(next, Symbol):
                raise SelectorSyntaxError(
                    "Expected symbol, got '%s'" % next)
        else:
            namespace = '*'
            element = next
    result = Element(namespace, element)
    has_hash = False
    while 1:
        peek = stream.peek()
        if peek == '#':
            if has_hash:
                # You can't have two hashes
                # (FIXME: is there some more general rule I'm missing?)
                break
            stream.next()
            result = Hash(result, stream.next())
            has_hash = True
            continue
        elif peek == '.':
            stream.next()
            result = Class(result, stream.next())
            continue
        elif peek == '[':
            stream.next()
            result = parse_attrib(result, stream)
            next = stream.next()
            if not next == ']':
                raise SelectorSyntaxError(
                    "] expected, got '%s'" % next)
            continue
        elif peek == ':' or peek == '::':
            type = stream.next()
            ident = stream.next()
            if not isinstance(ident, Symbol):
                raise SelectorSyntaxError(
                    "Expected symbol, got '%s'" % ident)
            if stream.peek() == '(':
                stream.next()
                peek = stream.peek()
                if isinstance(peek, String):
                    selector = stream.next()
                elif isinstance(peek, Symbol) and is_int(peek):
                    selector = int(stream.next())
                else:
                    # FIXME: parse_simple_selector, or selector, or...?
                    selector = parse_simple_selector(stream)
                next = stream.next()
                if not next == ')':
                    raise SelectorSyntaxError(
                        "Expected ')', got '%s' and '%s'"
                        % (next, selector))
                result = Function(result, type, ident, selector)
            else:
                result = Pseudo(result, type, ident)
            continue
        else:
            if peek == ' ':
                stream.next()
            break
        # FIXME: not sure what "negation" is
    return result

def is_int(v):
    try:
        int(v)
    except ValueError:
        return False
    else:
        return True

def parse_attrib(selector, stream):
    attrib = stream.next()
    if stream.peek() == '|':
        namespace = attrib
        stream.next()
        attrib = stream.next()
    else:
        namespace = '*'
    if stream.peek() == ']':
        return Attrib(selector, namespace, attrib, 'exists', None)
    op = stream.next()
    if not op in ('^=', '$=', '*=', '=', '~=', '|=', '!='):
        raise SelectorSyntaxError(
            "Operator expected, got '%s'" % op)
    value = stream.next()
    if not isinstance(value, (Symbol, String)):
        raise SelectorSyntaxError(
            "Expected string or symbol, got '%s'" % value)
    return Attrib(selector, namespace, attrib, op, value)

def parse_series(s):
    """
    Parses things like '1n+2', or 'an+b' generally, returning (a, b)
    """
    if isinstance(s, Element):
        s = s._format_element()
    if not s or s == '*':
        # Happens when there's nothing, which the CSS parser thinks of as *
        return (0, 0)
    if isinstance(s, int):
        # Happens when you just get a number
        return (0, s)
    if s == 'odd':
        return (2, 1)
    elif s == 'even':
        return (2, 0)
    elif s == 'n':
        return (1, 0)
    if 'n' not in s:
        # Just a b
        return (0, int(s))
    a, b = s.split('n', 1)
    if not a:
        a = 1
    elif a == '-' or a == '+':
        a = int(a+'1')
    else:
        a = int(a)
    if not b:
        b = 0
    elif b == '-' or b == '+':
        b = int(b+'1')
    else:
        b = int(b)
    return (a, b)


############################################################
## Tokenizing
############################################################

_match_whitespace = re.compile(r'\s+', re.UNICODE).match

_replace_comments = re.compile(r'/\*.*?\*/', re.DOTALL).sub

_match_count_number = re.compile(r'[+-]?\d*n(?:[+-]\d+)?').match

def tokenize(s):
    pos = 0
    s = _replace_comments('', s)
    while 1:
        match = _match_whitespace(s, pos=pos)
        if match:
            preceding_whitespace_pos = pos
            pos = match.end()
        else:
            preceding_whitespace_pos = 0
        if pos >= len(s):
            return
        match = _match_count_number(s, pos=pos)
        if match and match.group() != 'n':
            sym = s[pos:match.end()]
            yield Symbol(sym, pos)
            pos = match.end()
            continue
        c = s[pos]
        c2 = s[pos:pos+2]
        if c2 in ('~=', '|=', '^=', '$=', '*=', '::', '!='):
            yield Token(c2, pos)
            pos += 2
            continue
        if c in '>+~,.*=[]()|:#':
            if c in '.#[' and preceding_whitespace_pos > 0:
                yield Token(' ', preceding_whitespace_pos)
            yield Token(c, pos)
            pos += 1
            continue
        if c == '"' or c == "'":
            # Quoted string
            old_pos = pos
            sym, pos = tokenize_escaped_string(s, pos)
            yield String(sym, old_pos)
            continue
        old_pos = pos
        sym, pos = tokenize_symbol(s, pos)
        yield Symbol(sym, old_pos)
        continue

split_at_string_escapes = re.compile(r'(\\(?:%s))'
                                     % '|'.join(['[A-Fa-f0-9]{1,6}(?:\r\n|\s)?',
                                                 '[^A-Fa-f0-9]'])).split

def unescape_string_literal(literal):
    substrings = []
    for substring in split_at_string_escapes(literal):
        if not substring:
            continue
        elif '\\' in substring:
            if substring[0] == '\\' and len(substring) > 1:
                substring = substring[1:]
                if substring[0] in '0123456789ABCDEFabcdef':
                    # int() correctly ignores the potentially trailing whitespace
                    substring = _unichr(int(substring, 16))
            else:
                raise SelectorSyntaxError(
                    "Invalid escape sequence %r in string %r"
                    % (substring.split('\\')[1], literal))
        substrings.append(substring)
    return ''.join(substrings)

def tokenize_escaped_string(s, pos):
    quote = s[pos]
    assert quote in ('"', "'")
    pos = pos+1
    start = pos
    while 1:
        next = s.find(quote, pos)
        if next == -1:
            raise SelectorSyntaxError(
                "Expected closing %s for string in: %r"
                % (quote, s[start:]))
        result = s[start:next]
        if result.endswith('\\'):
            # next quote character is escaped
            pos = next+1
            continue
        if '\\' in result:
            result = unescape_string_literal(result)
        return result, next+1

_illegal_symbol = re.compile(r'[^\w\\-]', re.UNICODE)

def tokenize_symbol(s, pos):
    start = pos
    match = _illegal_symbol.search(s, pos=pos)
    if not match:
        # Goes to end of s
        return s[start:], len(s)
    if match.start() == pos:
        assert 0, (
            "Unexpected symbol: %r at %s" % (s[pos], pos))
    if not match:
        result = s[start:]
        pos = len(s)
    else:
        result = s[start:match.start()]
        pos = match.start()
    try:
        result = result.encode('ASCII', 'backslashreplace').decode('unicode_escape')
    except UnicodeDecodeError:
        import sys
        e = sys.exc_info()[1]
        raise SelectorSyntaxError(
            "Bad symbol %r: %s" % (result, e))
    return result, pos

class TokenStream(object):

    def __init__(self, tokens, source=None):
        self.used = []
        self.tokens = iter(tokens)
        self.source = source
        self.peeked = None
        self._peeking = False
        try:
            self.next_token = self.tokens.next
        except AttributeError:
            # Python 3
            self.next_token = self.tokens.__next__

    def next(self):
        if self._peeking:
            self._peeking = False
            self.used.append(self.peeked)
            return self.peeked
        else:
            try:
                next = self.next_token()
                self.used.append(next)
                return next
            except StopIteration:
                return None

    def __iter__(self):
        return iter(self.next, None)

    def peek(self):
        if not self._peeking:
            try:
                self.peeked = self.next_token()
            except StopIteration:
                return None
            self._peeking = True
        return self.peeked
