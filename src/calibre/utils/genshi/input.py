# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Support for constructing markup streams from files, strings, or other
sources.
"""

from itertools import chain
from xml.parsers import expat
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
import HTMLParser as html
import htmlentitydefs
from StringIO import StringIO

from calibre.utils.genshi.core import Attrs, QName, Stream, stripentities
from calibre.utils.genshi.core import START, END, XML_DECL, DOCTYPE, TEXT, START_NS, END_NS, \
                        START_CDATA, END_CDATA, PI, COMMENT

__all__ = ['ET', 'ParseError', 'XMLParser', 'XML', 'HTMLParser', 'HTML']
__docformat__ = 'restructuredtext en'

def ET(element):
    """Convert a given ElementTree element to a markup stream.
    
    :param element: an ElementTree element
    :return: a markup stream
    """
    tag_name = QName(element.tag.lstrip('{'))
    attrs = Attrs([(QName(attr.lstrip('{')), value)
                   for attr, value in element.items()])

    yield START, (tag_name, attrs), (None, -1, -1)
    if element.text:
        yield TEXT, element.text, (None, -1, -1)
    for child in element.getchildren():
        for item in ET(child):
            yield item
    yield END, tag_name, (None, -1, -1)
    if element.tail:
        yield TEXT, element.tail, (None, -1, -1)


class ParseError(Exception):
    """Exception raised when fatal syntax errors are found in the input being
    parsed.
    """

    def __init__(self, message, filename=None, lineno=-1, offset=-1):
        """Exception initializer.
        
        :param message: the error message from the parser
        :param filename: the path to the file that was parsed
        :param lineno: the number of the line on which the error was encountered
        :param offset: the column number where the error was encountered
        """
        self.msg = message
        if filename:
            message += ', in ' + filename
        Exception.__init__(self, message)
        self.filename = filename or '<string>'
        self.lineno = lineno
        self.offset = offset


class XMLParser(object):
    """Generator-based XML parser based on roughly equivalent code in
    Kid/ElementTree.
    
    The parsing is initiated by iterating over the parser object:
    
    >>> parser = XMLParser(StringIO('<root id="2"><child>Foo</child></root>'))
    >>> for kind, data, pos in parser:
    ...     print kind, data
    START (QName(u'root'), Attrs([(QName(u'id'), u'2')]))
    START (QName(u'child'), Attrs())
    TEXT Foo
    END child
    END root
    """

    _entitydefs = ['<!ENTITY %s "&#%d;">' % (name, value) for name, value in
                   htmlentitydefs.name2codepoint.items()]
    _external_dtd = '\n'.join(_entitydefs)

    def __init__(self, source, filename=None, encoding=None):
        """Initialize the parser for the given XML input.
        
        :param source: the XML text as a file-like object
        :param filename: the name of the file, if appropriate
        :param encoding: the encoding of the file; if not specified, the
                         encoding is assumed to be ASCII, UTF-8, or UTF-16, or
                         whatever the encoding specified in the XML declaration
                         (if any)
        """
        self.source = source
        self.filename = filename

        # Setup the Expat parser
        parser = expat.ParserCreate(encoding, '}')
        parser.buffer_text = True
        parser.returns_unicode = True
        parser.ordered_attributes = True

        parser.StartElementHandler = self._handle_start
        parser.EndElementHandler = self._handle_end
        parser.CharacterDataHandler = self._handle_data
        parser.StartDoctypeDeclHandler = self._handle_doctype
        parser.StartNamespaceDeclHandler = self._handle_start_ns
        parser.EndNamespaceDeclHandler = self._handle_end_ns
        parser.StartCdataSectionHandler = self._handle_start_cdata
        parser.EndCdataSectionHandler = self._handle_end_cdata
        parser.ProcessingInstructionHandler = self._handle_pi
        parser.XmlDeclHandler = self._handle_xml_decl
        parser.CommentHandler = self._handle_comment

        # Tell Expat that we'll handle non-XML entities ourselves
        # (in _handle_other)
        parser.DefaultHandler = self._handle_other
        parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_ALWAYS)
        parser.UseForeignDTD()
        parser.ExternalEntityRefHandler = self._build_foreign

        # Location reporting is only support in Python >= 2.4
        if not hasattr(parser, 'CurrentLineNumber'):
            self._getpos = self._getpos_unknown

        self.expat = parser
        self._queue = []

    def parse(self):
        """Generator that parses the XML source, yielding markup events.
        
        :return: a markup event stream
        :raises ParseError: if the XML text is not well formed
        """
        def _generate():
            try:
                bufsize = 4 * 1024 # 4K
                done = False
                while 1:
                    while not done and len(self._queue) == 0:
                        data = self.source.read(bufsize)
                        if data == '': # end of data
                            if hasattr(self, 'expat'):
                                self.expat.Parse('', True)
                                del self.expat # get rid of circular references
                            done = True
                        else:
                            if isinstance(data, unicode):
                                data = data.encode('utf-8')
                            self.expat.Parse(data, False)
                    for event in self._queue:
                        yield event
                    self._queue = []
                    if done:
                        break
            except expat.ExpatError, e:
                msg = str(e)
                raise ParseError(msg, self.filename, e.lineno, e.offset)
        return Stream(_generate()).filter(_coalesce)

    def __iter__(self):
        return iter(self.parse())

    def _build_foreign(self, context, base, sysid, pubid):
        parser = self.expat.ExternalEntityParserCreate(context)
        parser.ParseFile(StringIO(self._external_dtd))
        return 1

    def _enqueue(self, kind, data=None, pos=None):
        if pos is None:
            pos = self._getpos()
        if kind is TEXT:
            # Expat reports the *end* of the text event as current position. We
            # try to fix that up here as much as possible. Unfortunately, the
            # offset is only valid for single-line text. For multi-line text,
            # it is apparently not possible to determine at what offset it
            # started
            if '\n' in data:
                lines = data.splitlines()
                lineno = pos[1] - len(lines) + 1
                offset = -1
            else:
                lineno = pos[1]
                offset = pos[2] - len(data)
            pos = (pos[0], lineno, offset)
        self._queue.append((kind, data, pos))

    def _getpos_unknown(self):
        return (self.filename, -1, -1)

    def _getpos(self):
        return (self.filename, self.expat.CurrentLineNumber,
                self.expat.CurrentColumnNumber)

    def _handle_start(self, tag, attrib):
        attrs = Attrs([(QName(name), value) for name, value in
                       zip(*[iter(attrib)] * 2)])
        self._enqueue(START, (QName(tag), attrs))

    def _handle_end(self, tag):
        self._enqueue(END, QName(tag))

    def _handle_data(self, text):
        self._enqueue(TEXT, text)

    def _handle_xml_decl(self, version, encoding, standalone):
        self._enqueue(XML_DECL, (version, encoding, standalone))

    def _handle_doctype(self, name, sysid, pubid, has_internal_subset):
        self._enqueue(DOCTYPE, (name, pubid, sysid))

    def _handle_start_ns(self, prefix, uri):
        self._enqueue(START_NS, (prefix or '', uri))

    def _handle_end_ns(self, prefix):
        self._enqueue(END_NS, prefix or '')

    def _handle_start_cdata(self):
        self._enqueue(START_CDATA)

    def _handle_end_cdata(self):
        self._enqueue(END_CDATA)

    def _handle_pi(self, target, data):
        self._enqueue(PI, (target, data))

    def _handle_comment(self, text):
        self._enqueue(COMMENT, text)

    def _handle_other(self, text):
        if text.startswith('&'):
            # deal with undefined entities
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
                self._enqueue(TEXT, text)
            except KeyError:
                filename, lineno, offset = self._getpos()
                error = expat.error('undefined entity "%s": line %d, column %d'
                                    % (text, lineno, offset))
                error.code = expat.errors.XML_ERROR_UNDEFINED_ENTITY
                error.lineno = lineno
                error.offset = offset
                raise error


def XML(text):
    """Parse the given XML source and return a markup stream.
    
    Unlike with `XMLParser`, the returned stream is reusable, meaning it can be
    iterated over multiple times:
    
    >>> xml = XML('<doc><elem>Foo</elem><elem>Bar</elem></doc>')
    >>> print xml
    <doc><elem>Foo</elem><elem>Bar</elem></doc>
    >>> print xml.select('elem')
    <elem>Foo</elem><elem>Bar</elem>
    >>> print xml.select('elem/text()')
    FooBar
    
    :param text: the XML source
    :return: the parsed XML event stream
    :raises ParseError: if the XML text is not well-formed
    """
    return Stream(list(XMLParser(StringIO(text))))


class HTMLParser(html.HTMLParser, object):
    """Parser for HTML input based on the Python `HTMLParser` module.
    
    This class provides the same interface for generating stream events as
    `XMLParser`, and attempts to automatically balance tags.
    
    The parsing is initiated by iterating over the parser object:
    
    >>> parser = HTMLParser(StringIO('<UL compact><LI>Foo</UL>'))
    >>> for kind, data, pos in parser:
    ...     print kind, data
    START (QName(u'ul'), Attrs([(QName(u'compact'), u'compact')]))
    START (QName(u'li'), Attrs())
    TEXT Foo
    END li
    END ul
    """

    _EMPTY_ELEMS = frozenset(['area', 'base', 'basefont', 'br', 'col', 'frame',
                              'hr', 'img', 'input', 'isindex', 'link', 'meta',
                              'param'])

    def __init__(self, source, filename=None, encoding='utf-8'):
        """Initialize the parser for the given HTML input.
        
        :param source: the HTML text as a file-like object
        :param filename: the name of the file, if known
        :param filename: encoding of the file; ignored if the input is unicode
        """
        html.HTMLParser.__init__(self)
        self.source = source
        self.filename = filename
        self.encoding = encoding
        self._queue = []
        self._open_tags = []

    def parse(self):
        """Generator that parses the HTML source, yielding markup events.
        
        :return: a markup event stream
        :raises ParseError: if the HTML text is not well formed
        """
        def _generate():
            try:
                bufsize = 4 * 1024 # 4K
                done = False
                while 1:
                    while not done and len(self._queue) == 0:
                        data = self.source.read(bufsize)
                        if data == '': # end of data
                            self.close()
                            done = True
                        else:
                            self.feed(data)
                    for kind, data, pos in self._queue:
                        yield kind, data, pos
                    self._queue = []
                    if done:
                        open_tags = self._open_tags
                        open_tags.reverse()
                        for tag in open_tags:
                            yield END, QName(tag), pos
                        break
            except html.HTMLParseError, e:
                msg = '%s: line %d, column %d' % (e.msg, e.lineno, e.offset)
                raise ParseError(msg, self.filename, e.lineno, e.offset)
        return Stream(_generate()).filter(_coalesce)

    def __iter__(self):
        return iter(self.parse())

    def _enqueue(self, kind, data, pos=None):
        if pos is None:
            pos = self._getpos()
        self._queue.append((kind, data, pos))

    def _getpos(self):
        lineno, column = self.getpos()
        return (self.filename, lineno, column)

    def handle_starttag(self, tag, attrib):
        fixed_attrib = []
        for name, value in attrib: # Fixup minimized attributes
            if value is None:
                value = unicode(name)
            elif not isinstance(value, unicode):
                value = value.decode(self.encoding, 'replace')
            fixed_attrib.append((QName(name), stripentities(value)))

        self._enqueue(START, (QName(tag), Attrs(fixed_attrib)))
        if tag in self._EMPTY_ELEMS:
            self._enqueue(END, QName(tag))
        else:
            self._open_tags.append(tag)

    def handle_endtag(self, tag):
        if tag not in self._EMPTY_ELEMS:
            while self._open_tags:
                open_tag = self._open_tags.pop()
                self._enqueue(END, QName(open_tag))
                if open_tag.lower() == tag.lower():
                    break

    def handle_data(self, text):
        if not isinstance(text, unicode):
            text = text.decode(self.encoding, 'replace')
        self._enqueue(TEXT, text)

    def handle_charref(self, name):
        if name.lower().startswith('x'):
            text = unichr(int(name[1:], 16))
        else:
            text = unichr(int(name))
        self._enqueue(TEXT, text)

    def handle_entityref(self, name):
        try:
            text = unichr(htmlentitydefs.name2codepoint[name])
        except KeyError:
            text = '&%s;' % name
        self._enqueue(TEXT, text)

    def handle_pi(self, data):
        target, data = data.split(None, 1)
        if data.endswith('?'):
            data = data[:-1]
        self._enqueue(PI, (target.strip(), data.strip()))

    def handle_comment(self, text):
        self._enqueue(COMMENT, text)


def HTML(text, encoding='utf-8'):
    """Parse the given HTML source and return a markup stream.
    
    Unlike with `HTMLParser`, the returned stream is reusable, meaning it can be
    iterated over multiple times:
    
    >>> html = HTML('<body><h1>Foo</h1></body>')
    >>> print html
    <body><h1>Foo</h1></body>
    >>> print html.select('h1')
    <h1>Foo</h1>
    >>> print html.select('h1/text()')
    Foo
    
    :param text: the HTML source
    :return: the parsed XML event stream
    :raises ParseError: if the HTML text is not well-formed, and error recovery
                        fails
    """
    return Stream(list(HTMLParser(StringIO(text), encoding=encoding)))

def _coalesce(stream):
    """Coalesces adjacent TEXT events into a single event."""
    textbuf = []
    textpos = None
    for kind, data, pos in chain(stream, [(None, None, None)]):
        if kind is TEXT:
            textbuf.append(data)
            if textpos is None:
                textpos = pos
        else:
            if textbuf:
                yield TEXT, u''.join(textbuf), textpos
                del textbuf[:]
                textpos = None
            if kind:
                yield kind, data, pos
