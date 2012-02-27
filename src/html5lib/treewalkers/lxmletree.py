from lxml import etree
from html5lib.treebuilders.etree import tag_regexp

from gettext import gettext
_ = gettext

import _base

from html5lib.constants import voidElements
from html5lib import ihatexml

class Root(object):
    def __init__(self, et):
        self.elementtree = et
        self.children = []
        if et.docinfo.internalDTD:
            self.children.append(Doctype(self, et.docinfo.root_name, 
                                         et.docinfo.public_id, 
                                         et.docinfo.system_url))
        root = et.getroot()
        node = root

        while node.getprevious() is not None:
            node = node.getprevious()
        while node is not None:
            self.children.append(node)
            node = node.getnext()

        self.text = None
        self.tail = None
    
    def __getitem__(self, key):
        return self.children[key]

    def getnext(self):
        return None

    def __len__(self):
        return 1

class Doctype(object):
    def __init__(self, root_node, name, public_id, system_id):
        self.root_node = root_node
        self.name = name
        self.public_id = public_id
        self.system_id = system_id
        
        self.text = None
        self.tail = None

    def getnext(self):
        return self.root_node.children[1]

class FragmentRoot(Root):
    def __init__(self, children):
        self.children = [FragmentWrapper(self, child) for child in children]
        self.text = self.tail = None

    def getnext(self):
        return None

class FragmentWrapper(object):
    def __init__(self, fragment_root, obj):
        self.root_node = fragment_root
        self.obj = obj
        if hasattr(self.obj, 'text'):
            self.text = self.obj.text
        else:
            self.text = None
        if hasattr(self.obj, 'tail'):
            self.tail = self.obj.tail
        else:
            self.tail = None
        self.isstring = isinstance(obj, basestring)
        
    def __getattr__(self, name):
        return getattr(self.obj, name)
    
    def getnext(self):
        siblings = self.root_node.children
        idx = siblings.index(self)
        if idx < len(siblings) - 1:
            return siblings[idx + 1]
        else:
            return None

    def __getitem__(self, key):
        return self.obj[key]

    def __nonzero__(self):
        return bool(self.obj)

    def getparent(self):
        return None

    def __str__(self):
        return str(self.obj)

    def __len__(self):
        return len(self.obj)

        
class TreeWalker(_base.NonRecursiveTreeWalker):
    def __init__(self, tree):
        if hasattr(tree, "getroot"):
            tree = Root(tree)
        elif isinstance(tree, list):
            tree = FragmentRoot(tree)
        _base.NonRecursiveTreeWalker.__init__(self, tree)
        self.filter = ihatexml.InfosetFilter()
    def getNodeDetails(self, node):
        if isinstance(node, tuple): # Text node
            node, key = node
            assert key in ("text", "tail"), _("Text nodes are text or tail, found %s") % key
            return _base.TEXT, getattr(node, key)

        elif isinstance(node, Root):
            return (_base.DOCUMENT,)

        elif isinstance(node, Doctype):
            return _base.DOCTYPE, node.name, node.public_id, node.system_id

        elif isinstance(node, FragmentWrapper) and node.isstring:
            return _base.TEXT, node

        elif node.tag == etree.Comment:
            return _base.COMMENT, node.text

        else:
            #This is assumed to be an ordinary element
            match = tag_regexp.match(node.tag)
            if match:
                namespace, tag = match.groups()
            else:
                namespace = None
                tag = node.tag
            return (_base.ELEMENT, namespace, self.filter.fromXmlName(tag), 
                    [(self.filter.fromXmlName(name), value) for 
                     name,value in node.attrib.iteritems()], 
                     len(node) > 0 or node.text)

    def getFirstChild(self, node):
        assert not isinstance(node, tuple), _("Text nodes have no children")

        assert len(node) or node.text, "Node has no children"
        if node.text:
            return (node, "text")
        else:
            return node[0]

    def getNextSibling(self, node):
        if isinstance(node, tuple): # Text node
            node, key = node
            assert key in ("text", "tail"), _("Text nodes are text or tail, found %s") % key
            if key == "text":
                # XXX: we cannot use a "bool(node) and node[0] or None" construct here
                # because node[0] might evaluate to False if it has no child element
                if len(node):
                    return node[0]
                else:
                    return None
            else: # tail
                return node.getnext()

        return node.tail and (node, "tail") or node.getnext()

    def getParentNode(self, node):
        if isinstance(node, tuple): # Text node
            node, key = node
            assert key in ("text", "tail"), _("Text nodes are text or tail, found %s") % key
            if key == "text":
                return node
            # else: fallback to "normal" processing

        return node.getparent()
