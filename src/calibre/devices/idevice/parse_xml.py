#!/usr/bin/env python
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

"""
https://github.com/ishikawa/python-plist-parser/blob/master/plist_parser.py

A `Property Lists`_ is a data representation used in Apple's Mac OS X as
a convenient way to store standard object types, such as string, number,
boolean, and container object.

This file contains a class ``XmlPropertyListParser`` for parse
a property list file and get back a python native data structure.

    :copyright: 2008 by Takanori Ishikawa <takanori.ishikawa@gmail.com>
    :license: MIT (See LICENSE file for more details)

.. _Property Lists: http://developer.apple.com/documentation/Cocoa/Conceptual/PropertyLists/
"""


class PropertyListParseError(Exception):
    """Raised when parsing a property list is failed."""
    pass


class XmlPropertyListParser(object):
    """
    The ``XmlPropertyListParser`` class provides methods that
    convert `Property Lists`_ objects from xml format.
    Property list objects include ``string``, ``unicode``,
    ``list``, ``dict``, ``datetime``, and ``int`` or ``float``.

        :copyright: 2008 by Takanori Ishikawa <takanori.ishikawa@gmail.com>
        :license: MIT License

    .. _Property List: http://developer.apple.com/documentation/Cocoa/Conceptual/PropertyLists/
    """

    def _assert(self, test, message):
        if not test:
            raise PropertyListParseError(message)

    # ------------------------------------------------
    # SAX2: ContentHandler
    # ------------------------------------------------
    def setDocumentLocator(self, locator):
        pass

    def startPrefixMapping(self, prefix, uri):
        pass

    def endPrefixMapping(self, prefix):
        pass

    def startElementNS(self, name, qname, attrs):
        pass

    def endElementNS(self, name, qname):
        pass

    def ignorableWhitespace(self, whitespace):
        pass

    def processingInstruction(self, target, data):
        pass

    def skippedEntity(self, name):
        pass

    def startDocument(self):
        self.__stack = []
        self.__plist = self.__key = self.__characters = None
        # For reducing runtime type checking,
        # the parser caches top level object type.
        self.__in_dict = False

    def endDocument(self):
        self._assert(self.__plist is not None, "A top level element must be <plist>.")
        self._assert(
            len(self.__stack) is 0,
            "multiple objects at top level.")

    def startElement(self, name, attributes):
        if name in XmlPropertyListParser.START_CALLBACKS:
            XmlPropertyListParser.START_CALLBACKS[name](self, name, attributes)
        if name in XmlPropertyListParser.PARSE_CALLBACKS:
            self.__characters = []

    def endElement(self, name):
        if name in XmlPropertyListParser.END_CALLBACKS:
            XmlPropertyListParser.END_CALLBACKS[name](self, name)
        if name in XmlPropertyListParser.PARSE_CALLBACKS:
            # Creates character string from buffered characters.
            content = ''.join(self.__characters)
            # For compatibility with ``xml.etree`` and ``plistlib``,
            # convert text string to ascii, if possible
            try:
                content = content.encode('ascii')
            except (UnicodeError, AttributeError):
                pass
            XmlPropertyListParser.PARSE_CALLBACKS[name](self, name, content)
            self.__characters = None

    def characters(self, content):
        if self.__characters is not None:
            self.__characters.append(content)

    # ------------------------------------------------
    # XmlPropertyListParser private
    # ------------------------------------------------
    def _push_value(self, value):
        if not self.__stack:
            self._assert(self.__plist is None, "Multiple objects at top level")
            self.__plist = value
        else:
            top = self.__stack[-1]
            #assert isinstance(top, (dict, list))
            if self.__in_dict:
                k = self.__key
                if k is None:
                    raise PropertyListParseError("Missing key for dictionary.")
                top[k] = value
                self.__key = None
            else:
                top.append(value)

    def _push_stack(self, value):
        self.__stack.append(value)
        self.__in_dict = isinstance(value, dict)

    def _pop_stack(self):
        self.__stack.pop()
        self.__in_dict = self.__stack and isinstance(self.__stack[-1], dict)

    def _start_plist(self, name, attrs):
        self._assert(not self.__stack and self.__plist is None, "<plist> more than once.")
        self._assert(attrs.get('version', '1.0') == '1.0',
                     "version 1.0 is only supported, but was '%s'." % attrs.get('version'))

    def _start_array(self, name, attrs):
        v = list()
        self._push_value(v)
        self._push_stack(v)

    def _start_dict(self, name, attrs):
        v = dict()
        self._push_value(v)
        self._push_stack(v)

    def _end_array(self, name):
        self._pop_stack()

    def _end_dict(self, name):
        if self.__key is not None:
            raise PropertyListParseError("Missing value for key '%s'" % self.__key)
        self._pop_stack()

    def _start_true(self, name, attrs):
        self._push_value(True)

    def _start_false(self, name, attrs):
        self._push_value(False)

    def _parse_key(self, name, content):
        if not self.__in_dict:
            print("XmlPropertyListParser() WARNING: ignoring <key>%s</key> (<key> elements must be contained in <dict> element)" % content)
            #raise PropertyListParseError("<key> element '%s' must be in <dict> element." % content)
        else:
            self.__key = content

    def _parse_string(self, name, content):
        self._push_value(content)

    def _parse_data(self, name, content):
        import base64
        self._push_value(base64.b64decode(content))

    # http://www.apple.com/DTDs/PropertyList-1.0.dtd says:
    #
    # Contents should conform to a subset of ISO 8601
    # (in particular, YYYY '-' MM '-' DD 'T' HH ':' MM ':' SS 'Z'.
    # Smaller units may be omitted with a loss of precision)
    import re
    DATETIME_PATTERN = re.compile(r"(?P<year>\d\d\d\d)(?:-(?P<month>\d\d)(?:-(?P<day>\d\d)(?:T(?P<hour>\d\d)(?::(?P<minute>\d\d)(?::(?P<second>\d\d))?)?)?)?)?Z$")

    def _parse_date(self, name, content):
        import datetime

        units = ('year', 'month', 'day', 'hour', 'minute', 'second', )
        pattern = XmlPropertyListParser.DATETIME_PATTERN
        match = pattern.match(content)
        if not match:
            raise PropertyListParseError("Failed to parse datetime '%s'" % content)

        groups, components = match.groupdict(), []
        for key in units:
            value = groups[key]
            if value is None:
                break
            components.append(int(value))
        while len(components) < 3:
            components.append(1)

        d = datetime.datetime(*components)
        self._push_value(d)

    def _parse_real(self, name, content):
        self._push_value(float(content))

    def _parse_integer(self, name, content):
        self._push_value(int(content))

    START_CALLBACKS = {
        'plist': _start_plist,
        'array': _start_array,
        'dict': _start_dict,
        'true': _start_true,
        'false': _start_false,
    }

    END_CALLBACKS = {
        'array': _end_array,
        'dict': _end_dict,
    }

    PARSE_CALLBACKS = {
        'key': _parse_key,
        'string': _parse_string,
        'data': _parse_data,
        'date': _parse_date,
        'real': _parse_real,
        'integer': _parse_integer,
    }

    # ------------------------------------------------
    # XmlPropertyListParser
    # ------------------------------------------------
    def _to_stream(self, io_or_string):
        if isinstance(io_or_string, basestring):
            # Creates a string stream for in-memory contents.
            from cStringIO import StringIO
            return StringIO(io_or_string)
        elif hasattr(io_or_string, 'read') and callable(getattr(io_or_string, 'read')):
            return io_or_string
        else:
            raise TypeError('Can\'t convert %s to file-like-object' % type(io_or_string))

    def _parse_using_etree(self, xml_input):
        from xml.etree.cElementTree import iterparse

        parser = iterparse(self._to_stream(xml_input), events=(b'start', b'end'))
        self.startDocument()
        try:
            for action, element in parser:
                name = element.tag
                if action == 'start':
                    if name in XmlPropertyListParser.START_CALLBACKS:
                        XmlPropertyListParser.START_CALLBACKS[name](self, element.tag, element.attrib)
                elif action == 'end':
                    if name in XmlPropertyListParser.END_CALLBACKS:
                        XmlPropertyListParser.END_CALLBACKS[name](self, name)
                    if name in XmlPropertyListParser.PARSE_CALLBACKS:
                        XmlPropertyListParser.PARSE_CALLBACKS[name](self, name, element.text or "")
                    element.clear()
        except SyntaxError, e:
            raise PropertyListParseError(e)

        self.endDocument()
        return self.__plist

    def _parse_using_sax_parser(self, xml_input):
        from xml.sax import make_parser, xmlreader, SAXParseException
        source = xmlreader.InputSource()
        source.setByteStream(self._to_stream(xml_input))
        reader = make_parser()
        reader.setContentHandler(self)
        try:
            reader.parse(source)
        except SAXParseException, e:
            raise PropertyListParseError(e)

        return self.__plist

    def parse(self, xml_input):
        """
        Parse the property list (`.plist`, `.xml, for example) ``xml_input``,
        which can be either a string or a file-like object.

        >>> parser = XmlPropertyListParser()
        >>> parser.parse(r'<plist version="1.0">'
        ...              r'<dict><key>Python</key><string>.py</string></dict>'
        ...              r'</plist>')
        {'Python': '.py'}
        """
        try:
            return self._parse_using_etree(xml_input)
        except ImportError:
            # No xml.etree.ccElementTree found.
            return self._parse_using_sax_parser(xml_input)
