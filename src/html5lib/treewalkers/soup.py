import re
import gettext
_ = gettext.gettext

from BeautifulSoup import BeautifulSoup, Declaration, Comment, Tag
from html5lib.constants import namespaces
import _base

class TreeWalker(_base.NonRecursiveTreeWalker):
    doctype_regexp = re.compile(
        r'(?P<name>[^\s]*)(\s*PUBLIC\s*"(?P<publicId>.*)"\s*"(?P<systemId1>.*)"|\s*SYSTEM\s*"(?P<systemId2>.*)")?')
    def getNodeDetails(self, node):
        if isinstance(node, BeautifulSoup): # Document or DocumentFragment
            return (_base.DOCUMENT,)

        elif isinstance(node, Declaration): # DocumentType
            string = unicode(node.string)
            #Slice needed to remove markup added during unicode conversion,
            #but only in some versions of BeautifulSoup/Python
            if string.startswith('<!') and string.endswith('>'):
                string = string[2:-1]
            m = self.doctype_regexp.match(string)
            #This regexp approach seems wrong and fragile
            #but beautiful soup stores the doctype as a single thing and we want the seperate bits
            #It should work as long as the tree is created by html5lib itself but may be wrong if it's
            #been modified at all
            #We could just feed to it a html5lib tokenizer, I guess...
            assert m is not None, "DOCTYPE did not match expected format"
            name = m.group('name')
            publicId = m.group('publicId')
            if publicId is not None:
                systemId = m.group('systemId1')
            else:
                systemId = m.group('systemId2')
            return _base.DOCTYPE, name, publicId or "", systemId or ""

        elif isinstance(node, Comment):
            string = unicode(node.string)
            if string.startswith('<!--') and string.endswith('-->'):
                string = string[4:-3]
            return _base.COMMENT, string

        elif isinstance(node, unicode): # TextNode
            return _base.TEXT, node

        elif isinstance(node, Tag): # Element
            return (_base.ELEMENT, namespaces["html"], node.name,
                    dict(node.attrs).items(), node.contents)
        else:
            return _base.UNKNOWN, node.__class__.__name__

    def getFirstChild(self, node):
        return node.contents[0]

    def getNextSibling(self, node):
        return node.nextSibling

    def getParentNode(self, node):
        return node.parent
