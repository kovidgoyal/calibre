#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import namedtuple

from lxml.etree import tostring

from calibre.ebooks.docx.names import XPath, descendants, get, ancestor
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.oeb.polish.toc import elem_to_toc_text

class Count(object):

    __slots__ = ('val',)

    def __init__(self):
        self.val = 0

def from_headings(body, log):
    ' Create a TOC from headings in the document '
    headings = ('h1', 'h2', 'h3')
    tocroot = TOC()
    xpaths = [XPath('//%s' % x) for x in headings]
    level_prev = {i+1:None for i in xrange(len(xpaths))}
    level_prev[0] = tocroot
    level_item_map = {i+1:frozenset(xp(body)) for i, xp in enumerate(xpaths)}
    item_level_map = {e:i for i, elems in level_item_map.iteritems() for e in elems}

    idcount = Count()

    def ensure_id(elem):
        ans = elem.get('id', None)
        if not ans:
            idcount.val += 1
            ans = 'toc_id_%d' % idcount.val
            elem.set('id', ans)
        return ans

    for item in descendants(body, *headings):
        lvl = plvl = item_level_map.get(item, None)
        if lvl is None:
            continue
        parent = None
        while parent is None:
            plvl -= 1
            parent = level_prev[plvl]
        lvl = plvl + 1
        elem_id = ensure_id(item)
        text = elem_to_toc_text(item)
        toc = parent.add_item('index.html', elem_id, text)
        level_prev[lvl] = toc
        for i in xrange(lvl+1, len(xpaths)+1):
            level_prev[i] = None

    if len(tuple(tocroot.flat())) > 1:
        log('Generating Table of Contents from headings')
        return tocroot

def structure_toc(entries):
    indent_vals = sorted({x.indent for x in entries})
    last_found = [None for i in indent_vals]
    newtoc = TOC()

    if len(indent_vals) > 6:
        for x in entries:
            newtoc.add_item('index.html', x.anchor, x.text)
        return newtoc

    def find_parent(level):
        candidates = last_found[:level]
        for x in reversed(candidates):
            if x is not None:
                return x
        return newtoc

    for item in entries:
        level = indent_vals.index(item.indent)
        parent = find_parent(level)
        last_found[level] = parent.add_item('index.html', item.anchor,
                    item.text)
        for i in xrange(level+1, len(last_found)):
            last_found[i] = None

    return newtoc

def link_to_txt(a, styles, object_map):
    if len(a) > 1:
        for child in a:
            run = object_map.get(child, None)
            if run is not None:
                rs = styles.resolve(run)
                if rs.css.get('display', None) == 'none':
                    a.remove(child)

    return tostring(a, method='text', with_tail=False, encoding=unicode).strip()

def from_toc(docx, link_map, styles, object_map, log):
    toc_level = None
    level = 0
    TI = namedtuple('TI', 'text anchor indent')
    toc = []
    for tag in XPath('//*[(@w:fldCharType and name()="w:fldChar") or name()="w:hyperlink" or name()="w:instrText"]')(docx):
        n = tag.tag.rpartition('}')[-1]
        if n == 'fldChar':
            t = get(tag, 'w:fldCharType')
            if t == 'begin':
                level += 1
            elif t == 'end':
                level -= 1
                if toc_level is not None and level < toc_level:
                    break
        elif n == 'instrText':
            if level > 0 and tag.text and tag.text.strip().startswith('TOC '):
                toc_level = level
        elif n == 'hyperlink':
            if toc_level is not None and level >= toc_level and tag in link_map:
                a = link_map[tag]
                href = a.get('href', None)
                txt = link_to_txt(a, styles, object_map)
                p = ancestor(tag, 'w:p')
                if txt and href and p is not None:
                    ps = styles.resolve_paragraph(p)
                    try:
                        ml = int(ps.margin_left[:-2])
                    except (TypeError, ValueError, AttributeError):
                        ml = 0
                    if ps.text_align in {'center', 'right'}:
                        ml = 0
                    toc.append(TI(txt, href[1:], ml))
    if toc:
        log('Found Word Table of Contents, using it to generate the Table of Contents')
        return structure_toc(toc)

def create_toc(docx, body, link_map, styles, object_map, log):
    return from_toc(docx, link_map, styles, object_map, log) or from_headings(body, log)


