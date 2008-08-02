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

"""This module provides different kinds of serialization methods for XML event
streams.
"""

from itertools import chain
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
import re

from calibre.utils.genshi.core import escape, Attrs, Markup, Namespace, QName, StreamEventKind
from calibre.utils.genshi.core import START, END, TEXT, XML_DECL, DOCTYPE, START_NS, END_NS, \
                        START_CDATA, END_CDATA, PI, COMMENT, XML_NAMESPACE

__all__ = ['encode', 'get_serializer', 'DocType', 'XMLSerializer',
           'XHTMLSerializer', 'HTMLSerializer', 'TextSerializer']
__docformat__ = 'restructuredtext en'

def encode(iterator, method='xml', encoding='utf-8', out=None):
    """Encode serializer output into a string.
    
    :param iterator: the iterator returned from serializing a stream (basically
                     any iterator that yields unicode objects)
    :param method: the serialization method; determines how characters not
                   representable in the specified encoding are treated
    :param encoding: how the output string should be encoded; if set to `None`,
                     this method returns a `unicode` object
    :param out: a file-like object that the output should be written to
                instead of being returned as one big string; note that if
                this is a file or socket (or similar), the `encoding` must
                not be `None` (that is, the output must be encoded)
    :return: a `str` or `unicode` object (depending on the `encoding`
             parameter), or `None` if the `out` parameter is provided
    
    :since: version 0.4.1
    :note: Changed in 0.5: added the `out` parameter
    """
    if encoding is not None:
        errors = 'replace'
        if method != 'text' and not isinstance(method, TextSerializer):
            errors = 'xmlcharrefreplace'
        _encode = lambda string: string.encode(encoding, errors)
    else:
        _encode = lambda string: string
    if out is None:
        return _encode(u''.join(list(iterator)))
    for chunk in iterator:
        out.write(_encode(chunk))

def get_serializer(method='xml', **kwargs):
    """Return a serializer object for the given method.
    
    :param method: the serialization method; can be either "xml", "xhtml",
                   "html", "text", or a custom serializer class

    Any additional keyword arguments are passed to the serializer, and thus
    depend on the `method` parameter value.
    
    :see: `XMLSerializer`, `XHTMLSerializer`, `HTMLSerializer`, `TextSerializer`
    :since: version 0.4.1
    """
    if isinstance(method, basestring):
        method = {'xml':   XMLSerializer,
                  'xhtml': XHTMLSerializer,
                  'html':  HTMLSerializer,
                  'text':  TextSerializer}[method.lower()]
    return method(**kwargs)


