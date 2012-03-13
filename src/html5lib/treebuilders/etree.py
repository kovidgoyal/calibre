import new
import re

import _base
from html5lib import ihatexml
from html5lib import constants
from html5lib.constants import namespaces

tag_regexp = re.compile("{([^}]*)}(.*)")

moduleCache = {}

def getETreeModule(ElementTreeImplementation, fullTree=False):
    name = "_" + ElementTreeImplementation.__name__+"builder"
    if name in moduleCache:
        return moduleCache[name]
    else:
        mod = new.module("_" + ElementTreeImplementation.__name__+"builder")
        objs = getETreeBuilder(ElementTreeImplementation, fullTree)
        mod.__dict__.update(objs)
        moduleCache[name] = mod    
        return mod

def getETreeBuilder(ElementTreeImplementation, fullTree=False):
    ElementTree = ElementTreeImplementation
    class Element(_base.Node):
        def __init__(self, name, namespace=None):
            self._name = name
            self._namespace = namespace
            self._element = ElementTree.Element(self._getETreeTag(name,
                                                                  namespace))
            if namespace is None:
                self.nameTuple = namespaces["html"], self._name
            else:
                self.nameTuple = self._namespace, self._name
            self.parent = None
            self._childNodes = []
            self._flags = []

        def _getETreeTag(self, name, namespace):
            if namespace is None:
                etree_tag = name
            else:
                etree_tag = "{%s}%s"%(namespace, name)
            return etree_tag
    
        def _setName(self, name):
            self._name = name
            self._element.tag = self._getETreeTag(self._name, self._namespace)
        
        def _getName(self):
            return self._name
        
        name = property(_getName, _setName)

        def _setNamespace(self, namespace):
            self._namespace = namespace
            self._element.tag = self._getETreeTag(self._name, self._namespace)

        def _getNamespace(self):
            return self._namespace

        namespace = property(_getNamespace, _setNamespace)
    
        def _getAttributes(self):
            return self._element.attrib
    
        def _setAttributes(self, attributes):
            #Delete existing attributes first
            #XXX - there may be a better way to do this...
            for key in self._element.attrib.keys():
                del self._element.attrib[key]
            for key, value in attributes.iteritems():
                if isinstance(key, tuple):
                    name = "{%s}%s"%(key[2], key[1])
                else:
                    name = key
                self._element.set(name, value)
    
        attributes = property(_getAttributes, _setAttributes)
    
        def _getChildNodes(self):
            return self._childNodes    
        def _setChildNodes(self, value):
            del self._element[:]
            self._childNodes = []
            for element in value:
                self.insertChild(element)
    
        childNodes = property(_getChildNodes, _setChildNodes)
    
        def hasContent(self):
            """Return true if the node has children or text"""
            return bool(self._element.text or self._element.getchildren())
    
        def appendChild(self, node):
            self._childNodes.append(node)
            self._element.append(node._element)
            node.parent = self
    
        def insertBefore(self, node, refNode):
            index = self._element.getchildren().index(refNode._element)
            self._element.insert(index, node._element)
            node.parent = self
    
        def removeChild(self, node):
            self._element.remove(node._element)
            node.parent=None
    
        def insertText(self, data, insertBefore=None):
            if not(len(self._element)):
                if not self._element.text:
                    self._element.text = ""
                self._element.text += data
            elif insertBefore is None:
                #Insert the text as the tail of the last child element
                if not self._element[-1].tail:
                    self._element[-1].tail = ""
                self._element[-1].tail += data
            else:
                #Insert the text before the specified node
                children = self._element.getchildren()
                index = children.index(insertBefore._element)
                if index > 0:
                    if not self._element[index-1].tail:
                        self._element[index-1].tail = ""
                    self._element[index-1].tail += data
                else:
                    if not self._element.text:
                        self._element.text = ""
                    self._element.text += data
    
        def cloneNode(self):
            element = Element(self.name, self.namespace)
            for name, value in self.attributes.iteritems():
                element.attributes[name] = value
            return element
    
        def reparentChildren(self, newParent):
            if newParent.childNodes:
                newParent.childNodes[-1]._element.tail += self._element.text
            else:
                if not newParent._element.text:
                    newParent._element.text = ""
                if self._element.text is not None:
                    newParent._element.text += self._element.text
            self._element.text = ""
            _base.Node.reparentChildren(self, newParent)
    
    class Comment(Element):
        def __init__(self, data):
            #Use the superclass constructor to set all properties on the 
            #wrapper element
            self._element = ElementTree.Comment(data)
            self.parent = None
            self._childNodes = []
            self._flags = []
            
        def _getData(self):
            return self._element.text
    
        def _setData(self, value):
            self._element.text = value
    
        data = property(_getData, _setData)
    
    class DocumentType(Element):
        def __init__(self, name, publicId, systemId):
            Element.__init__(self, "<!DOCTYPE>") 
            self._element.text = name
            self.publicId = publicId
            self.systemId = systemId

        def _getPublicId(self):
            return self._element.get(u"publicId", "")

        def _setPublicId(self, value):
            if value is not None:
                self._element.set(u"publicId", value)

        publicId = property(_getPublicId, _setPublicId)
    
        def _getSystemId(self):
            return self._element.get(u"systemId", "")

        def _setSystemId(self, value):
            if value is not None:
                self._element.set(u"systemId", value)

        systemId = property(_getSystemId, _setSystemId)
    
    class Document(Element):
        def __init__(self):
            Element.__init__(self, "<DOCUMENT_ROOT>") 
    
    class DocumentFragment(Element):
        def __init__(self):
            Element.__init__(self, "<DOCUMENT_FRAGMENT>")
    
    def testSerializer(element):
        rv = []
        finalText = None
        def serializeElement(element, indent=0):
            if not(hasattr(element, "tag")):
                element = element.getroot()
            if element.tag == "<!DOCTYPE>":
                if element.get("publicId") or element.get("systemId"):
                    publicId = element.get("publicId") or ""
                    systemId = element.get("systemId") or ""
                    rv.append( """<!DOCTYPE %s "%s" "%s">"""%(
                            element.text, publicId, systemId))
                else:     
                    rv.append("<!DOCTYPE %s>"%(element.text,))
            elif element.tag == "<DOCUMENT_ROOT>":
                rv.append("#document")
                if element.text:
                    rv.append("|%s\"%s\""%(' '*(indent+2), element.text))
                if element.tail:
                    finalText = element.tail
            elif type(element.tag) == type(ElementTree.Comment):
                rv.append("|%s<!-- %s -->"%(' '*indent, element.text))
            else:
                nsmatch = tag_regexp.match(element.tag)

                if nsmatch is None:
                    name = element.tag
                else:
                    ns, name = nsmatch.groups()
                    prefix = constants.prefixes[ns]
                    name = "%s %s"%(prefix, name)
                rv.append("|%s<%s>"%(' '*indent, name))

                if hasattr(element, "attrib"):
                    for name, value in element.attrib.iteritems():
                        nsmatch = tag_regexp.match(name)
                        if nsmatch is not None:
                            ns, name = nsmatch.groups()
                            prefix = constants.prefixes[ns]
                            name = "%s %s"%(prefix, name)
                        rv.append('|%s%s="%s"' % (' '*(indent+2), name, value))
                if element.text:
                    rv.append("|%s\"%s\"" %(' '*(indent+2), element.text))
            indent += 2
            for child in element.getchildren():
                serializeElement(child, indent)
            if element.tail:
                rv.append("|%s\"%s\"" %(' '*(indent-2), element.tail))
        serializeElement(element, 0)
    
        if finalText is not None:
            rv.append("|%s\"%s\""%(' '*2, finalText))
    
        return "\n".join(rv)
    
    def tostring(element):
        """Serialize an element and its child nodes to a string"""
        rv = []
        finalText = None
        filter = ihatexml.InfosetFilter()
        def serializeElement(element):
            if type(element) == type(ElementTree.ElementTree):
                element = element.getroot()
            
            if element.tag == "<!DOCTYPE>":
                if element.get("publicId") or element.get("systemId"):
                    publicId = element.get("publicId") or ""
                    systemId = element.get("systemId") or ""
                    rv.append( """<!DOCTYPE %s PUBLIC "%s" "%s">"""%(
                            element.text, publicId, systemId))
                else:     
                    rv.append("<!DOCTYPE %s>"%(element.text,))
            elif element.tag == "<DOCUMENT_ROOT>":
                if element.text:
                    rv.append(element.text)
                if element.tail:
                    finalText = element.tail
    
                for child in element.getchildren():
                    serializeElement(child)
    
            elif type(element.tag) == type(ElementTree.Comment):
                rv.append("<!--%s-->"%(element.text,))
            else:
                #This is assumed to be an ordinary element
                if not element.attrib:
                    rv.append("<%s>"%(filter.fromXmlName(element.tag),))
                else:
                    attr = " ".join(["%s=\"%s\""%(
                                filter.fromXmlName(name), value) 
                                     for name, value in element.attrib.iteritems()])
                    rv.append("<%s %s>"%(element.tag, attr))
                if element.text:
                    rv.append(element.text)
    
                for child in element.getchildren():
                    serializeElement(child)
    
                rv.append("</%s>"%(element.tag,))
    
            if element.tail:
                rv.append(element.tail)
    
        serializeElement(element)
    
        if finalText is not None:
            rv.append("%s\""%(' '*2, finalText))
    
        return "".join(rv)
    
    class TreeBuilder(_base.TreeBuilder):
        documentClass = Document
        doctypeClass = DocumentType
        elementClass = Element
        commentClass = Comment
        fragmentClass = DocumentFragment
    
        def testSerializer(self, element):
            return testSerializer(element)
    
        def getDocument(self):
            if fullTree:
                return self.document._element
            else:
                return self.document._element.find("html")
        
        def getFragment(self):
            return _base.TreeBuilder.getFragment(self)._element
        
    return locals()
