import gettext
_ = gettext.gettext

import _base

class TreeWalker(_base.NonRecursiveTreeWalker):
    """Given that simpletree has no performant way of getting a node's
    next sibling, this implementation returns "nodes" as tuples with the
    following content:

    1. The parent Node (Element, Document or DocumentFragment)

    2. The child index of the current node in its parent's children list

    3. A list used as a stack of all ancestors. It is a pair tuple whose
       first item is a parent Node and second item is a child index.
    """

    def getNodeDetails(self, node):
        if isinstance(node, tuple): # It might be the root Node
            parent, idx, parents = node
            node = parent.childNodes[idx]

        # testing node.type allows us not to import treebuilders.simpletree
        if node.type in (1, 2): # Document or DocumentFragment
            return (_base.DOCUMENT,)

        elif node.type == 3: # DocumentType
            return _base.DOCTYPE, node.name, node.publicId, node.systemId

        elif node.type == 4: # TextNode
            return _base.TEXT, node.value

        elif node.type == 5: # Element
            return (_base.ELEMENT, node.namespace, node.name, 
                    node.attributes.items(), node.hasContent())

        elif node.type == 6: # CommentNode
            return _base.COMMENT, node.data

        else:
            return _node.UNKNOWN, node.type

    def getFirstChild(self, node):
        if isinstance(node, tuple): # It might be the root Node
            parent, idx, parents = node
            parents.append((parent, idx))
            node = parent.childNodes[idx]
        else:
            parents = []

        assert node.hasContent(), "Node has no children"
        return (node, 0, parents)

    def getNextSibling(self, node):
        assert isinstance(node, tuple), "Node is not a tuple: " + str(node)
        parent, idx, parents = node
        idx += 1
        if len(parent.childNodes) > idx:
            return (parent, idx, parents)
        else:
            return None

    def getParentNode(self, node):
        assert isinstance(node, tuple)
        parent, idx, parents = node
        if parents:
            parent, idx = parents.pop()
            return parent, idx, parents
        else:
            # HACK: We could return ``parent`` but None will stop the algorithm the same way
            return None