class DocType(object):
    """Defines a number of commonly used DOCTYPE declarations as constants."""

    HTML_STRICT = (
        'html', '-//W3C//DTD HTML 4.01//EN',
        'http://www.w3.org/TR/html4/strict.dtd'
    )
    HTML_TRANSITIONAL = (
        'html', '-//W3C//DTD HTML 4.01 Transitional//EN',
        'http://www.w3.org/TR/html4/loose.dtd'
    )
    HTML_FRAMESET = (
        'html', '-//W3C//DTD HTML 4.01 Frameset//EN',
        'http://www.w3.org/TR/html4/frameset.dtd'
    )
    HTML = HTML_STRICT

    HTML5 = ('html', None, None)

    XHTML_STRICT = (
        'html', '-//W3C//DTD XHTML 1.0 Strict//EN',
        'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd'
    )
    XHTML_TRANSITIONAL = (
        'html', '-//W3C//DTD XHTML 1.0 Transitional//EN',
        'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'
    )
    XHTML_FRAMESET = (
        'html', '-//W3C//DTD XHTML 1.0 Frameset//EN',
        'http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd'
    )
    XHTML = XHTML_STRICT

    XHTML11 = (
        'html', '-//W3C//DTD XHTML 1.1//EN',
        'http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd'
    )

    SVG_FULL = (
        'svg', '-//W3C//DTD SVG 1.1//EN',
        'http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd'
    )
    SVG_BASIC = (
        'svg', '-//W3C//DTD SVG Basic 1.1//EN',
        'http://www.w3.org/Graphics/SVG/1.1/DTD/svg11-basic.dtd'
    )
    SVG_TINY = (
        'svg', '-//W3C//DTD SVG Tiny 1.1//EN',
        'http://www.w3.org/Graphics/SVG/1.1/DTD/svg11-tiny.dtd'
    )
    SVG = SVG_FULL

    def get(cls, name):
        """Return the ``(name, pubid, sysid)`` tuple of the ``DOCTYPE``
        declaration for the specified name.
        
        The following names are recognized in this version:
         * "html" or "html-strict" for the HTML 4.01 strict DTD
         * "html-transitional" for the HTML 4.01 transitional DTD
         * "html-frameset" for the HTML 4.01 frameset DTD
         * "html5" for the ``DOCTYPE`` proposed for HTML5
         * "xhtml" or "xhtml-strict" for the XHTML 1.0 strict DTD
         * "xhtml-transitional" for the XHTML 1.0 transitional DTD
         * "xhtml-frameset" for the XHTML 1.0 frameset DTD
         * "xhtml11" for the XHTML 1.1 DTD
         * "svg" or "svg-full" for the SVG 1.1 DTD
         * "svg-basic" for the SVG Basic 1.1 DTD
         * "svg-tiny" for the SVG Tiny 1.1 DTD
        
        :param name: the name of the ``DOCTYPE``
        :return: the ``(name, pubid, sysid)`` tuple for the requested
                 ``DOCTYPE``, or ``None`` if the name is not recognized
        :since: version 0.4.1
        """
        return {
            'html': cls.HTML, 'html-strict': cls.HTML_STRICT,
            'html-transitional': DocType.HTML_TRANSITIONAL,
            'html-frameset': DocType.HTML_FRAMESET,
            'html5': cls.HTML5,
            'xhtml': cls.XHTML, 'xhtml-strict': cls.XHTML_STRICT,
            'xhtml-transitional': cls.XHTML_TRANSITIONAL,
            'xhtml-frameset': cls.XHTML_FRAMESET,
            'xhtml11': cls.XHTML11,
            'svg': cls.SVG, 'svg-full': cls.SVG_FULL,
            'svg-basic': cls.SVG_BASIC,
            'svg-tiny': cls.SVG_TINY
        }.get(name.lower())
    get = classmethod(get)


class XMLSerializer(object):
    """Produces XML text from an event stream.
    
    >>> from genshi.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(XMLSerializer()(elem.generate()))
    <div><a href="foo"/><br/><hr noshade="True"/></div>
    """

    _PRESERVE_SPACE = frozenset()

    def __init__(self, doctype=None, strip_whitespace=True,
                 namespace_prefixes=None):
        """Initialize the XML serializer.
        
        :param doctype: a ``(name, pubid, sysid)`` tuple that represents the
                        DOCTYPE declaration that should be included at the top
                        of the generated output, or the name of a DOCTYPE as
                        defined in `DocType.get`
        :param strip_whitespace: whether extraneous whitespace should be
                                 stripped from the output
        :note: Changed in 0.4.2: The  `doctype` parameter can now be a string.
        """
        self.filters = [EmptyTagFilter()]
        if strip_whitespace:
            self.filters.append(WhitespaceFilter(self._PRESERVE_SPACE))
        self.filters.append(NamespaceFlattener(prefixes=namespace_prefixes))
        if doctype:
            self.filters.append(DocTypeInserter(doctype))

    def __call__(self, stream):
        have_decl = have_doctype = False
        in_cdata = False

        for filter_ in self.filters:
            stream = filter_(stream)
        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
                tag, attrib = data
                buf = ['<', tag]
                for attr, value in attrib:
                    buf += [' ', attr, '="', escape(value), '"']
                buf.append(kind is EMPTY and '/>' or '>')
                yield Markup(u''.join(buf))

            elif kind is END:
                yield Markup('</%s>' % data)

            elif kind is TEXT:
                if in_cdata:
                    yield data
                else:
                    yield escape(data, quotes=False)

            elif kind is COMMENT:
                yield Markup('<!--%s-->' % data)

            elif kind is XML_DECL and not have_decl:
                version, encoding, standalone = data
                buf = ['<?xml version="%s"' % version]
                if encoding:
                    buf.append(' encoding="%s"' % encoding)
                if standalone != -1:
                    standalone = standalone and 'yes' or 'no'
                    buf.append(' standalone="%s"' % standalone)
                buf.append('?>\n')
                yield Markup(u''.join(buf))
                have_decl = True

            elif kind is DOCTYPE and not have_doctype:
                name, pubid, sysid = data
                buf = ['<!DOCTYPE %s']
                if pubid:
                    buf.append(' PUBLIC "%s"')
                elif sysid:
                    buf.append(' SYSTEM')
                if sysid:
                    buf.append(' "%s"')
                buf.append('>\n')
                yield Markup(u''.join(buf)) % filter(None, data)
                have_doctype = True

            elif kind is START_CDATA:
                yield Markup('<![CDATA[')
                in_cdata = True

            elif kind is END_CDATA:
                yield Markup(']]>')
                in_cdata = False

            elif kind is PI:
                yield Markup('<?%s %s?>' % data)


