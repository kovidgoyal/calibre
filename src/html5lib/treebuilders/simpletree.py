import _base
from html5lib.constants import voidElements, namespaces, prefixes
from xml.sax.saxutils import escape

# Really crappy basic implementation of a DOM-core like thing
class Node(_base.Node):
    type = -1
    def __init__(self, name):
        self.name = name
        self.parent = None
        self.value = None
        self.childNodes = []
        self._flags = []

    def __iter__(self):
        for node in self.childNodes:
            yield node
            for item in node:
                yield item

    def __unicode__(self):
        return self.name

    def toxml(self):
        raise NotImplementedError

    def printTree(self, indent=0):
        tree = '\n|%s%s' % (' '* indent, unicode(self))
        for child in self.childNodes:
            tree += child.printTree(indent + 2)
        return tree

    def appendChild(self, node):
        if (isinstance(node, TextNode) and self.childNodes and
          isinstance(self.childNodes[-1], TextNode)):
            self.childNodes[-1].value += node.value
        else:
            self.childNodes.append(node)
        node.parent = self

    def insertText(self, data, insertBefore=None):
        if insertBefore is None:
            self.appendChild(TextNode(data))
        else:
            self.insertBefore(TextNode(data), insertBefore)

    def insertBefore(self, node, refNode):
        index = self.childNodes.index(refNode)
        if (isinstance(node, TextNode) and index > 0 and
          isinstance(self.childNodes[index - 1], TextNode)):
            self.childNodes[index - 1].value += node.value
        else:
            self.childNodes.insert(index, node)
        node.parent = self

    def removeChild(self, node):
        try:
            self.childNodes.remove(node)
        except:
            # XXX
            raise
        node.parent = None

    def cloneNode(self):
        raise NotImplementedError

    def hasContent(self):
        """Return true if the node has children or text"""
        return bool(self.childNodes)

    def getNameTuple(self):
        if self.namespace == None:
            return namespaces["html"], self.name
        else:
            return self.namespace, self.name

    nameTuple = property(getNameTuple)

class Document(Node):
    type = 1
    def __init__(self):
        Node.__init__(self, None)

    def __unicode__(self):
        return "#document"

    def appendChild(self, child):
        Node.appendChild(self, child)

    def toxml(self, encoding="utf=8"):
        result = ""
        for child in self.childNodes:
            result += child.toxml()
        return result.encode(encoding)

    def hilite(self, encoding="utf-8"):
        result = "<pre>"
        for child in self.childNodes:
            result += child.hilite()
        return result.encode(encoding) + "</pre>"
    
    def printTree(self):
        tree = unicode(self)
        for child in self.childNodes:
            tree += child.printTree(2)
        return tree

    def cloneNode(self):
        return Document()

class DocumentFragment(Document):
    type = 2
    def __unicode__(self):
        return "#document-fragment"

    def cloneNode(self):
        return DocumentFragment()

class DocumentType(Node):
    type = 3
    def __init__(self, name, publicId, systemId):
        Node.__init__(self, name)
        self.publicId = publicId
        self.systemId = systemId

    def __unicode__(self):
        if self.publicId or self.systemId:
            publicId = self.publicId or ""
            systemId = self.systemId or ""
            return """<!DOCTYPE %s "%s" "%s">"""%(
                self.name, publicId, systemId)
                            
        else:
            return u"<!DOCTYPE %s>" % self.name
    

    toxml = __unicode__
    
    def hilite(self):
        return '<code class="markup doctype">&lt;!DOCTYPE %s></code>' % self.name

    def cloneNode(self):
        return DocumentType(self.name, self.publicId, self.systemId)

class TextNode(Node):
    type = 4
    def __init__(self, value):
        Node.__init__(self, None)
        self.value = value

    def __unicode__(self):
        return u"\"%s\"" % self.value

    def toxml(self):
        return escape(self.value)
    
    hilite = toxml

    def cloneNode(self):
        return TextNode(self.value)

class Element(Node):
    type = 5
    def __init__(self, name, namespace=None):
        Node.__init__(self, name)
        self.namespace = namespace
        self.attributes = {}

    def __unicode__(self):
        if self.namespace == None:
            return u"<%s>" % self.name
        else:
            return u"<%s %s>"%(prefixes[self.namespace], self.name)

    def toxml(self):
        result = '<' + self.name
        if self.attributes:
            for name,value in self.attributes.iteritems():
                result += u' %s="%s"' % (name, escape(value,{'"':'&quot;'}))
        if self.childNodes:
            result += '>'
            for child in self.childNodes:
                result += child.toxml()
            result += u'</%s>' % self.name
        else:
            result += u'/>'
        return result
    
    def hilite(self):
        result = '&lt;<code class="markup element-name">%s</code>' % self.name
        if self.attributes:
            for name, value in self.attributes.iteritems():
                result += ' <code class="markup attribute-name">%s</code>=<code class="markup attribute-value">"%s"</code>' % (name, escape(value, {'"':'&quot;'}))
        if self.childNodes:
            result += ">"
            for child in self.childNodes:
                result += child.hilite()
        elif self.name in voidElements:
            return result + ">"
        return result + '&lt;/<code class="markup element-name">%s</code>>' % self.name

    def printTree(self, indent):
        tree = '\n|%s%s' % (' '*indent, unicode(self))
        indent += 2
        if self.attributes:
            for name, value in self.attributes.iteritems():
                if isinstance(name, tuple):
                    name = "%s %s"%(name[0], name[1])
                tree += '\n|%s%s="%s"' % (' ' * indent, name, value)
        for child in self.childNodes:
            tree += child.printTree(indent)
        return tree

    def cloneNode(self):
        newNode = Element(self.name)
        if hasattr(self, 'namespace'):
            newNode.namespace = self.namespace
        for attr, value in self.attributes.iteritems():
            newNode.attributes[attr] = value
        return newNode

class CommentNode(Node):
    type = 6
    def __init__(self, data):
        Node.__init__(self, None)
        self.data = data

    def __unicode__(self):
        return "<!-- %s -->" % self.data
    
    def toxml(self):
        return "<!--%s-->" % self.data

    def hilite(self):
        return '<code class="markup comment">&lt;!--%s--></code>' % escape(self.data)

    def cloneNode(self):
        return CommentNode(self.data)

class TreeBuilder(_base.TreeBuilder):
    documentClass = Document
    doctypeClass = DocumentType
    elementClass = Element
    commentClass = CommentNode
    fragmentClass = DocumentFragment
    
    def testSerializer(self, node):
        return node.printTree()
