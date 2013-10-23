#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import copy

from lxml.etree import ElementBase, XMLParser, ElementDefaultClassLookup, CommentBase

from html5lib.constants import namespaces
from html5lib.treebuilders._base import TreeBuilder as BaseTreeBuilder
from html5lib.ihatexml import InfosetFilter

infoset_filter = InfosetFilter()
coerce_comment = infoset_filter.coerceComment
coerce_text = infoset_filter.coerceCharacters

def create_lxml_context():
    parser = XMLParser()
    parser.set_element_class_lookup(ElementDefaultClassLookup(element=Element, comment=Comment))
    return parser

def ElementFactory(name, namespace=None, context=None):
    context = context or create_lxml_context()
    ns = namespace or namespaces['html']
    return context.makeelement('{%s}%s' % (ns, name), nsmap={None:ns})

def CommentFactory(text):
    return Comment(coerce_comment(text))

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

    @dynamic_property
    def name(self):
        def fget(self):
            return self.tag.rpartition('}')[2]
        def fset(self, val):
            self.tag = '%s}%s' % (self.tag.rpartition('}')[2], val)
        return property(fget=fget, fset=fset)

    @property
    def namespace(self):
        return self.nsmap[self.prefix]

    @dynamic_property
    def attributes(self):
        def fget(self):
            return self.attrib
        def fset(self, val):
            attrs = {('{%s}%s' % k) if isinstance(k, tuple) else k : v for k, v in val.iteritems()}
            self.attrib.clear()
            self.attrib.update(attrs)
        return property(fget=fget, fset=fset)

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
        data = coerce_text(data)
        if len(self) == 0:
            self.text = (self.text or '') + data
        elif insertBefore is None:
            # Insert the text as the tail of the last child element
            el = self[-1]
            el.tail = (el.tail or '') + data
        else:
            # Insert the text before the specified node
            index = self.index(insertBefore)
            if index > 0:
                el = self[index - 1]
                el.tail = (el.tail or '') + data
            else:
                self.text = (self.text or '') + data

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
            self.text = coerce_comment(val)
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
        self.text = (self.text or '') + coerce_comment(text)

    def cloneNode(self):
        return copy.copy(self)

class Document(object):

    def __init__(self):
        self.root = None
        self.doctype = None

    def appendChild(self, child):
        if isinstance(child, Element):
            self.root = child
        elif isinstance(child, DocType):
            self.doctype = child

class DocType(object):

    def __init__(self, name, public_id, system_id):
        self.text = self.name = name
        self.public_id, self.system_id = public_id, system_id

class TreeBuilder(BaseTreeBuilder):

    elementClass = ElementFactory
    commentClass = Comment
    documentClass = Document
    doctypeClass = DocType

    def __init__(self):
        BaseTreeBuilder.__init__(self, True)

