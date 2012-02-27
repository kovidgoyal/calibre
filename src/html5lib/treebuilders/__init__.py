"""A collection of modules for building different kinds of tree from
HTML documents.

To create a treebuilder for a new type of tree, you need to do
implement several things:

1) A set of classes for various types of elements: Document, Doctype,
Comment, Element. These must implement the interface of
_base.treebuilders.Node (although comment nodes have a different
signature for their constructor, see treebuilders.simpletree.Comment)
Textual content may also be implemented as another node type, or not, as
your tree implementation requires.

2) A treebuilder object (called TreeBuilder by convention) that
inherits from treebuilders._base.TreeBuilder. This has 4 required attributes:
documentClass - the class to use for the bottommost node of a document
elementClass - the class to use for HTML Elements
commentClass - the class to use for comments
doctypeClass - the class to use for doctypes
It also has one required method:
getDocument - Returns the root node of the complete document tree

3) If you wish to run the unit tests, you must also create a
testSerializer method on your treebuilder which accepts a node and
returns a string containing Node and its children serialized according
to the format used in the unittests

The supplied simpletree module provides a python-only implementation
of a full treebuilder and is a useful reference for the semantics of
the various methods.
"""

treeBuilderCache = {}

def getTreeBuilder(treeType, implementation=None, **kwargs):
    """Get a TreeBuilder class for various types of tree with built-in support
    
    treeType - the name of the tree type required (case-insensitive). Supported
               values are "simpletree", "dom", "etree" and "beautifulsoup"
               
               "simpletree" - a built-in DOM-ish tree type with support for some
                              more pythonic idioms.
                "dom" - A generic builder for DOM implementations, defaulting to
                        a xml.dom.minidom based implementation for the sake of
                        backwards compatibility (as releases up until 0.10 had a
                        builder called "dom" that was a minidom implemenation).
                "etree" - A generic builder for tree implementations exposing an
                          elementtree-like interface (known to work with
                          ElementTree, cElementTree and lxml.etree).
                "beautifulsoup" - Beautiful soup (if installed)
               
    implementation - (Currently applies to the "etree" and "dom" tree types). A
                      module implementing the tree type e.g.
                      xml.etree.ElementTree or lxml.etree."""
    
    treeType = treeType.lower()
    if treeType not in treeBuilderCache:
        if treeType == "dom":
            import dom
            # XXX: Keep backwards compatibility by using minidom if no implementation is given
            if implementation == None:
                from xml.dom import minidom
                implementation = minidom
            # XXX: NEVER cache here, caching is done in the dom submodule
            return dom.getDomModule(implementation, **kwargs).TreeBuilder
        elif treeType == "simpletree":
            import simpletree
            treeBuilderCache[treeType] = simpletree.TreeBuilder
        elif treeType == "beautifulsoup":
            import soup
            treeBuilderCache[treeType] = soup.TreeBuilder
        elif treeType == "lxml":
            import etree_lxml
            treeBuilderCache[treeType] = etree_lxml.TreeBuilder
        elif treeType == "etree":
            # Come up with a sane default
            if implementation == None:
                try:
                    import xml.etree.cElementTree as ET
                except ImportError:
                    try:
                        import xml.etree.ElementTree as ET
                    except ImportError:
                        try:
                            import cElementTree as ET
                        except ImportError:
                            import elementtree.ElementTree as ET
                implementation = ET
            import etree
            # XXX: NEVER cache here, caching is done in the etree submodule
            return etree.getETreeModule(implementation, **kwargs).TreeBuilder
    return treeBuilderCache.get(treeType)
