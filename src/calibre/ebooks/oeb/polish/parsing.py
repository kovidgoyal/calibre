#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import copy, re, warnings
from functools import partial
from bisect import bisect

from lxml.etree import ElementBase, XMLParser, ElementDefaultClassLookup, CommentBase

from html5lib.constants import namespaces, tableInsertModeElements, EOF
from html5lib.treebuilders._base import TreeBuilder as BaseTreeBuilder
from html5lib.ihatexml import InfosetFilter, DataLossWarning
from html5lib.html5parser import HTMLParser

from calibre import xml_replace_entities
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.oeb.parse_utils import fix_self_closing_cdata_tags
from calibre.utils.cleantext import clean_xml_chars

infoset_filter = InfosetFilter()
to_xml_name = infoset_filter.toXmlName
known_namespaces = {namespaces[k]:k for k in ('mathml', 'svg', 'xlink')}
html_ns = namespaces['html']
xlink_ns = namespaces['xlink']

class NamespacedHTMLPresent(ValueError):

    def __init__(self, prefix):
        ValueError.__init__(self, prefix)
        self.prefix = prefix

# Nodes {{{
def ElementFactory(name, namespace=None, context=None):
    context = context or create_lxml_context()
    ns = namespace or namespaces['html']
    try:
        return context.makeelement('{%s}%s' % (ns, name), nsmap={None:ns})
    except ValueError:
        return context.makeelement('{%s}%s' % (ns, to_xml_name(name)), nsmap={None:ns})

class Element(ElementBase):

    ''' Implements the interface required by the html5lib tree builders (see
    html5lib.treebuilders._base.Node) on top of the lxml ElementBase class '''

    def __str__(self):
        attrs = ''
        if self.attrib:
            attrs = ' ' + ' '.join('%s="%s"' % (k, v) for k, v in self.attrib.iteritems())
        ns = self.tag.rpartition('}')[0][1:]
        prefix = {v:k for k, v in self.nsmap.iteritems()}[ns] or ''
        if prefix:
            prefix += ':'
        return '<%s%s%s (%s)>' % (prefix, self.name, attrs, hex(id(self)))
    __repr__ = __str__

    @property
    def attributes(self):
        return self.attrib

    @dynamic_property
    def childNodes(self):
        def fget(self):
            return self
        def fset(self, val):
            self[:] = list(val)
        return property(fget=fget, fset=fset)

    @property
    def parent(self):
        return self.getparent()

    def hasContent(self):
        return bool(self.text or len(self))

    appendChild = ElementBase.append
    removeChild = ElementBase.remove

    def cloneNode(self):
        return self.makeelement(self.tag, nsmap=self.nsmap, attrib=self.attrib)

    def insertBefore(self, node, ref_node):
        self.insert(self.index(ref_node), node)

    def insertText(self, data, insertBefore=None):
        def append_text(el, attr):
            try:
                setattr(el, attr, (getattr(el, attr) or '') + data)
            except ValueError:
                text = data.replace('\u000c', ' ')
                try:
                    setattr(el, attr, (getattr(el, attr) or '') + text)
                except ValueError:
                    setattr(el, attr, (getattr(el, attr) or '') + clean_xml_chars(text))

        if len(self) == 0:
            append_text(self, 'text')
        elif insertBefore is None:
            # Insert the text as the tail of the last child element
            el = self[-1]
            append_text(el, 'tail')
        else:
            # Insert the text before the specified node
            index = self.index(insertBefore)
            if index > 0:
                el = self[index - 1]
                append_text(el, 'tail')
            else:
                append_text(self, 'text')

    def reparentChildren(self, new_parent):
        # Move self.text
        if len(new_parent) > 0:
            el = new_parent[-1]
            el.tail = (el.tail or '') + self.text
        else:
            if self.text:
                new_parent.text = (new_parent.text or '') + self.text
        self.text = None
        for child in self:
            new_parent.append(child)


