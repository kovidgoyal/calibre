#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import copy
from future_builtins import map
from urlparse import urlparse

from calibre.ebooks.oeb.base import barename, XPNSMAP, XPath, OPF
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

class SplitLinkReplacer(object):

    def __init__(self, base, bottom_anchors, top_name, bottom_name, container):
        self.bottom_anchors, self.bottom_name = bottom_anchors, bottom_name
        self.container, self.top_name = container, top_name
        self.base = base
        self.replaced = False

    def __call__(self, url):
        if url and url.startswith('#'):
            return url
        name = self.container.href_to_name(url, self.base)
        if name != self.top_name:
            return url
        purl = urlparse(url)
        if purl.fragment and purl.fragment in self.bottom_anchors:
            url = self.container.name_to_href(self.bottom_name, self.base) + '#' + purl.fragment
            self.replaced = True
        return url

def split(container, name, loc_or_xpath, before=True):
    ''' Split the file specified by name at the position specified by loc_or_xpath. '''

    root = container.parsed(name)
    if isinstance(loc_or_xpath, type('')):
        split_point = root.xpath(loc_or_xpath)[0]
    else:
        split_point = node_from_loc(root, loc_or_xpath)
    if in_table(split_point):
        raise ValueError('Cannot split inside tables')
    if split_point.tag.endswith('}body'):
        raise ValueError('Cannot split on the <body> tag')
    tree1, tree2 = do_split(split_point, container.log, before=before)
    root1, root2 = tree1.getroot(), tree2.getroot()
    anchors_in_top = frozenset(root1.xpath('//*/@id')) | frozenset(root1.xpath('//*/@name')) | {''}
    anchors_in_bottom = frozenset(root2.xpath('//*/@id')) | frozenset(root2.xpath('//*/@name'))
    manifest_item = container.generate_item(name, media_type=container.mime_map[name])
    bottom_name = container.href_to_name(manifest_item.get('href'), container.opf_name)

    # Fix links in the split trees
    for r, rname, anchors in [(root1, bottom_name, anchors_in_bottom), (root2, name, anchors_in_top)]:
        for a in r.xpath('//*[@href]'):
            url = a.get('href')
            if url.startswith('#'):
                fname = name
            else:
                fname = container.href_to_name(url, name)
            if fname == name:
                purl = urlparse(url)
                if purl.fragment in anchors:
                    a.set('href', '%s#%s' % (container.name_to_href(rname, name), purl.fragment))

    # Fix all links in the container that point to anchors in the bottom tree
    for fname, media_type in container.mime_map.iteritems():
        if fname not in {name, bottom_name}:
            repl = SplitLinkReplacer(fname, anchors_in_bottom, name, bottom_name, container)
            container.replace_links(fname, repl)

    container.replace(name, root1)
    container.replace(bottom_name, root2)

    spine = container.opf_xpath('//opf:spine')[0]
    for spine_item, spine_name, linear in container.spine_iter:
        if spine_name == name:
            break
    index = spine.index(spine_item) + 1

    si = spine.makeelement(OPF('itemref'), idref=manifest_item.get('id'))
    if not linear:
        si.set('linear', 'no')
    container.insert_into_xml(spine, si, index=index)
    container.dirty(container.opf_name)
    return bottom_name