class XHTMLSerializer(XMLSerializer):
    """Produces XHTML text from an event stream.
    
    >>> from genshi.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(XHTMLSerializer()(elem.generate()))
    <div><a href="foo"></a><br /><hr noshade="noshade" /></div>
    """

    _EMPTY_ELEMS = frozenset(['area', 'base', 'basefont', 'br', 'col', 'frame',
                              'hr', 'img', 'input', 'isindex', 'link', 'meta',
                              'param'])
    _BOOLEAN_ATTRS = frozenset(['selected', 'checked', 'compact', 'declare',
                                'defer', 'disabled', 'ismap', 'multiple',
                                'nohref', 'noresize', 'noshade', 'nowrap'])
    _PRESERVE_SPACE = frozenset([
        QName('pre'), QName('http://www.w3.org/1999/xhtml}pre'),
        QName('textarea'), QName('http://www.w3.org/1999/xhtml}textarea')
    ])

    def __init__(self, doctype=None, strip_whitespace=True,
                 namespace_prefixes=None, drop_xml_decl=True):
        super(XHTMLSerializer, self).__init__(doctype, False)
        self.filters = [EmptyTagFilter()]
        if strip_whitespace:
            self.filters.append(WhitespaceFilter(self._PRESERVE_SPACE))
        namespace_prefixes = namespace_prefixes or {}
        namespace_prefixes['http://www.w3.org/1999/xhtml'] = ''
        self.filters.append(NamespaceFlattener(prefixes=namespace_prefixes))
        if doctype:
            self.filters.append(DocTypeInserter(doctype))
        self.drop_xml_decl = drop_xml_decl

    def __call__(self, stream):
        boolean_attrs = self._BOOLEAN_ATTRS
        empty_elems = self._EMPTY_ELEMS
        drop_xml_decl = self.drop_xml_decl
        have_decl = have_doctype = False
        in_cdata = False

        for filter_ in self.filters:
            stream = filter_(stream)
        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
                tag, attrib = data
                buf = ['<', tag]
                for attr, value in attrib:
                    if attr in boolean_attrs:
                        value = attr
                    elif attr == u'xml:lang' and u'lang' not in attrib:
                        buf += [' lang="', escape(value), '"']
                    elif attr == u'xml:space':
                        continue
                    buf += [' ', attr, '="', escape(value), '"']
                if kind is EMPTY:
                    if tag in empty_elems:
                        buf.append(' />')
                    else:
                        buf.append('></%s>' % tag)
                else:
                    buf.append('>')
                yield Markup(u''.join(buf))

            elif kind is END:
                yield Markup('</%s>' % data)

            elif kind is TEXT:
                if in_cdata:
                    yield data
                else:
                    yield escape(data, quotes=False)

            elif kind is COMMENT:
                yield Markup('<!--%s-->' % data)

            elif kind is DOCTYPE and not have_doctype:
                name, pubid, sysid = data
                buf = ['<!DOCTYPE %s']
                if pubid:
                    buf.append(' PUBLIC "%s"')
                elif sysid:
                    buf.append(' SYSTEM')
                if sysid:
                    buf.append(' "%s"')
                buf.append('>\n')
                yield Markup(u''.join(buf)) % filter(None, data)
                have_doctype = True

            elif kind is XML_DECL and not have_decl and not drop_xml_decl:
                version, encoding, standalone = data
                buf = ['<?xml version="%s"' % version]
                if encoding:
                    buf.append(' encoding="%s"' % encoding)
                if standalone != -1:
                    standalone = standalone and 'yes' or 'no'
                    buf.append(' standalone="%s"' % standalone)
                buf.append('?>\n')
                yield Markup(u''.join(buf))
                have_decl = True

            elif kind is START_CDATA:
                yield Markup('<![CDATA[')
                in_cdata = True

            elif kind is END_CDATA:
                yield Markup(']]>')
                in_cdata = False

            elif kind is PI:
                yield Markup('<?%s %s?>' % data)