class Comment(CommentBase):

    @dynamic_property
    def data(self):
        def fget(self):
            return self.text
        def fset(self, val):
            self.text = val.replace('--', '- -')
        return property(fget=fget, fset=fset)

    @property
    def parent(self):
        return self.getparent()

    @property
    def name(self):
        return None

    @property
    def namespace(self):
        return None

    @property
    def nameTuple(self):
        return None, None

    @property
    def childNodes(self):
        return []

    @property
    def attributes(self):
        return {}

    def hasContent(self):
        return bool(self.text)

    def no_op(self, *args, **kwargs):
        pass

    appendChild = no_op
    removeChild = no_op
    insertBefore = no_op
    reparentChildren = no_op

    def insertText(self, text, insertBefore=None):
        self.text = (self.text or '') + text.replace('--', '- -')

    def cloneNode(self):
        return copy.copy(self)

class Document(object):

    def __init__(self):
        self.root = None
        self.doctype = None

    def appendChild(self, child):
        if isinstance(child, ElementBase):
            self.root = child
        elif isinstance(child, DocType):
            self.doctype = child

class DocType(object):

    def __init__(self, name, public_id, system_id):
        self.text = self.name = name
        self.public_id, self.system_id = public_id, system_id

def create_lxml_context():
    parser = XMLParser(no_network=True)
    parser.set_element_class_lookup(ElementDefaultClassLookup(element=Element, comment=Comment))
    return parser

# }}}

def process_attribs(attrs, nsmap):
    attribs = {}
    namespaced_attribs = {}
    xmlns = namespaces['xmlns']
    for k, v in attrs.iteritems():
        if isinstance(k, tuple):
            if k[2] == xmlns:
                prefix, name, ns = k
                if prefix is None:
                    nsmap[None] = v
                else:
                    nsmap[name] = v
            else:
                if k[2] == xlink_ns and 'xlink' not in nsmap:
                    for prefix, ns in tuple(nsmap.iteritems()):
                        if ns == xlink_ns:
                            del nsmap[prefix]
                    nsmap['xlink'] = xlink_ns
                attribs['{%s}%s' % (k[2], k[1])] = v
        else:
            if ':' in k:
                if k.startswith('xmlns') and (k.startswith('xmlns:') or k == 'xmlns'):
                    prefix = k.partition(':')[2] or None
                    if prefix is not None:
                        # Use an existing prefix for this namespace, if
                        # possible
                        existing = {v:k for k, v in nsmap.iteritems()}.get(v, False)
                        if existing is not False:
                            prefix = existing
                    nsmap[prefix] = v
                else:
                    namespaced_attribs[k] = v
            else:
                attribs[k] = v

    for k, v in namespaced_attribs.iteritems():
        prefix, name = k.partition(':')[0::2]
        if prefix == 'xml':
            if name == 'lang':
                attribs['lang'] = attribs.get('lang', v)
            continue
        ns = nsmap.get(prefix, None)
        if ns is not None:
            name = '{%s}%s' % (ns, name)
        attribs[name] =v

    return attribs

