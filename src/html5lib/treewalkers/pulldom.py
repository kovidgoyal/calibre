from xml.dom.pulldom import START_ELEMENT, END_ELEMENT, \
    COMMENT, IGNORABLE_WHITESPACE, CHARACTERS

import _base

from html5lib.constants import voidElements

class TreeWalker(_base.TreeWalker):
    def __iter__(self):
        ignore_until = None
        previous = None
        for event in self.tree:
            if previous is not None and \
              (ignore_until is None or previous[1] is ignore_until):
                if previous[1] is ignore_until:
                    ignore_until = None
                for token in self.tokens(previous, event):
                    yield token
                    if token["type"] == "EmptyTag":
                        ignore_until = previous[1]
            previous = event
        if ignore_until is None or previous[1] is ignore_until:
            for token in self.tokens(previous, None):
                yield token
        elif ignore_until is not None:
            raise ValueError("Illformed DOM event stream: void element without END_ELEMENT")

    def tokens(self, event, next):
        type, node = event
        if type == START_ELEMENT:
            name = node.nodeName
            namespace = node.namespaceURI
            if name in voidElements:
                for token in self.emptyTag(namespace,
                                           name,
                                           node.attributes.items(), 
                                           not next or next[1] is not node):
                    yield token
            else:
                yield self.startTag(namespace, name, node.attributes.items())

        elif type == END_ELEMENT:
            name = node.nodeName
            namespace = node.namespaceURI
            if name not in voidElements:
                yield self.endTag(namespace, name)

        elif type == COMMENT:
            yield self.comment(node.nodeValue)

        elif type in (IGNORABLE_WHITESPACE, CHARACTERS):
            for token in self.text(node.nodeValue):
                yield token

        else:
            yield self.unknown(type)
