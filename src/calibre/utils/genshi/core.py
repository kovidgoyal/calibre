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

"""Core classes for markup processing."""

from itertools import chain
import operator

from calibre.utils.genshi.util import plaintext, stripentities, striptags

__all__ = ['Stream', 'Markup', 'escape', 'unescape', 'Attrs', 'Namespace',
           'QName']
__docformat__ = 'restructuredtext en'


class StreamEventKind(str):
    """A kind of event on a markup stream."""
    __slots__ = []
    _instances = {}

    def __new__(cls, val):
        return cls._instances.setdefault(val, str.__new__(cls, val))


class Stream(object):
    """Represents a stream of markup events.
    
    This class is basically an iterator over the events.
    
    Stream events are tuples of the form::
    
      (kind, data, position)
    
    where ``kind`` is the event kind (such as `START`, `END`, `TEXT`, etc),
    ``data`` depends on the kind of event, and ``position`` is a
    ``(filename, line, offset)`` tuple that contains the location of the
    original element or text in the input. If the original location is unknown,
    ``position`` is ``(None, -1, -1)``.
    
    Also provided are ways to serialize the stream to text. The `serialize()`
    method will return an iterator over generated strings, while `render()`
    returns the complete generated text at once. Both accept various parameters
    that impact the way the stream is serialized.
    """
    __slots__ = ['events', 'serializer']

    START = StreamEventKind('START') #: a start tag
    END = StreamEventKind('END') #: an end tag
    TEXT = StreamEventKind('TEXT') #: literal text
    XML_DECL = StreamEventKind('XML_DECL') #: XML declaration
    DOCTYPE = StreamEventKind('DOCTYPE') #: doctype declaration
    START_NS = StreamEventKind('START_NS') #: start namespace mapping
    END_NS = StreamEventKind('END_NS') #: end namespace mapping
    START_CDATA = StreamEventKind('START_CDATA') #: start CDATA section
    END_CDATA = StreamEventKind('END_CDATA') #: end CDATA section
    PI = StreamEventKind('PI') #: processing instruction
    COMMENT = StreamEventKind('COMMENT') #: comment

    def __init__(self, events, serializer=None):
        """Initialize the stream with a sequence of markup events.
        
        :param events: a sequence or iterable providing the events
        :param serializer: the default serialization method to use for this
                           stream

        :note: Changed in 0.5: added the `serializer` argument
        """
        self.events = events #: The underlying iterable producing the events
        self.serializer = serializer #: The default serializion method

    def __iter__(self):
        return iter(self.events)

    def __or__(self, function):
        """Override the "bitwise or" operator to apply filters or serializers
        to the stream, providing a syntax similar to pipes on Unix shells.
        
        Assume the following stream produced by the `HTML` function:
        
        >>> from genshi.input import HTML
        >>> html = HTML('''<p onclick="alert('Whoa')">Hello, world!</p>''')
        >>> print html
        <p onclick="alert('Whoa')">Hello, world!</p>
        
        A filter such as the HTML sanitizer can be applied to that stream using
        the pipe notation as follows:
        
        >>> from genshi.filters import HTMLSanitizer
        >>> sanitizer = HTMLSanitizer()
        >>> print html | sanitizer
        <p>Hello, world!</p>
        
        Filters can be any function that accepts and produces a stream (where
        a stream is anything that iterates over events):
        
        >>> def uppercase(stream):
        ...     for kind, data, pos in stream:
        ...         if kind is TEXT:
        ...             data = data.upper()
        ...         yield kind, data, pos
        >>> print html | sanitizer | uppercase
        <p>HELLO, WORLD!</p>
        
        Serializers can also be used with this notation:
        
        >>> from genshi.output import TextSerializer
        >>> output = TextSerializer()
        >>> print html | sanitizer | uppercase | output
        HELLO, WORLD!
        
        Commonly, serializers should be used at the end of the "pipeline";
        using them somewhere in the middle may produce unexpected results.
        
        :param function: the callable object that should be applied as a filter
        :return: the filtered stream
        :rtype: `Stream`
        """
        return Stream(_ensure(function(self)), serializer=self.serializer)

    def filter(self, *filters):
        """Apply filters to the stream.
        
        This method returns a new stream with the given filters applied. The
        filters must be callables that accept the stream object as parameter,
        and return the filtered stream.
        
        The call::
        
            stream.filter(filter1, filter2)
        
        is equivalent to::
        
            stream | filter1 | filter2
        
        :param filters: one or more callable objects that should be applied as
                        filters
        :return: the filtered stream
        :rtype: `Stream`
        """
        return reduce(operator.or_, (self,) + filters)

    def render(self, method=None, encoding='utf-8', out=None, **kwargs):
        """Return a string representation of the stream.
        
        Any additional keyword arguments are passed to the serializer, and thus
        depend on the `method` parameter value.
        
        :param method: determines how the stream is serialized; can be either
                       "xml", "xhtml", "html", "text", or a custom serializer
                       class; if `None`, the default serialization method of
                       the stream is used
        :param encoding: how the output string should be encoded; if set to
                         `None`, this method returns a `unicode` object
        :param out: a file-like object that the output should be written to
                    instead of being returned as one big string; note that if
                    this is a file or socket (or similar), the `encoding` must
                    not be `None` (that is, the output must be encoded)
        :return: a `str` or `unicode` object (depending on the `encoding`
                 parameter), or `None` if the `out` parameter is provided
        :rtype: `basestring`
        
        :see: XMLSerializer, XHTMLSerializer, HTMLSerializer, TextSerializer
        :note: Changed in 0.5: added the `out` parameter
        """
        from calibre.utils.genshi.output import encode
        if method is None:
            method = self.serializer or 'xml'
        generator = self.serialize(method=method, **kwargs)
        return encode(generator, method=method, encoding=encoding, out=out)

    def select(self, path, namespaces=None, variables=None):
        """Return a new stream that contains the events matching the given
        XPath expression.
        
        >>> from genshi import HTML
        >>> stream = HTML('<doc><elem>foo</elem><elem>bar</elem></doc>')
        >>> print stream.select('elem')
        <elem>foo</elem><elem>bar</elem>
        >>> print stream.select('elem/text()')
        foobar
        
        Note that the outermost element of the stream becomes the *context
        node* for the XPath test. That means that the expression "doc" would
        not match anything in the example above, because it only tests against
        child elements of the outermost element:
        
        >>> print stream.select('doc')
        <BLANKLINE>
        
        You can use the "." expression to match the context node itself
        (although that usually makes little sense):
        
        >>> print stream.select('.')
        <doc><elem>foo</elem><elem>bar</elem></doc>
        
        :param path: a string containing the XPath expression
        :param namespaces: mapping of namespace prefixes used in the path
        :param variables: mapping of variable names to values
        :return: the selected substream
        :rtype: `Stream`
        :raises PathSyntaxError: if the given path expression is invalid or not
                                 supported
        """
        from genshi.path import Path
        return Path(path).select(self, namespaces, variables)

    def serialize(self, method='xml', **kwargs):
        """Generate strings corresponding to a specific serialization of the
        stream.
        
        Unlike the `render()` method, this method is a generator that returns
        the serialized output incrementally, as opposed to returning a single
        string.
        
        Any additional keyword arguments are passed to the serializer, and thus
        depend on the `method` parameter value.
        
        :param method: determines how the stream is serialized; can be either
                       "xml", "xhtml", "html", "text", or a custom serializer
                       class; if `None`, the default serialization method of
                       the stream is used
        :return: an iterator over the serialization results (`Markup` or
                 `unicode` objects, depending on the serialization method)
        :rtype: ``iterator``
        :see: XMLSerializer, XHTMLSerializer, HTMLSerializer, TextSerializer
        """
        from calibre.utils.genshi.output import get_serializer
        if method is None:
            method = self.serializer or 'xml'
        return get_serializer(method, **kwargs)(_ensure(self))

    def __str__(self):
        return self.render()

    def __unicode__(self):
        return self.render(encoding=None)

    def __html__(self):
        return self