class HTMLSerializer(XHTMLSerializer):
    """Produces HTML text from an event stream.
    
    >>> from genshi.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(HTMLSerializer()(elem.generate()))
    <div><a href="foo"></a><br><hr noshade></div>
    """

    _NOESCAPE_ELEMS = frozenset([
        QName('script'), QName('http://www.w3.org/1999/xhtml}script'),
        QName('style'), QName('http://www.w3.org/1999/xhtml}style')
    ])

    def __init__(self, doctype=None, strip_whitespace=True):
        """Initialize the HTML serializer.
        
        :param doctype: a ``(name, pubid, sysid)`` tuple that represents the
                        DOCTYPE declaration that should be included at the top
                        of the generated output
        :param strip_whitespace: whether extraneous whitespace should be
                                 stripped from the output
        """
        super(HTMLSerializer, self).__init__(doctype, False)
        self.filters = [EmptyTagFilter()]
        if strip_whitespace:
            self.filters.append(WhitespaceFilter(self._PRESERVE_SPACE,
                                                 self._NOESCAPE_ELEMS))
        self.filters.append(NamespaceFlattener(prefixes={
            'http://www.w3.org/1999/xhtml': ''
        }))
        if doctype:
            self.filters.append(DocTypeInserter(doctype))

    def __call__(self, stream):
        boolean_attrs = self._BOOLEAN_ATTRS
        empty_elems = self._EMPTY_ELEMS
        noescape_elems = self._NOESCAPE_ELEMS
        have_doctype = False
        noescape = False

        for filter_ in self.filters:
            stream = filter_(stream)
        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
                tag, attrib = data
                buf = ['<', tag]
                for attr, value in attrib:
                    if attr in boolean_attrs:
                        if value:
                            buf += [' ', attr]
                    elif ':' in attr:
                        if attr == 'xml:lang' and u'lang' not in attrib:
                            buf += [' lang="', escape(value), '"']
                    elif attr != 'xmlns':
                        buf += [' ', attr, '="', escape(value), '"']
                buf.append('>')
                if kind is EMPTY:
                    if tag not in empty_elems:
                        buf.append('</%s>' % tag)
                yield Markup(u''.join(buf))
                if tag in noescape_elems:
                    noescape = True

            elif kind is END:
                yield Markup('</%s>' % data)
                noescape = False

            elif kind is TEXT:
                if noescape:
                    yield data
                else:
                    yield escape(data, quotes=False)

            elif kind is COMMENT:
                yield Markup('<!--%s-->' % data)

            elif kind is DOCTYPE and not have_doctype:
                name, pubid, sysid = data
                buf = ['<!DOCTYPE %s']
                if pubid:
                    buf.append(' PUBLIC "%s"')
                elif sysid:
                    buf.append(' SYSTEM')
                if sysid:
                    buf.append(' "%s"')
                buf.append('>\n')
                yield Markup(u''.join(buf)) % filter(None, data)
                have_doctype = True

            elif kind is PI:
                yield Markup('<?%s %s?>' % data)


