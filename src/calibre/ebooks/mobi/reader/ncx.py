#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre import replace_entities
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.mobi.reader.headers import NULL_INDEX
from calibre.ebooks.mobi.reader.index import read_index
from polyglot.builtins import iteritems

tag_fieldname_map = {
        1:  ['pos',0],
        2:  ['len',0],
        3:  ['noffs',0],
        4:  ['hlvl',0],
        5:  ['koffs',0],
        6:  ['pos_fid',0],
        21: ['parent',0],
        22: ['child1',0],
        23: ['childn',0],
        69: ['image_index',0],
        70 : ['desc_offset', 0],  # 'Description offset in cncx'
        71 : ['author_offset', 0],  # 'Author offset in cncx'
        72 : ['image_caption_offset', 0],  # 'Image caption offset in cncx',
        73 : ['image_attr_offset', 0],  # 'Image attribution offset in cncx',

}

default_entry = {
                    'pos':  -1,
                    'len':  0,
                    'noffs': -1,
                    'text' : "Unknown Text",
                    'hlvl' : -1,
                    'kind' : "Unknown Class",
                    'pos_fid' : None,
                    'parent' : -1,
                    'child1' : -1,
                    'childn' : -1,
                    'description': None,
                    'author': None,
                    'image_caption': None,
                    'image_attribution': None,
}


def read_ncx(sections, index, codec):
    index_entries = []

    if index != NULL_INDEX:
        table, cncx = read_index(sections, index, codec)

        for num, x in enumerate(iteritems(table)):
            text, tag_map = x
            entry = default_entry.copy()
            entry['name'] = text
            entry['num'] = num

            for tag in tag_fieldname_map:
                fieldname, i = tag_fieldname_map[tag]
                if tag in tag_map:
                    fieldvalue = tag_map[tag][i]
                    if tag == 6:
                        # Appears to be an idx into the KF8 elems table with an
                        # offset
                        fieldvalue = tuple(tag_map[tag])
                    entry[fieldname] = fieldvalue
                    for which, name in iteritems({3:'text', 5:'kind', 70:'description',
                            71:'author', 72:'image_caption',
                            73:'image_attribution'}):
                        if tag == which:
                            entry[name] = cncx.get(fieldvalue,
                                    default_entry[name])
            index_entries.append(entry)

    return index_entries


def build_toc(index_entries):
    ans = TOC(base_path=os.getcwd())
    levels = {x['hlvl'] for x in index_entries}
    num_map = {-1: ans}
    level_map = {l:[x for x in index_entries if x['hlvl'] == l] for l in
            levels}
    for lvl in sorted(levels):
        for item in level_map[lvl]:
            parent = num_map[item['parent']]
            child = parent.add_item(item['href'], item['idtag'],
                    replace_entities(item['text'], encoding=None))
            num_map[item['num']] = child

    # Set play orders in depth first order
    for i, item in enumerate(ans.flat()):
        item.play_order = i

    return ans