START = Stream.START
END = Stream.END
TEXT = Stream.TEXT
XML_DECL = Stream.XML_DECL
DOCTYPE = Stream.DOCTYPE
START_NS = Stream.START_NS
END_NS = Stream.END_NS
START_CDATA = Stream.START_CDATA
END_CDATA = Stream.END_CDATA
PI = Stream.PI
COMMENT = Stream.COMMENT

def _ensure(stream):
    """Ensure that every item on the stream is actually a markup event."""
    stream = iter(stream)
    event = stream.next()

    # Check whether the iterable is a real markup event stream by examining the
    # first item it yields; if it's not we'll need to do some conversion
    if type(event) is not tuple or len(event) != 3:
        for event in chain([event], stream):
            if hasattr(event, 'totuple'):
                event = event.totuple()
            else:
                event = TEXT, unicode(event), (None, -1, -1)
            yield event
        return

    # This looks like a markup event stream, so we'll just pass it through
    # unchanged
    yield event
    for event in stream:
        yield event


class Attrs(tuple):
    """Immutable sequence type that stores the attributes of an element.
    
    Ordering of the attributes is preserved, while access by name is also
    supported.
    
    >>> attrs = Attrs([('href', '#'), ('title', 'Foo')])
    >>> attrs
    Attrs([('href', '#'), ('title', 'Foo')])
    
    >>> 'href' in attrs
    True
    >>> 'tabindex' in attrs
    False
    >>> attrs.get('title')
    'Foo'
    
    Instances may not be manipulated directly. Instead, the operators ``|`` and
    ``-`` can be used to produce new instances that have specific attributes
    added, replaced or removed.
    
    To remove an attribute, use the ``-`` operator. The right hand side can be
    either a string or a set/sequence of strings, identifying the name(s) of
    the attribute(s) to remove:
    
    >>> attrs - 'title'
    Attrs([('href', '#')])
    >>> attrs - ('title', 'href')
    Attrs()
    
    The original instance is not modified, but the operator can of course be
    used with an assignment:

    >>> attrs
    Attrs([('href', '#'), ('title', 'Foo')])
    >>> attrs -= 'title'
    >>> attrs
    Attrs([('href', '#')])
    
    To add a new attribute, use the ``|`` operator, where the right hand value
    is a sequence of ``(name, value)`` tuples (which includes `Attrs`
    instances):
    
    >>> attrs | [('title', 'Bar')]
    Attrs([('href', '#'), ('title', 'Bar')])
    
    If the attributes already contain an attribute with a given name, the value
    of that attribute is replaced:
    
    >>> attrs | [('href', 'http://example.org/')]
    Attrs([('href', 'http://example.org/')])
    """
    __slots__ = []

    def __contains__(self, name):
        """Return whether the list includes an attribute with the specified
        name.
        
        :return: `True` if the list includes the attribute
        :rtype: `bool`
        """
        for attr, _ in self:
            if attr == name:
                return True

    def __getslice__(self, i, j):
        """Return a slice of the attributes list.
        
        >>> attrs = Attrs([('href', '#'), ('title', 'Foo')])
        >>> attrs[1:]
        Attrs([('title', 'Foo')])
        """
        return Attrs(tuple.__getslice__(self, i, j))

    def __or__(self, attrs):
        """Return a new instance that contains the attributes in `attrs` in
        addition to any already existing attributes.
        
        :return: a new instance with the merged attributes
        :rtype: `Attrs`
        """
        repl = dict([(an, av) for an, av in attrs if an in self])
        return Attrs([(sn, repl.get(sn, sv)) for sn, sv in self] +
                     [(an, av) for an, av in attrs if an not in self])

    def __repr__(self):
        if not self:
            return 'Attrs()'
        return 'Attrs([%s])' % ', '.join([repr(item) for item in self])

    def __sub__(self, names):
        """Return a new instance with all attributes with a name in `names` are
        removed.
        
        :param names: the names of the attributes to remove
        :return: a new instance with the attribute removed
        :rtype: `Attrs`
        """
        if isinstance(names, basestring):
            names = (names,)
        return Attrs([(name, val) for name, val in self if name not in names])

    def get(self, name, default=None):
        """Return the value of the attribute with the specified name, or the
        value of the `default` parameter if no such attribute is found.
        
        :param name: the name of the attribute
        :param default: the value to return when the attribute does not exist
        :return: the attribute value, or the `default` value if that attribute
                 does not exist
        :rtype: `object`
        """
        for attr, value in self:
            if attr == name:
                return value
        return default

    def totuple(self):
        """Return the attributes as a markup event.
        
        The returned event is a `TEXT` event, the data is the value of all
        attributes joined together.
        
        >>> Attrs([('href', '#'), ('title', 'Foo')]).totuple()
        ('TEXT', u'#Foo', (None, -1, -1))
        
        :return: a `TEXT` event
        :rtype: `tuple`
        """
        return TEXT, u''.join([x[1] for x in self]), (None, -1, -1)


