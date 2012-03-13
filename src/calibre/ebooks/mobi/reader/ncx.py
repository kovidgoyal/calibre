#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.mobi.utils import to_base
from calibre.ebooks.mobi.reader.headers import NULL_INDEX
from calibre.ebooks.mobi.reader.index import read_index

tag_fieldname_map = {
        1:  ['pos',0],
        2:  ['len',0],
        3:  ['noffs',0],
        4:  ['hlvl',0],
        5:  ['koffs',0],
        6:  ['pos_fid',0],
        21: ['parent',0],
        22: ['child1',0],
        23: ['childn',0]
}

def read_ncx(sections, index, codec):
    index_entries = []

    if index != NULL_INDEX:
        table, cncx = read_index(sections, index, codec)

        for num, x in enumerate(table.iteritems()):
            text, tag_map = x
            entry = {
                    'name': text,
                    'pos':  -1,
                    'len':  0,
                    'noffs': -1,
                    'text' : "Unknown Text",
                    'hlvl' : -1,
                    'kind' : "Unknown Kind",
                    'pos_fid' : None,
                    'parent' : -1,
                    'child1' : -1,
                    'childn' : -1,
                    'num'  : num
            }

            for tag in tag_fieldname_map.keys():
                fieldname, i = tag_fieldname_map[tag]
                if tag in tag_map:
                    fieldvalue = tag_map[tag][i]
                    if tag == 6:
                        fieldvalue = to_base(fieldvalue, base=32)
                    entry[fieldname] = fieldvalue
                    if tag == 3:
                        entry['text'] = cncx.get(fieldvalue, 'Unknown Text')
                    if tag == 5:
                        entry['kind'] = cncx.get(fieldvalue, 'Unknown Kind')
            index_entries.append(entry)

    return index_entries

def build_toc(index_entries):
    ans = TOC(base_path=os.getcwdu())
    levels = {x['hlvl'] for x in index_entries}
    num_map = {-1: ans}
    level_map = {l:[x for x in index_entries if x['hlvl'] == l] for l in
            levels}
    for lvl in sorted(levels):
        for item in level_map[lvl]:
            parent = num_map[item['parent']]
            child = parent.add_item(item['href'], item['idtag'], item['text'])
            num_map[item['num']] = child

    # Set play orders in depth first order
    for i, item in enumerate(ans.flat()):
        item.play_order = i

    return ans

