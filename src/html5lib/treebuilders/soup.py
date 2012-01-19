import warnings

warnings.warn("BeautifulSoup 3.x (as of 3.1) is not fully compatible with html5lib and support will be removed in the future", DeprecationWarning)

from BeautifulSoup import BeautifulSoup, Tag, NavigableString, Comment, Declaration

import _base
from html5lib.constants import namespaces, DataLossWarning

class AttrList(object):
    def __init__(self, element):
        self.element = element
        self.attrs = dict(self.element.attrs)
    def __iter__(self):
        return self.attrs.items().__iter__()
    def __setitem__(self, name, value):
        "set attr", name, value
        self.element[name] = value
    def items(self):
        return self.attrs.items()
    def keys(self):
        return self.attrs.keys()
    def __getitem__(self, name):
        return self.attrs[name]
    def __contains__(self, name):
        return name in self.attrs.keys()


class Element(_base.Node):
    def __init__(self, element, soup, namespace):
        _base.Node.__init__(self, element.name)
        self.element = element
        self.soup = soup
        self.namespace = namespace

    def _nodeIndex(self, node, refNode):
        # Finds a node by identity rather than equality
        for index in range(len(self.element.contents)):
            if id(self.element.contents[index]) == id(refNode.element):
                return index
        return None

    def appendChild(self, node):
        if (node.element.__class__ == NavigableString and self.element.contents
            and self.element.contents[-1].__class__ == NavigableString):
            # Concatenate new text onto old text node
            # (TODO: This has O(n^2) performance, for input like "a</a>a</a>a</a>...")
            newStr = NavigableString(self.element.contents[-1]+node.element)

            # Remove the old text node
            # (Can't simply use .extract() by itself, because it fails if
            # an equal text node exists within the parent node)
            oldElement = self.element.contents[-1]
            del self.element.contents[-1]
            oldElement.parent = None
            oldElement.extract()

            self.element.insert(len(self.element.contents), newStr)
        else:
            self.element.insert(len(self.element.contents), node.element)
            node.parent = self

    def getAttributes(self):
        return AttrList(self.element)

    def setAttributes(self, attributes):
        if attributes:
            for name, value in attributes.items():
                self.element[name] =  value

    attributes = property(getAttributes, setAttributes)
    
    def insertText(self, data, insertBefore=None):
        text = TextNode(NavigableString(data), self.soup)
        if insertBefore:
            self.insertBefore(text, insertBefore)
        else:
            self.appendChild(text)

    def insertBefore(self, node, refNode):
        index = self._nodeIndex(node, refNode)
        if (node.element.__class__ == NavigableString and self.element.contents
            and self.element.contents[index-1].__class__ == NavigableString):
            # (See comments in appendChild)
            newStr = NavigableString(self.element.contents[index-1]+node.element)
            oldNode = self.element.contents[index-1]
            del self.element.contents[index-1]
            oldNode.parent = None
            oldNode.extract()

            self.element.insert(index-1, newStr)
        else:
            self.element.insert(index, node.element)
            node.parent = self

    def removeChild(self, node):
        index = self._nodeIndex(node.parent, node)
        del node.parent.element.contents[index]
        node.element.parent = None
        node.element.extract()
        node.parent = None

    def reparentChildren(self, newParent):
        while self.element.contents:
            child = self.element.contents[0]
            child.extract()
            if isinstance(child, Tag):
                newParent.appendChild(Element(child, self.soup, namespaces["html"]))
            else:
                newParent.appendChild(TextNode(child, self.soup))

    def cloneNode(self):
        node = Element(Tag(self.soup, self.element.name), self.soup, self.namespace)
        for key,value in self.attributes:
            node.attributes[key] = value
        return node

    def hasContent(self):
        return self.element.contents

    def getNameTuple(self):
        if self.namespace == None:
            return namespaces["html"], self.name
        else:
            return self.namespace, self.name

    nameTuple = property(getNameTuple)

class TextNode(Element):
    def __init__(self, element, soup):
        _base.Node.__init__(self, None)
        self.element = element
        self.soup = soup
    
    def cloneNode(self):
        raise NotImplementedError

class TreeBuilder(_base.TreeBuilder):
    def __init__(self, namespaceHTMLElements):
        if namespaceHTMLElements:
            warnings.warn("BeautifulSoup cannot represent elements in any namespace", DataLossWarning)
        _base.TreeBuilder.__init__(self, namespaceHTMLElements)
        
    def documentClass(self):
        self.soup = BeautifulSoup("")
        return Element(self.soup, self.soup, None)
    
    def insertDoctype(self, token):
        name = token["name"]
        publicId = token["publicId"]
        systemId = token["systemId"]

        if publicId:
            self.soup.insert(0, Declaration("%s PUBLIC \"%s\" \"%s\""%(name, publicId, systemId or "")))
        elif systemId:
            self.soup.insert(0, Declaration("%s SYSTEM \"%s\""%
                                            (name, systemId)))
        else:
            self.soup.insert(0, Declaration(name))
    
    def elementClass(self, name, namespace):
        if namespace is not None:
            warnings.warn("BeautifulSoup cannot represent elements in any namespace", DataLossWarning)
        return Element(Tag(self.soup, name), self.soup, namespace)
        
    def commentClass(self, data):
        return TextNode(Comment(data), self.soup)
    
    def fragmentClass(self):
        self.soup = BeautifulSoup("")
        self.soup.name = "[document_fragment]"
        return Element(self.soup, self.soup, None) 

    def appendChild(self, node):
        self.soup.insert(len(self.soup.contents), node.element)

    def testSerializer(self, element):
        return testSerializer(element)

    def getDocument(self):
        return self.soup
    
    def getFragment(self):
        return _base.TreeBuilder.getFragment(self).element
    
def testSerializer(element):
    import re
    rv = []
    def serializeElement(element, indent=0):
        if isinstance(element, Declaration):
            doctype_regexp = r'(?P<name>[^\s]*)( PUBLIC "(?P<publicId>.*)" "(?P<systemId1>.*)"| SYSTEM "(?P<systemId2>.*)")?'
            m = re.compile(doctype_regexp).match(element.string)
            assert m is not None, "DOCTYPE did not match expected format"
            name = m.group('name')
            publicId = m.group('publicId')
            if publicId is not None:
                systemId = m.group('systemId1') or ""
            else:
                systemId = m.group('systemId2')

            if publicId is not None or systemId is not None:
                rv.append("""|%s<!DOCTYPE %s "%s" "%s">"""%
                          (' '*indent, name, publicId or "", systemId or ""))
            else:
                rv.append("|%s<!DOCTYPE %s>"%(' '*indent, name))
            
        elif isinstance(element, BeautifulSoup):
            if element.name == "[document_fragment]":
                rv.append("#document-fragment")                
            else:
                rv.append("#document")

        elif isinstance(element, Comment):
            rv.append("|%s<!-- %s -->"%(' '*indent, element.string))
        elif isinstance(element, unicode):
            rv.append("|%s\"%s\"" %(' '*indent, element))
        else:
            rv.append("|%s<%s>"%(' '*indent, element.name))
            if element.attrs:
                for name, value in element.attrs:
                    rv.append('|%s%s="%s"' % (' '*(indent+2), name, value))
        indent += 2
        if hasattr(element, "contents"):
            for child in element.contents:
                serializeElement(child, indent)
    serializeElement(element, 0)

    return "\n".join(rv)