class Markup(unicode):
    """Marks a string as being safe for inclusion in HTML/XML output without
    needing to be escaped.
    """
    __slots__ = []

    def __add__(self, other):
        return Markup(unicode(self) + unicode(escape(other)))

    def __radd__(self, other):
        return Markup(unicode(escape(other)) + unicode(self))

    def __mod__(self, args):
        if isinstance(args, dict):
            args = dict(zip(args.keys(), map(escape, args.values())))
        elif isinstance(args, (list, tuple)):
            args = tuple(map(escape, args))
        else:
            args = escape(args)
        return Markup(unicode.__mod__(self, args))

    def __mul__(self, num):
        return Markup(unicode(self) * num)

    def __rmul__(self, num):
        return Markup(num * unicode(self))

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, unicode(self))

    def join(self, seq, escape_quotes=True):
        """Return a `Markup` object which is the concatenation of the strings
        in the given sequence, where this `Markup` object is the separator
        between the joined elements.
        
        Any element in the sequence that is not a `Markup` instance is
        automatically escaped.
        
        :param seq: the sequence of strings to join
        :param escape_quotes: whether double quote characters in the elements
                              should be escaped
        :return: the joined `Markup` object
        :rtype: `Markup`
        :see: `escape`
        """
        return Markup(unicode(self).join([escape(item, quotes=escape_quotes)
                                          for item in seq]))

    def escape(cls, text, quotes=True):
        """Create a Markup instance from a string and escape special characters
        it may contain (<, >, & and \").
        
        >>> escape('"1 < 2"')
        <Markup u'&#34;1 &lt; 2&#34;'>
        
        If the `quotes` parameter is set to `False`, the \" character is left
        as is. Escaping quotes is generally only required for strings that are
        to be used in attribute values.
        
        >>> escape('"1 < 2"', quotes=False)
        <Markup u'"1 &lt; 2"'>
        
        :param text: the text to escape
        :param quotes: if ``True``, double quote characters are escaped in
                       addition to the other special characters
        :return: the escaped `Markup` string
        :rtype: `Markup`
        """
        if not text:
            return cls()
        if type(text) is cls:
            return text
        if hasattr(text, '__html__'):
            return Markup(text.__html__())

        if isinstance(text, str):
            text = text.decode('utf-8', 'replace')
        text = text.replace('&', '&amp;') \
                            .replace('<', '&lt;') \
                            .replace('>', '&gt;')
        if quotes:
            text = text.replace('"', '&#34;')
        return cls(text)
    escape = classmethod(escape)

    def unescape(self):
        """Reverse-escapes &, <, >, and \" and returns a `unicode` object.
        
        >>> Markup('1 &lt; 2').unescape()
        u'1 < 2'
        
        :return: the unescaped string
        :rtype: `unicode`
        :see: `genshi.core.unescape`
        """
        if not self:
            return u''
        return unicode(self).replace('&#34;', '"') \
                            .replace('&gt;', '>') \
                            .replace('&lt;', '<') \
                            .replace('&amp;', '&')

    def stripentities(self, keepxmlentities=False):
        """Return a copy of the text with any character or numeric entities
        replaced by the equivalent UTF-8 characters.
        
        If the `keepxmlentities` parameter is provided and evaluates to `True`,
        the core XML entities (``&amp;``, ``&apos;``, ``&gt;``, ``&lt;`` and
        ``&quot;``) are not stripped.
        
        :return: a `Markup` instance with entities removed
        :rtype: `Markup`
        :see: `genshi.util.stripentities`
        """
        return Markup(stripentities(self, keepxmlentities=keepxmlentities))

    def striptags(self):
        """Return a copy of the text with all XML/HTML tags removed.
        
        :return: a `Markup` instance with all tags removed
        :rtype: `Markup`
        :see: `genshi.util.striptags`
        """
        return Markup(striptags(self))


