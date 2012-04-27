#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import namedtuple
from functools import partial

from calibre.ebooks.mobi.utils import (RECORD_SIZE, encode_trailing_data,
        encode_tbs)

Entry = namedtuple('IndexEntry', 'index start length depth parent '
        'first_child last_child title')
Data = namedtuple('Data', 'starts ends completes spans')

def collect_indexing_data(entries, number_of_text_records):
    ''' For every text record calculate which index entries start, end, span or
    are contained within that record.'''

    data = []
    for i in xrange(number_of_text_records):
        record_start, next_record_start = i*RECORD_SIZE, (i+1)*RECORD_SIZE
        datum = Data([], [], [], [])
        data.append(datum)

        for entry in entries:
            end = entry.start + entry.length - 1
            if (entry.start >= next_record_start or end < record_start):
                # This entry does not have any overlap with this record
                continue
            if (entry.start < record_start and end >= next_record_start):
                # This entry spans this record
                datum.spans.append(entry)
                continue
            if (entry.start >= record_start and end < next_record_start):
                # This entry is contained in this record
                datum.completes.append(entry)
            if (entry.start >= record_start and end >= next_record_start):
                # This entry starts in this record
                datum.starts.append(entry)
                continue
            if (entry.start < record_start and end < next_record_start):
                # This entry ends in this record
                datum.ends.append(entry)

        for x in datum:
            # Should be unnecessary as entries are already in this order, but
            # best to be safe.
            x.sort(key=lambda x:x.depth)

    return data

def generate_tbs_for_flat_index(indexing_data):
    ans = []
    record_type = 8 # 8 for KF8 0 for MOBI 6
    enc = partial(encode_tbs, flag_size=3)
    for datum in indexing_data:
        tbs = b''
        extra = {0b010 : record_type}
        if not (datum.starts or datum.ends or datum.completes or datum.spans):
            # No index entry touches this record
            pass
        elif datum.spans:
            extra[0b001] = 0
            tbs = enc(datum.spans[0].index, extra)
        else:
            starts, ends, completes = datum[:3]
            if (not completes and len(starts) + len(ends) == 1):
                # Either has the first or the last index, and no other indices.
                node = (starts+ends)[0]
                tbs = enc(node.index, extra)
            else:
                # This record contains the end of an index and
                # some complete index entries. Or it contains some complete
                # entries and a start. Or it contains an end, a start and
                # optionally some completes. In every case, we encode the first
                # entry to touch this record and the number of entries
                # that touch this record.
                nodes = starts + completes + ends
                nodes.sort(key=lambda x:x.index)
                extra[0b100] = len(nodes)
                tbs = enc(nodes[0].index, extra)
        ans.append(tbs)

    return ans

def apply_trailing_byte_sequences(index_table, records, number_of_text_records):
    entries = tuple(Entry(r['index'], r['offset'], r['length'], r['depth'],
        r.get('parent', None), r.get('first_child', None), r.get('last_child',
            None), r['label']) for r in index_table)

    indexing_data = collect_indexing_data(entries, number_of_text_records)
    max_depth = max(e['depth'] for e in index_table)
    if max_depth > 0:
        # TODO: Implement for hierarchical ToCs
        tbs = []
    else:
        tbs = generate_tbs_for_flat_index(indexing_data)
    if not tbs:
        return False
    for i, tbs_bytes in enumerate(tbs):
        records[i+1] += encode_trailing_data(tbs_bytes)
    return True