class TextSerializer(object):
    """Produces plain text from an event stream.
    
    Only text events are included in the output. Unlike the other serializer,
    special XML characters are not escaped:
    
    >>> from genshi.builder import tag
    >>> elem = tag.div(tag.a('<Hello!>', href='foo'), tag.br)
    >>> print elem
    <div><a href="foo">&lt;Hello!&gt;</a><br/></div>
    >>> print ''.join(TextSerializer()(elem.generate()))
    <Hello!>

    If text events contain literal markup (instances of the `Markup` class),
    that markup is by default passed through unchanged:
    
    >>> elem = tag.div(Markup('<a href="foo">Hello &amp; Bye!</a><br/>'))
    >>> print elem.generate().render(TextSerializer)
    <a href="foo">Hello &amp; Bye!</a><br/>
    
    You can use the ``strip_markup`` to change this behavior, so that tags and
    entities are stripped from the output (or in the case of entities,
    replaced with the equivalent character):

    >>> print elem.generate().render(TextSerializer, strip_markup=True)
    Hello & Bye!
    """

    def __init__(self, strip_markup=False):
        """Create the serializer.
        
        :param strip_markup: whether markup (tags and encoded characters) found
                             in the text should be removed
        """
        self.strip_markup = strip_markup

    def __call__(self, stream):
        strip_markup = self.strip_markup
        for event in stream:
            if event[0] is TEXT:
                data = event[1]
                if strip_markup and type(data) is Markup:
                    data = data.striptags().stripentities()
                yield unicode(data)


class EmptyTagFilter(object):
    """Combines `START` and `STOP` events into `EMPTY` events for elements that
    have no contents.
    """

    EMPTY = StreamEventKind('EMPTY')

    def __call__(self, stream):
        prev = (None, None, None)
        for ev in stream:
            if prev[0] is START:
                if ev[0] is END:
                    prev = EMPTY, prev[1], prev[2]
                    yield prev
                    continue
                else:
                    yield prev
            if ev[0] is not START:
                yield ev
            prev = ev


EMPTY = EmptyTagFilter.EMPTY


class NamespaceFlattener(object):
    r"""Output stream filter that removes namespace information from the stream,
    instead adding namespace attributes and prefixes as needed.
    
    :param prefixes: optional mapping of namespace URIs to prefixes
    
    >>> from genshi.input import XML
    >>> xml = XML('''<doc xmlns="NS1" xmlns:two="NS2">
    ...   <two:item/>
    ... </doc>''')
    >>> for kind, data, pos in NamespaceFlattener()(xml):
    ...     print kind, repr(data)
    START (u'doc', Attrs([(u'xmlns', u'NS1'), (u'xmlns:two', u'NS2')]))
    TEXT u'\n  '
    START (u'two:item', Attrs())
    END u'two:item'
    TEXT u'\n'
    END u'doc'
    """

    def __init__(self, prefixes=None):
        self.prefixes = {XML_NAMESPACE.uri: 'xml'}
        if prefixes is not None:
            self.prefixes.update(prefixes)

    def __call__(self, stream):
        prefixes = dict([(v, [k]) for k, v in self.prefixes.items()])
        namespaces = {XML_NAMESPACE.uri: ['xml']}
        default = prefixes.get('', [''])
        def _push_ns(prefix, uri):
            namespaces.setdefault(uri, []).append(prefix)
            prefixes.setdefault(prefix, []).append(uri)

        ns_attrs = []
        _push_ns_attr = ns_attrs.append
        def _make_ns_attr(prefix, uri):
            return u'xmlns%s' % (prefix and ':%s' % prefix or ''), uri

        def _gen_prefix():
            val = 0
            while 1:
                val += 1
                yield 'ns%d' % val
        _gen_prefix = _gen_prefix().next

        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
                tag, attrs = data

                tagname = tag.localname
                tagns = tag.namespace
                if tagns and tagns != default[-1]:
                    if tagns in namespaces:
                        prefix = namespaces[tagns][-1]
                        if prefix:
                            tagname = u'%s:%s' % (prefix, tagname)
                    else:
                        _push_ns_attr((u'xmlns', tagns))
                        default.push(tagns)

                new_attrs = []
                for attr, value in attrs:
                    attrname = attr.localname
                    attrns = attr.namespace
                    if attrns:
                        if attrns not in namespaces:
                            prefix = _gen_prefix()
                            _push_ns(prefix, attrns)
                            _push_ns_attr(('xmlns:%s' % prefix, attrns))
                        else:
                            prefix = namespaces[attrns][-1]
                        if prefix:
                            attrname = u'%s:%s' % (prefix, attrname)
                    new_attrs.append((attrname, value))

                yield kind, (tagname, Attrs(ns_attrs + new_attrs)), pos
                del ns_attrs[:]

            elif kind is END:
                tagname = data.localname
                tagns = data.namespace
                if tagns and tagns != default[-1]:
                    prefix = namespaces[tagns][-1]
                    if prefix:
                        tagname = u'%s:%s' % (prefix, tagname)
                yield kind, tagname, pos

            elif kind is START_NS:
                prefix, uri = data
                push_attr = False
                if prefix is '' and default[-1] != uri:
                    default.append(uri)
                    _push_ns_attr(_make_ns_attr(prefix, uri))
                elif uri not in namespaces:
                    prefix = namespaces.get(uri, [prefix])[-1]
                    _push_ns_attr(_make_ns_attr(prefix, uri))
                if prefix is not '':
                    _push_ns(prefix, uri)

            elif kind is END_NS:
                if data is '':
                    default.pop()
                if data in prefixes:
                    uris = prefixes.get(data)
                    uri = uris.pop()
                    if not uris:
                        del prefixes[data]
                    if uri not in uris or uri != uris[-1]:
                        uri_prefixes = namespaces[uri]
                        uri_prefixes.pop()
                        if not uri_prefixes:
                            del namespaces[uri]
                    if ns_attrs:
                        attr = _make_ns_attr(data, uri)
                        if attr in ns_attrs:
                            ns_attrs.remove(attr)

            else:
                yield kind, data, pos


