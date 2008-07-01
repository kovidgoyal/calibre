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

"""Support for programmatically generating markup streams from Python code using
a very simple syntax. The main entry point to this module is the `tag` object
(which is actually an instance of the ``ElementFactory`` class). You should
rarely (if ever) need to directly import and use any of the other classes in
this module.

Elements can be created using the `tag` object using attribute access. For
example:

>>> doc = tag.p('Some text and ', tag.a('a link', href='http://example.org/'), '.')
>>> doc
<Element "p">

This produces an `Element` instance which can be further modified to add child
nodes and attributes. This is done by "calling" the element: positional
arguments are added as child nodes (alternatively, the `Element.append` method
can be used for that purpose), whereas keywords arguments are added as
attributes:

>>> doc(tag.br)
<Element "p">
>>> print doc
<p>Some text and <a href="http://example.org/">a link</a>.<br/></p>

If an attribute name collides with a Python keyword, simply append an underscore
to the name:

>>> doc(class_='intro')
<Element "p">
>>> print doc
<p class="intro">Some text and <a href="http://example.org/">a link</a>.<br/></p>

As shown above, an `Element` can easily be directly rendered to XML text by
printing it or using the Python ``str()`` function. This is basically a
shortcut for converting the `Element` to a stream and serializing that
stream:

>>> stream = doc.generate()
>>> stream #doctest: +ELLIPSIS
<genshi.core.Stream object at ...>
>>> print stream
<p class="intro">Some text and <a href="http://example.org/">a link</a>.<br/></p>


The `tag` object also allows creating "fragments", which are basically lists
of nodes (elements or text) that don't have a parent element. This can be useful
for creating snippets of markup that are attached to a parent element later (for
example in a template). Fragments are created by calling the `tag` object, which
returns an object of type `Fragment`:

>>> fragment = tag('Hello, ', tag.em('world'), '!')
>>> fragment
<Fragment>
>>> print fragment
Hello, <em>world</em>!
"""

try:
    set
except NameError:
    from sets import Set as set

from calibre.utils.genshi.core import Attrs, Markup, Namespace, QName, Stream, \
                        START, END, TEXT

__all__ = ['Fragment', 'Element', 'ElementFactory', 'tag']
__docformat__ = 'restructuredtext en'


class Fragment(object):
    """Represents a markup fragment, which is basically just a list of element
    or text nodes.
    """
    __slots__ = ['children']

    def __init__(self):
        """Create a new fragment."""
        self.children = []

    def __add__(self, other):
        return Fragment()(self, other)

    def __call__(self, *args):
        """Append any positional arguments as child nodes.
        
        :see: `append`
        """
        map(self.append, args)
        return self

    def __iter__(self):
        return self._generate()

    def __repr__(self):
        return '<%s>' % self.__class__.__name__

    def __str__(self):
        return str(self.generate())

    def __unicode__(self):
        return unicode(self.generate())

    def __html__(self):
        return Markup(self.generate())

    def append(self, node):
        """Append an element or string as child node.
        
        :param node: the node to append; can be an `Element`, `Fragment`, or a
                     `Stream`, or a Python string or number
        """
        if isinstance(node, (Stream, Element, basestring, int, float, long)):
            # For objects of a known/primitive type, we avoid the check for
            # whether it is iterable for better performance
            self.children.append(node)
        elif isinstance(node, Fragment):
            self.children.extend(node.children)
        elif node is not None:
            try:
                map(self.append, iter(node))
            except TypeError:
                self.children.append(node)

    def _generate(self):
        for child in self.children:
            if isinstance(child, Fragment):
                for event in child._generate():
                    yield event
            elif isinstance(child, Stream):
                for event in child:
                    yield event
            else:
                if not isinstance(child, basestring):
                    child = unicode(child)
                yield TEXT, child, (None, -1, -1)

    def generate(self):
        """Return a markup event stream for the fragment.
        
        :rtype: `Stream`
        """
        return Stream(self._generate())


def _kwargs_to_attrs(kwargs):
    attrs = []
    names = set()
    for name, value in kwargs.items():
        name = name.rstrip('_').replace('_', '-')
        if value is not None and name not in names:
            attrs.append((QName(name), unicode(value)))
            names.add(name)
    return Attrs(attrs)


