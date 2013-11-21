#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import copy
from future_builtins import map

from calibre.ebooks.oeb.base import barename, XPNSMAP, XPath
from calibre.ebooks.oeb.polish.toc import node_from_loc

def in_table(node):
    while node is not None:
        if node.tag.endswith('}table'):
            return True
        node = node.getparent()
    return False

def adjust_split_point(split_point, log):
    '''
    Move the split point up its ancestor chain if it has no content
    before it. This handles the common case:
    <div id="chapter1"><h2>Chapter 1</h2>...</div> with a page break on the
    h2.
    '''
    sp = split_point
    while True:
        parent = sp.getparent()
        if (
            parent is None or
            barename(parent.tag) in {'body', 'html'} or
            (parent.text and parent.text.strip()) or
            parent.index(sp) > 0
        ):
            break
        sp = parent

    if sp is not split_point:
        log.debug('Adjusted split point to ancestor')

    return sp

def get_body(root):
    return root.find('h:body', namespaces=XPNSMAP)

def do_split(split_point, log, before=True):
    '''
    Split tree into a *before* and an *after* tree at ``split_point``.

    :param split_point: The Element at which to split
    :param before: If True tree is split before split_point, otherwise after split_point
    :return: before_tree, after_tree
    '''
    if before:
        # We cannot adjust for after since moving an after split point to a
        # parent will cause breakage if the parent contains any content
        # after the original split point
        split_point = adjust_split_point(split_point, log)
    tree         = split_point.getroottree()
    path         = tree.getpath(split_point)

    tree, tree2  = copy.deepcopy(tree), copy.deepcopy(tree)
    root, root2  = tree.getroot(), tree2.getroot()
    body, body2  = map(get_body, (root, root2))
    split_point  = root.xpath(path)[0]
    split_point2 = root2.xpath(path)[0]

    def nix_element(elem, top=True):
        # Remove elem unless top is False in which case replace elem by its
        # children
        parent = elem.getparent()
        if top:
            parent.remove(elem)
        else:
            index = parent.index(elem)
            parent[index:index+1] = list(elem.iterchildren())

    # Tree 1
    hit_split_point = False
    keep_descendants = False
    split_point_descendants = frozenset(split_point.iterdescendants())
    for elem in tuple(body.iterdescendants()):
        if elem is split_point:
            hit_split_point = True
            if before:
                nix_element(elem)
            else:
                # We want to keep the descendants of the split point in
                # Tree 1
                keep_descendants = True
                # We want the split point element, but not its tail
                elem.tail = '\n'

            continue
        if hit_split_point:
            if keep_descendants:
                if elem in split_point_descendants:
                    # elem is a descendant keep it
                    continue
                else:
                    # We are out of split_point, so prevent further set
                    # lookups of split_point_descendants
                    keep_descendants = False
            nix_element(elem)

    # Tree 2
    ancestors = frozenset(XPath('ancestor::*')(split_point2))
    for elem in tuple(body2.iterdescendants()):
        if elem is split_point2:
            if not before:
                # Keep the split point element's tail, if it contains non-whitespace
                # text
                tail = elem.tail
                if tail and not tail.isspace():
                    parent = elem.getparent()
                    idx = parent.index(elem)
                    if idx == 0:
                        parent.text = (parent.text or '') + tail
                    else:
                        sib = parent[idx-1]
                        sib.tail = (sib.tail or '') + tail
                # Remove the element itself
                nix_element(elem)
            break
        if elem in ancestors:
            # We have to preserve the ancestors as they could have CSS
            # styles that are inherited/applicable, like font or
            # width. So we only remove the text, if any.
            elem.text = '\n'
        else:
            nix_element(elem, top=False)

    body2.text = '\n'

    return tree, tree2


def split(container, name, loc):
    root = container.parsed(name)
    split_point = node_from_loc(root, loc)
    if in_table(split_point):
        raise ValueError('Cannot split inside tables')
    if split_point.tag.endswith('}body'):
        raise ValueError('Cannot split on the <body> tag')


