#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import namedtuple
from itertools import count

from lxml.etree import tostring

from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.oeb.polish.toc import elem_to_toc_text
from polyglot.builtins import iteritems, range


def from_headings(body, log, namespace, num_levels=3):
    ' Create a TOC from headings in the document '
    tocroot = TOC()
    all_heading_nodes = body.xpath('//*[@data-heading-level]')
    level_prev = {i+1:None for i in range(num_levels)}
    level_prev[0] = tocroot
    level_item_map = {i:frozenset(
        x for x in all_heading_nodes if int(x.get('data-heading-level')) == i)
        for i in range(1, num_levels+1)}
    item_level_map = {e:i for i, elems in iteritems(level_item_map) for e in elems}

    idcount = count()

    def ensure_id(elem):
        ans = elem.get('id', None)
        if not ans:
            ans = 'toc_id_%d' % (next(idcount) + 1)
            elem.set('id', ans)
        return ans

    for item in all_heading_nodes:
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
        for i in range(lvl+1, num_levels+1):
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
        for i in range(level+1, len(last_found)):
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

    return tostring(a, method='text', with_tail=False, encoding='unicode').strip()


def from_toc(docx, link_map, styles, object_map, log, namespace):
    XPath, get, ancestor = namespace.XPath, namespace.get, namespace.ancestor
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


def create_toc(docx, body, link_map, styles, object_map, log, namespace):
    ans = from_toc(docx, link_map, styles, object_map, log, namespace) or from_headings(body, log, namespace)
    # Remove heading level attributes
    for h in body.xpath('//*[@data-heading-level]'):
        del h.attrib['data-heading-level']
    return ans
