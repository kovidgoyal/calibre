#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from bisect import bisect

class PositionFinder(object):

    def __init__(self, raw):
        pat = br'\n' if isinstance(raw, bytes) else r'\n'
        self.new_lines = tuple(m.start() + 1 for m in re.finditer(pat, raw))

    def __call__(self, pos):
        lnum = bisect(self.new_lines, pos)
        try:
            offset = abs(pos - self.new_lines[lnum - 1])
        except IndexError:
            offset = pos
        return (lnum + 1, offset)

class CommentFinder(object):

    def __init__(self, raw, pat=r'(?s)/\*.*?\*/'):
        self.starts, self.ends = [], []
        for m in re.finditer(pat, raw):
            start, end = m.span()
            self.starts.append(start), self.ends.append(end)

    def __call__(self, offset):
        if not self.starts:
            return False
        q = bisect(self.starts, offset) - 1
        return q >= 0 and self.starts[q] <= offset <= self.ends[q]

def link_stylesheets(container, names, sheets, remove=False, mtype='text/css'):
    from calibre.ebooks.oeb.base import XPath, XHTML
    changed_names = set()
    snames = set(sheets)
    lp = XPath('//h:link[@href]')
    hp = XPath('//h:head')
    for name in names:
        root = container.parsed(name)
        if remove:
            for link in lp(root):
                if (link.get('type', mtype) or mtype) == mtype:
                    container.remove_from_xml(link)
                    changed_names.add(name)
                    container.dirty(name)
        existing = {container.href_to_name(l.get('href'), name) for l in lp(root) if (l.get('type', mtype) or mtype) == mtype}
        extra = snames - existing
        if extra:
            changed_names.add(name)
            try:
                parent = hp(root)[0]
            except (TypeError, IndexError):
                parent = XHTML('head')
                container.insert_into_xml(root, parent, index=0)
            for sheet in sheets:
                if sheet in extra:
                    container.insert_into_xml(
                        parent, parent.makeelement(XHTML('link'), rel='stylesheet', type=mtype,
                                                   href=container.name_to_href(sheet, name)))
            container.dirty(name)

    return changed_names
