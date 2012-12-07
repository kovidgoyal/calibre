#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os
from functools import partial
from operator import attrgetter
from collections import namedtuple

from calibre import guess_type
from calibre.ebooks.chardet import xml_to_unicode

def character_count(html):
    ''' Return the number of "significant" text characters in a HTML string. '''
    count = 0
    strip_space = re.compile(r'\s+')
    for match in re.finditer(r'>[^<]+<', html):
        count += len(strip_space.sub(' ', match.group()))-2
    return count

def anchor_map(html):
    ''' Return map of all anchor names to their offsets in the html '''
    ans = {}
    for match in re.finditer(
        r'''(?:id|name)\s*=\s*['"]([^'"]+)['"]''', html):
        anchor = match.group(1)
        ans[anchor] = ans.get(anchor, match.start())
    return ans

class SpineItem(unicode):

    def __new__(cls, path, mime_type=None, read_anchor_map=True,
            run_char_count=True):
        ppath = path.partition('#')[0]
        if not os.path.exists(path) and os.path.exists(ppath):
            path = ppath
        obj = super(SpineItem, cls).__new__(cls, path)
        with open(path, 'rb') as f:
            raw = f.read()
        raw, obj.encoding = xml_to_unicode(raw)
        obj.character_count = character_count(raw) if run_char_count else 10000
        obj.anchor_map = anchor_map(raw) if read_anchor_map else {}
        obj.start_page = -1
        obj.pages      = -1
        obj.max_page   = -1
        obj.index_entries = []
        if mime_type is None:
            mime_type = guess_type(obj)[0]
        obj.mime_type = mime_type
        obj.is_single_page = None
        return obj

class IndexEntry(object):

    def __init__(self, spine, toc_entry, num):
        self.num = num
        self.text = toc_entry.text or _('Unknown')
        self.key = toc_entry.abspath
        self.anchor = self.start_anchor = toc_entry.fragment or None
        try:
            self.spine_pos = spine.index(self.key)
        except ValueError:
            self.spine_pos = -1
        self.anchor_pos = 0
        if self.spine_pos > -1:
            self.anchor_pos = spine[self.spine_pos].anchor_map.get(self.anchor,
                    0)

        self.depth = 0
        p = toc_entry.parent
        while p is not None:
            self.depth += 1
            p = p.parent

        self.sort_key = (self.spine_pos, self.anchor_pos)
        self.spine_count = len(spine)

    def find_end(self, all_entries):
        potential_enders = [i for i in all_entries if
                i.depth <= self.depth and
                (
                    (i.spine_pos == self.spine_pos and i.anchor_pos >
                                                            self.anchor_pos)
                    or
                    i.spine_pos > self.spine_pos
                )]
        if potential_enders:
            # potential_enders is sorted by (spine_pos, anchor_pos)
            end = potential_enders[0]
            self.end_spine_pos = end.spine_pos
            self.end_anchor = end.anchor
        else:
            self.end_spine_pos = self.spine_count - 1
            self.end_anchor = None

def create_indexing_data(spine, toc):
    if not toc: return
    f = partial(IndexEntry, spine)
    index_entries = list(map(f,
        (t for t in toc.flat() if t is not toc),
        (i-1 for i, t in enumerate(toc.flat()) if t is not toc)
        ))
    index_entries.sort(key=attrgetter('sort_key'))
    [ i.find_end(index_entries) for i in index_entries ]

    ie = namedtuple('IndexEntry', 'entry start_anchor end_anchor')

    for spine_pos, spine_item in enumerate(spine):
        for i in index_entries:
            if i.end_spine_pos < spine_pos or i.spine_pos > spine_pos:
                continue # Does not touch this file
            start = i.anchor if i.spine_pos == spine_pos else None
            end = i.end_anchor if i.spine_pos == spine_pos else None
            spine_item.index_entries.append(ie(i, start, end))

