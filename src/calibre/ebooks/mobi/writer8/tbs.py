#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

DOC = '''
Trailing Byte Sequences contain information about which index entries touch a
particular text record. Every text records has a set of trailing byte
sequences. In order to figure out the sequence for a given text record, you
have to first calculate all the indices that start, end, span and are
contained within that text record. Then arrange the indices into 'strands',
where each strand is a hierarchical progression from the top level index down.
For the exact algorithm, see separate_strands(). The strands are then encoded
into 'sequences', see encode_strands_as_sequences() and finally the sequences
are turned into bytes.
'''
from collections import namedtuple, OrderedDict
from operator import attrgetter

from calibre.ebooks.mobi.utils import (encode_trailing_data,
        encode_tbs)
from polyglot.builtins import iteritems, itervalues

Entry = namedtuple('IndexEntry', 'index start length depth parent '
        'first_child last_child title action start_offset length_offset '
        'text_record_length')


def fill_entry(entry, start_offset, text_record_length):
    length_offset = start_offset + entry.length
    if start_offset < 0:
        action = 'spans' if length_offset > text_record_length else 'ends'
    else:
        action = 'starts' if length_offset > text_record_length else 'completes'

    return Entry(*(entry[:-4] + (action, start_offset, length_offset,
        text_record_length)))


def populate_strand(parent, entries):
    ans = [parent]
    children = [c for c in entries if c.parent == parent.index]
    if children:
        # Add first child to this strand, and recurse downwards
        child = children[0]
        entries.remove(child)
        ans += populate_strand(child, entries)
    else:
        # Add any entries at the same depth that form a contiguous set of
        # indices and belong to the same parent (these can all be
        # represented as a single sequence with the 0b100 flag)
        current_index = parent.index
        siblings = []
        for entry in list(entries):
            if (entry.depth == parent.depth and entry.parent == parent.parent and entry.index == current_index+1):
                current_index += 1
                entries.remove(entry)
                children = [c for c in entries if c.parent == entry.index]
                if children:
                    siblings += populate_strand(entry, entries)
                    break  # Cannot add more siblings, as we have added children
                else:
                    siblings.append(entry)
        ans += siblings
    return ans


def separate_strands(entries):
    ans = []
    while entries:
        top, entries = entries[0], entries[1:]
        strand = populate_strand(top, entries)
        layers = OrderedDict()
        for entry in strand:
            if entry.depth not in layers:
                layers[entry.depth] = []
            layers[entry.depth].append(entry)
        ans.append(layers)
    return ans


def collect_indexing_data(entries, text_record_lengths):
    ''' For every text record calculate which index entries start, end, span or
    are contained within that record. Arrange these entries in 'strands'. '''

    data = []
    entries = sorted(entries, key=attrgetter('start'))
    record_start = 0
    for rec_length in text_record_lengths:
        next_record_start = record_start + rec_length
        local_entries = []

        for entry in entries:
            if entry.start >= next_record_start:
                # No more entries overlap this record
                break
            if entry.start + entry.length <= record_start:
                # This entry does not touch this record
                continue
            local_entries.append(fill_entry(entry, entry.start - record_start,
                rec_length))

        strands = separate_strands(local_entries)
        data.append(strands)
        record_start += rec_length

    return data


class NegativeStrandIndex(Exception):
    pass


def encode_strands_as_sequences(strands, tbs_type=8):
    ''' Encode the list of strands for a single text record into a list of
    sequences, ready to be converted into TBS bytes.    '''
    ans = []
    last_index = None
    max_length_offset = 0
    first_entry = None
    for strand in strands:
        for entries in itervalues(strand):
            for entry in entries:
                if first_entry is None:
                    first_entry = entry
                if entry.length_offset > max_length_offset:
                    max_length_offset = entry.length_offset

    for strand in strands:
        strand_seqs = []
        for depth, entries in iteritems(strand):
            extra = {}
            if entries[-1].action == 'spans':
                extra[0b1] = 0
            elif False and (
                    entries[-1].length_offset < entries[-1].text_record_length and
                    entries[-1].action == 'completes' and
                    entries[-1].length_offset != max_length_offset):
                # I can't figure out exactly when kindlegen decides to insert
                # this, so disable it for now.
                extra[0b1] = entries[-1].length_offset

            if entries[0] is first_entry:
                extra[0b10] = tbs_type

            if len(entries) > 1:
                extra[0b100] = len(entries)

            index = entries[0].index - (entries[0].parent or 0)
            if ans and not strand_seqs:
                # We are in the second or later strands, so we need to use a
                # special flag and index value. The index value is the entry
                # index - the index of the last entry in the previous strand.
                index = last_index - entries[0].index
                if index < 0:
                    if tbs_type == 5:
                        index = -index
                    else:
                        raise NegativeStrandIndex()
                else:
                    extra[0b1000] = True
            last_index = entries[-1].index
            strand_seqs.append((index, extra))

        # Handle the case of consecutive action == 'spans' entries. In this
        # case, the 0b1 = 0 flag should be present only in the last consecutive
        # spans entry.
        for i, seq in enumerate(strand_seqs):
            if i + 1 < len(strand_seqs):
                if 0b1 in seq[1] and 0b1 in strand_seqs[i+1][1]:
                    del seq[1][0b1]
        ans.extend(strand_seqs)

    return ans


def sequences_to_bytes(sequences):
    ans = []
    flag_size = 3
    for val, extra in sequences:
        ans.append(encode_tbs(val, extra, flag_size))
        flag_size = 4  # only the first sequence has flag size 3 as all
        # subsequent sequences could need the 0b1000 flag
    return b''.join(ans)


def calculate_all_tbs(indexing_data, tbs_type=8):
    rmap = {}
    for i, strands in enumerate(indexing_data):
        sequences = encode_strands_as_sequences(strands, tbs_type=tbs_type)
        tbs_bytes = sequences_to_bytes(sequences)
        rmap[i+1] = tbs_bytes
    return rmap


def apply_trailing_byte_sequences(index_table, records, text_record_lengths):
    entries = tuple(Entry(r['index'], r['offset'], r['length'], r['depth'],
        r.get('parent', None), r.get('first_child', None), r.get('last_child',
            None), r['label'], None, None, None, None) for r in index_table)

    indexing_data = collect_indexing_data(entries, text_record_lengths)
    try:
        rmap = calculate_all_tbs(indexing_data)
    except NegativeStrandIndex:
        rmap = calculate_all_tbs(indexing_data, tbs_type=5)

    for i, tbs_bytes in iteritems(rmap):
        records[i] += encode_trailing_data(tbs_bytes)

    return True
