from genshi.core import START, END, XML_NAMESPACE, DOCTYPE, TEXT
from genshi.core  import  START_NS, END_NS, START_CDATA, END_CDATA, PI, COMMENT
from genshi.output import NamespaceFlattener

import _base

from html5lib.constants import voidElements

class TreeWalker(_base.TreeWalker):
    def __iter__(self):
        depth = 0
        ignore_until = None
        previous = None
        for event in self.tree:
            if previous is not None:
                if previous[0] == START:
                    depth += 1
                if ignore_until <= depth:
                    ignore_until = None
                if ignore_until is None:
                    for token in self.tokens(previous, event):
                        yield token
                        if token["type"] == "EmptyTag":
                            ignore_until = depth
                if previous[0] == END:
                    depth -= 1
            previous = event
        if previous is not None:
            if ignore_until is None or ignore_until <= depth:
                for token in self.tokens(previous, None):
                    yield token
            elif ignore_until is not None:
                raise ValueError("Illformed DOM event stream: void element without END_ELEMENT")

    def tokens(self, event, next):
        kind, data, pos = event
        if kind == START:
            tag, attrib = data
            name = tag.localname
            namespace = tag.namespace
            if tag in voidElements:
                for token in self.emptyTag(namespace, name, list(attrib),
                                           not next or next[0] != END 
                                           or next[1] != tag):
                    yield token
            else:
                yield self.startTag(namespace, name, list(attrib))

        elif kind == END:
            name = data.localname
            namespace = data.namespace
            if name not in voidElements:
                yield self.endTag(namespace, name)

        elif kind == COMMENT:
            yield self.comment(data)

        elif kind == TEXT:
            for token in self.text(data):
                yield token

        elif kind == DOCTYPE:
            yield self.doctype(*data)

        elif kind in (XML_NAMESPACE, DOCTYPE, START_NS, END_NS, \
          START_CDATA, END_CDATA, PI):
            pass

        else:
            yield self.unknown(kind)