class TreeBuilder(BaseTreeBuilder):

    elementClass = ElementFactory
    documentClass = Document
    doctypeClass = DocType

    def __init__(self, namespaceHTMLElements=True):
        BaseTreeBuilder.__init__(self, namespaceHTMLElements)
        self.lxml_context = create_lxml_context()
        self.elementClass = partial(ElementFactory, context=self.lxml_context)
        self.proxy_cache = []

    def getDocument(self):
        return self.document.root

    # The following methods are re-implementations from BaseTreeBuilder to
    # handle namespaces properly.

    def insertRoot(self, token):
        element = self.createElement(token, nsmap={None:namespaces['html']})
        self.openElements.append(element)
        self.document.appendChild(element)

    def createElement(self, token, nsmap=None):
        """Create an element but don't insert it anywhere"""
        nsmap = nsmap or {}
        attribs = process_attribs(token['data'], nsmap)
        name = token_name = token["name"]
        namespace = token.get("namespace", self.defaultNamespace)
        if ':' in name:
            if name.endswith(':html'):
                raise NamespacedHTMLPresent(name.rpartition(':')[0])
            prefix, name = name.partition(':')[0::2]
            namespace = nsmap.get(prefix, namespace)
        try:
            elem = self.lxml_context.makeelement('{%s}%s' % (namespace, name), attrib=attribs, nsmap=nsmap)
        except ValueError:
            attribs = {to_xml_name(k):v for k, v in attribs.iteritems()}
            elem = self.lxml_context.makeelement('{%s}%s' % (namespace, to_xml_name(name)), attrib=attribs, nsmap=nsmap)

        # Ensure that svg and mathml elements get no namespace prefixes
        if elem.prefix is not None and namespace in known_namespaces:
            for k, v in tuple(nsmap.iteritems()):
                if v == namespace:
                    del nsmap[k]
            nsmap[None] = namespace
            elem = self.lxml_context.makeelement(elem.tag, attrib=elem.attrib, nsmap=nsmap)

        # Keep a reference to elem so that lxml does not delete and re-create
        # it, losing the name related attributes
        self.proxy_cache.append(elem)
        elem.name = token_name
        elem.namespace = elem.nsmap[elem.prefix]
        elem.nameTuple = (elem.nsmap[elem.prefix], elem.name)
        return elem

    def insertElementNormal(self, token):
        parent = self.openElements[-1]
        element = self.createElement(token, parent.nsmap)
        parent.appendChild(element)
        self.openElements.append(element)
        return element

    def insertElementTable(self, token):
        """Create an element and insert it into the tree"""
        if self.openElements[-1].name not in tableInsertModeElements:
            return self.insertElementNormal(token)
        # We should be in the InTable mode. This means we want to do
        # special magic element rearranging
        parent, insertBefore = self.getTableMisnestedNodePosition()
        element = self.createElement(token, nsmap=parent.nsmap)
        if insertBefore is None:
            parent.appendChild(element)
        else:
            parent.insertBefore(element, insertBefore)
        self.openElements.append(element)
        return element

    def apply_html_attributes(self, attrs):
        if not attrs:
            return
        html = self.openElements[0]
        nsmap = html.nsmap.copy()
        attribs = process_attribs(attrs, nsmap)
        for k, v in attribs.iteritems():
            if k not in html.attrib:
                try:
                    html.set(k, v)
                except ValueError:
                    html.set(to_xml_name(k), v)
        if nsmap != html.nsmap:
            newroot = self.lxml_context.makeelement(html.tag, attrib=html.attrib, nsmap=nsmap)
            self.proxy_cache.append(newroot)
            newroot.name, newroot.namespace, newroot.nameTuple = html.name, html.namespace, html.nameTuple
            self.openElements[0] = newroot
            if self.document.root is html:
                self.document.root = newroot
            if len(html) > 0:
                # TODO: the nsmap changes need to be propagated down the tree
                for child in html:
                    newroot.append(copy.copy(child))

    def insertComment(self, token, parent=None):
        if parent is None:
            parent = self.openElements[-1]
        parent.appendChild(Comment(token["data"].replace('--', '- -')))

def process_namespace_free_attribs(attrs):
    attribs = {k:v for k, v in attrs.iteritems() if ':' not in k}
    for k in set(attrs) - set(attribs):
        prefix, name = k.partition(':')[0::2]
        if prefix != 'xmlns' and name not in attribs:
            attribs[name] = attrs[k]
    return attribs

class NoNamespaceTreeBuilder(TreeBuilder):

    def __init__(self, namespaceHTMLElements=False):
        BaseTreeBuilder.__init__(self, namespaceHTMLElements)
        self.lxml_context = create_lxml_context()
        self.elementClass = partial(ElementFactory, context=self.lxml_context)
        self.proxy_cache = []

    def createElement(self, token, nsmap=None):
        name = token['name'].rpartition(':')[2]
        attribs = process_namespace_free_attribs(token['data'])
        try:
            elem = self.lxml_context.makeelement(name, attrib=attribs)
        except ValueError:
            attribs = {to_xml_name(k):v for k, v in attribs.iteritems()}
            elem = self.lxml_context.makeelement(to_xml_name(name), attrib=attribs)
        # Keep a reference to elem so that lxml does not delete and re-create
        # it, losing _namespace
        self.proxy_cache.append(elem)
        elem.name = elem.tag
        elem.namespace = token.get('namespace', self.defaultNamespace)
        elem.nameTuple = (elem.namespace or html_ns, elem.name)
        return elem

    def apply_html_attributes(self, attrs):
        if not attrs:
            return
        html = self.openElements[0]
        attribs = process_namespace_free_attribs(attrs)
        for k, v in attribs.iteritems():
            if k not in html.attrib:
                try:
                    html.set(k, v)
                except ValueError:
                    html.set(to_xml_name(k), v)