try:
    from calibre.utils.genshi._speedups import Markup
except ImportError:
    pass # just use the Python implementation

escape = Markup.escape

def unescape(text):
    """Reverse-escapes &, <, >, and \" and returns a `unicode` object.
    
    >>> unescape(Markup('1 &lt; 2'))
    u'1 < 2'
    
    If the provided `text` object is not a `Markup` instance, it is returned
    unchanged.
    
    >>> unescape('1 &lt; 2')
    '1 &lt; 2'
    
    :param text: the text to unescape
    :return: the unescsaped string
    :rtype: `unicode`
    """
    if not isinstance(text, Markup):
        return text
    return text.unescape()


class Namespace(object):
    """Utility class creating and testing elements with a namespace.
    
    Internally, namespace URIs are encoded in the `QName` of any element or
    attribute, the namespace URI being enclosed in curly braces. This class
    helps create and test these strings.
    
    A `Namespace` object is instantiated with the namespace URI.
    
    >>> html = Namespace('http://www.w3.org/1999/xhtml')
    >>> html
    <Namespace "http://www.w3.org/1999/xhtml">
    >>> html.uri
    u'http://www.w3.org/1999/xhtml'
    
    The `Namespace` object can than be used to generate `QName` objects with
    that namespace:
    
    >>> html.body
    QName(u'http://www.w3.org/1999/xhtml}body')
    >>> html.body.localname
    u'body'
    >>> html.body.namespace
    u'http://www.w3.org/1999/xhtml'
    
    The same works using item access notation, which is useful for element or
    attribute names that are not valid Python identifiers:
    
    >>> html['body']
    QName(u'http://www.w3.org/1999/xhtml}body')
    
    A `Namespace` object can also be used to test whether a specific `QName`
    belongs to that namespace using the ``in`` operator:
    
    >>> qname = html.body
    >>> qname in html
    True
    >>> qname in Namespace('http://www.w3.org/2002/06/xhtml2')
    False
    """
    def __new__(cls, uri):
        if type(uri) is cls:
            return uri
        return object.__new__(cls)

    def __getnewargs__(self):
        return (self.uri,)

    def __getstate__(self):
        return self.uri

    def __setstate__(self, uri):
        self.uri = uri

    def __init__(self, uri):
        self.uri = unicode(uri)

    def __contains__(self, qname):
        return qname.namespace == self.uri

    def __ne__(self, other):
        return not self == other

    def __eq__(self, other):
        if isinstance(other, Namespace):
            return self.uri == other.uri
        return self.uri == other

    def __getitem__(self, name):
        return QName(self.uri + u'}' + name)
    __getattr__ = __getitem__

    def __repr__(self):
        return '<Namespace "%s">' % self.uri

    def __str__(self):
        return self.uri.encode('utf-8')

    def __unicode__(self):
        return self.uri


