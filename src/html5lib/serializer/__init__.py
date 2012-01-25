
from html5lib import treewalkers

from htmlserializer import HTMLSerializer
from xhtmlserializer import XHTMLSerializer

def serialize(input, tree="simpletree", format="html", encoding=None,
              **serializer_opts):
    # XXX: Should we cache this?
    walker = treewalkers.getTreeWalker(tree) 
    if format == "html":
        s = HTMLSerializer(**serializer_opts)
    elif format == "xhtml":
        s = XHTMLSerializer(**serializer_opts)
    else:
        raise ValueError, "type must be either html or xhtml"
    return s.render(walker(input), encoding)
