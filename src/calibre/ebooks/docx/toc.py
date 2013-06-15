#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.docx.names import XPath, descendants
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.oeb.polish.toc import elem_to_toc_text

class Count(object):

    __slots__ = ('val',)

    def __init__(self):
        self.val = 0

def create_toc(body):
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
        return tocroot