class Element(Fragment):
    """Simple XML output generator based on the builder pattern.

    Construct XML elements by passing the tag name to the constructor:

    >>> print Element('strong')
    <strong/>

    Attributes can be specified using keyword arguments. The values of the
    arguments will be converted to strings and any special XML characters
    escaped:

    >>> print Element('textarea', rows=10, cols=60)
    <textarea rows="10" cols="60"/>
    >>> print Element('span', title='1 < 2')
    <span title="1 &lt; 2"/>
    >>> print Element('span', title='"baz"')
    <span title="&#34;baz&#34;"/>

    The " character is escaped using a numerical entity.
    The order in which attributes are rendered is undefined.

    If an attribute value evaluates to `None`, that attribute is not included
    in the output:

    >>> print Element('a', name=None)
    <a/>

    Attribute names that conflict with Python keywords can be specified by
    appending an underscore:

    >>> print Element('div', class_='warning')
    <div class="warning"/>

    Nested elements can be added to an element using item access notation.
    The call notation can also be used for this and for adding attributes
    using keyword arguments, as one would do in the constructor.

    >>> print Element('ul')(Element('li'), Element('li'))
    <ul><li/><li/></ul>
    >>> print Element('a')('Label')
    <a>Label</a>
    >>> print Element('a')('Label', href="target")
    <a href="target">Label</a>

    Text nodes can be nested in an element by adding strings instead of
    elements. Any special characters in the strings are escaped automatically:

    >>> print Element('em')('Hello world')
    <em>Hello world</em>
    >>> print Element('em')(42)
    <em>42</em>
    >>> print Element('em')('1 < 2')
    <em>1 &lt; 2</em>

    This technique also allows mixed content:

    >>> print Element('p')('Hello ', Element('b')('world'))
    <p>Hello <b>world</b></p>

    Quotes are not escaped inside text nodes:
    >>> print Element('p')('"Hello"')
    <p>"Hello"</p>

    Elements can also be combined with other elements or strings using the
    addition operator, which results in a `Fragment` object that contains the
    operands:
    
    >>> print Element('br') + 'some text' + Element('br')
    <br/>some text<br/>
    
    Elements with a namespace can be generated using the `Namespace` and/or
    `QName` classes:
    
    >>> from genshi.core import Namespace
    >>> xhtml = Namespace('http://www.w3.org/1999/xhtml')
    >>> print Element(xhtml.html, lang='en')
    <html xmlns="http://www.w3.org/1999/xhtml" lang="en"/>
    """
    __slots__ = ['tag', 'attrib']

    def __init__(self, tag_, **attrib):
        Fragment.__init__(self)
        self.tag = QName(tag_)
        self.attrib = _kwargs_to_attrs(attrib)

    def __call__(self, *args, **kwargs):
        """Append any positional arguments as child nodes, and keyword arguments
        as attributes.
        
        :return: the element itself so that calls can be chained
        :rtype: `Element`
        :see: `Fragment.append`
        """
        self.attrib |= _kwargs_to_attrs(kwargs)
        Fragment.__call__(self, *args)
        return self

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.tag)

    def _generate(self):
        yield START, (self.tag, self.attrib), (None, -1, -1)
        for kind, data, pos in Fragment._generate(self):
            yield kind, data, pos
        yield END, self.tag, (None, -1, -1)

    def generate(self):
        """Return a markup event stream for the fragment.
        
        :rtype: `Stream`
        """
        return Stream(self._generate())


class ElementFactory(object):
    """Factory for `Element` objects.
    
    A new element is created simply by accessing a correspondingly named
    attribute of the factory object:
    
    >>> factory = ElementFactory()
    >>> print factory.foo
    <foo/>
    >>> print factory.foo(id=2)
    <foo id="2"/>
    
    Markup fragments (lists of nodes without a parent element) can be created
    by calling the factory:
    
    >>> print factory('Hello, ', factory.em('world'), '!')
    Hello, <em>world</em>!
    
    A factory can also be bound to a specific namespace:
    
    >>> factory = ElementFactory('http://www.w3.org/1999/xhtml')
    >>> print factory.html(lang="en")
    <html xmlns="http://www.w3.org/1999/xhtml" lang="en"/>
    
    The namespace for a specific element can be altered on an existing factory
    by specifying the new namespace using item access:
    
    >>> factory = ElementFactory()
    >>> print factory.html(factory['http://www.w3.org/2000/svg'].g(id=3))
    <html><g xmlns="http://www.w3.org/2000/svg" id="3"/></html>
    
    Usually, the `ElementFactory` class is not be used directly. Rather, the
    `tag` instance should be used to create elements.
    """

    def __init__(self, namespace=None):
        """Create the factory, optionally bound to the given namespace.
        
        :param namespace: the namespace URI for any created elements, or `None`
                          for no namespace
        """
        if namespace and not isinstance(namespace, Namespace):
            namespace = Namespace(namespace)
        self.namespace = namespace

    def __call__(self, *args):
        """Create a fragment that has the given positional arguments as child
        nodes.

        :return: the created `Fragment`
        :rtype: `Fragment`
        """
        return Fragment()(*args)

    def __getitem__(self, namespace):
        """Return a new factory that is bound to the specified namespace.
        
        :param namespace: the namespace URI or `Namespace` object
        :return: an `ElementFactory` that produces elements bound to the given
                 namespace
        :rtype: `ElementFactory`
        """
        return ElementFactory(namespace)

    def __getattr__(self, name):
        """Create an `Element` with the given name.
        
        :param name: the tag name of the element to create
        :return: an `Element` with the specified name
        :rtype: `Element`
        """
        return Element(self.namespace and self.namespace[name] or name)


tag = ElementFactory()
"""Global `ElementFactory` bound to the default namespace.

:type: `ElementFactory`
"""