_regex_cache = {}

class FastStream(object):

    __slots__ = ('raw', 'pos', 'errors', 'new_lines', 'track_position', 'charEncoding')

    def __init__(self, raw, track_position=False):
        self.raw = raw
        self.pos = 0
        self.errors = []
        self.charEncoding = ("utf-8", "certain")
        self.track_position = track_position
        if track_position:
            self.new_lines = tuple(m.start() for m in re.finditer(r'\n', raw))

    def reset(self):
        self.pos = 0

    def char(self):
        try:
            ans = self.raw[self.pos]
        except IndexError:
            return EOF
        self.pos += 1
        return ans

    def unget(self, char):
        if char is not None:
            self.pos = max(0, self.pos - 1)

    def charsUntil(self, characters, opposite=False):
        # Use a cache of regexps to find the required characters
        try:
            chars = _regex_cache[(characters, opposite)]
        except KeyError:
            regex = "".join(["\\x%02x" % ord(c) for c in characters])
            if not opposite:
                regex = "^%s" % regex
            chars = _regex_cache[(characters, opposite)] = re.compile("[%s]+" % regex)

        # Find the longest matching prefix
        m = chars.match(self.raw, self.pos)
        if m is None:
            return ''
        self.pos = m.end()
        return m.group()

    def position(self):
        if not self.track_position:
            return (-1, -1)
        lnum = bisect(self.new_lines, self.pos)
        if lnum == 0:
            return (1, self.pos)
        return (lnum, self.pos - self.new_lines[lnum - 1])

if len("\U0010FFFF") == 1:  # UCS4 build
    replace_chars = re.compile("[\uD800-\uDFFF]")
else:
    replace_chars = re.compile("([\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF])")

def parse(raw, decoder=None, log=None, discard_namespaces=False, line_numbers=True):
    if isinstance(raw, bytes):
        raw = xml_to_unicode(raw)[0] if decoder is None else decoder(raw)
    raw = fix_self_closing_cdata_tags(raw)  # TODO: Handle this in the parser
    raw = xml_replace_entities(raw)
    raw = raw.replace('\r\n', '\n').replace('\r', '\n')
    raw = replace_chars.sub('', raw)

    stream_class = partial(FastStream, track_position=line_numbers)
    stream = stream_class(raw)
    builder = NoNamespaceTreeBuilder if discard_namespaces else TreeBuilder
    while True:
        try:
            parser = HTMLParser(tree=builder, namespaceHTMLElements=not discard_namespaces)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', category=DataLossWarning)
                try:
                    parser.parse(stream, parseMeta=False, useChardet=False)
                finally:
                    parser.tree.proxy_cache = None
        except NamespacedHTMLPresent as err:
            raw = re.sub(r'<\s*/{0,1}(%s:)' % err.prefix, lambda m: m.group().replace(m.group(1), ''), raw, flags=re.I)
            stream = stream_class(raw)
            continue
        break
    root = parser.tree.getDocument()
    if (discard_namespaces and root.tag != 'html') or (
        not discard_namespaces and (root.tag != '{%s}%s' % (namespaces['html'], 'html') or root.prefix)):
        raise ValueError('Failed to parse correctly, root has tag: %s and prefix: %s' % (root.tag, root.prefix))
    return root


if __name__ == '__main__':
    from lxml import etree
    # root = parse('\n<html><head><title>a\n</title><p>&nbsp;\n<b>b', discard_namespaces=False)
    root = parse('\n<html><p><svg viewbox="0 0 0 0"><image xlink:href="xxx"/><b></svg>&nbsp;\n<b>xxx', discard_namespaces=False)
    print (etree.tostring(root, encoding='utf-8'))
    print()