# The namespace used by attributes such as xml:lang and xml:space
XML_NAMESPACE = Namespace('http://www.w3.org/XML/1998/namespace')


class QName(unicode):
    """A qualified element or attribute name.
    
    The unicode value of instances of this class contains the qualified name of
    the element or attribute, in the form ``{namespace-uri}local-name``. The
    namespace URI can be obtained through the additional `namespace` attribute,
    while the local name can be accessed through the `localname` attribute.
    
    >>> qname = QName('foo')
    >>> qname
    QName(u'foo')
    >>> qname.localname
    u'foo'
    >>> qname.namespace
    
    >>> qname = QName('http://www.w3.org/1999/xhtml}body')
    >>> qname
    QName(u'http://www.w3.org/1999/xhtml}body')
    >>> qname.localname
    u'body'
    >>> qname.namespace
    u'http://www.w3.org/1999/xhtml'
    """
    __slots__ = ['namespace', 'localname']

    def __new__(cls, qname):
        """Create the `QName` instance.
        
        :param qname: the qualified name as a string of the form
                      ``{namespace-uri}local-name``, where the leading curly
                      brace is optional
        """
        if type(qname) is cls:
            return qname

        parts = qname.lstrip(u'{').split(u'}', 1)
        if len(parts) > 1:
            self = unicode.__new__(cls, u'{%s' % qname)
            self.namespace, self.localname = map(unicode, parts)
        else:
            self = unicode.__new__(cls, qname)
            self.namespace, self.localname = None, unicode(qname)
        return self

    def __getnewargs__(self):
        return (self.lstrip('{'),)

    def __repr__(self):
        return 'QName(%s)' % unicode.__repr__(self.lstrip('{'))