class WhitespaceFilter(object):
    """A filter that removes extraneous ignorable white space from the
    stream.
    """

    def __init__(self, preserve=None, noescape=None):
        """Initialize the filter.
        
        :param preserve: a set or sequence of tag names for which white-space
                         should be preserved
        :param noescape: a set or sequence of tag names for which text content
                         should not be escaped
        
        The `noescape` set is expected to refer to elements that cannot contain
        further child elements (such as ``<style>`` or ``<script>`` in HTML
        documents).
        """
        if preserve is None:
            preserve = []
        self.preserve = frozenset(preserve)
        if noescape is None:
            noescape = []
        self.noescape = frozenset(noescape)

    def __call__(self, stream, ctxt=None, space=XML_NAMESPACE['space'],
                 trim_trailing_space=re.compile('[ \t]+(?=\n)').sub,
                 collapse_lines=re.compile('\n{2,}').sub):
        mjoin = Markup('').join
        preserve_elems = self.preserve
        preserve = 0
        noescape_elems = self.noescape
        noescape = False

        textbuf = []
        push_text = textbuf.append
        pop_text = textbuf.pop
        for kind, data, pos in chain(stream, [(None, None, None)]):

            if kind is TEXT:
                if noescape:
                    data = Markup(data)
                push_text(data)
            else:
                if textbuf:
                    if len(textbuf) > 1:
                        text = mjoin(textbuf, escape_quotes=False)
                        del textbuf[:]
                    else:
                        text = escape(pop_text(), quotes=False)
                    if not preserve:
                        text = collapse_lines('\n', trim_trailing_space('', text))
                    yield TEXT, Markup(text), pos

                if kind is START:
                    tag, attrs = data
                    if preserve or (tag in preserve_elems or
                                    attrs.get(space) == 'preserve'):
                        preserve += 1
                    if not noescape and tag in noescape_elems:
                        noescape = True

                elif kind is END:
                    noescape = False
                    if preserve:
                        preserve -= 1

                elif kind is START_CDATA:
                    noescape = True

                elif kind is END_CDATA:
                    noescape = False

                if kind:
                    yield kind, data, pos


class DocTypeInserter(object):
    """A filter that inserts the DOCTYPE declaration in the correct location,
    after the XML declaration.
    """
    def __init__(self, doctype):
        """Initialize the filter.

        :param doctype: DOCTYPE as a string or DocType object.
        """
        if isinstance(doctype, basestring):
            doctype = DocType.get(doctype)
        self.doctype_event = (DOCTYPE, doctype, (None, -1, -1))

    def __call__(self, stream):
        doctype_inserted = False
        for kind, data, pos in stream:
            if not doctype_inserted:
                doctype_inserted = True
                if kind is XML_DECL:
                    yield (kind, data, pos)
                    yield self.doctype_event
                    continue
                yield self.doctype_event

            yield (kind, data, pos)

        if not doctype_inserted:
            yield self.doctype_event
