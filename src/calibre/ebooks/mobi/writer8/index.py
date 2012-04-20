#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import namedtuple
from struct import pack

from calibre.ebooks.mobi.utils import CNCX

TagMeta = namedtuple('TagMeta',
        'name number values_per_entry bitmask end_flag')
EndTagTable = TagMeta('eof', 0, 0, 0, 1)

class Index(object):

    control_byte_count = 1
    cncx = CNCX()
    tag_types = (EndTagTable,)

    @classmethod
    def generate_tagx(cls):
        header = b'TAGX'
        byts = bytearray()
        for tag_meta in cls.tag_types:
            byts.extend(tag_meta[1:])
        # table length, control byte count
        header += pack(b'>II', 12+len(byts), cls.control_byte_count)
        return header + bytes(byts)

class SkelIndex(Index):

    tag_types = tuple(map(TagMeta, (
        ('chunk_count', 1, 1, 3, 0),
        ('geometry',    6, 2, 12, 0),
        EndTagTable
    )))

    def __init__(self, skel_table):
        self.entries = [
                (s.name, {
                    # Dont ask me why these entries have to be repeated twice
                    'chunk_count':(s.chunk_count, s.chunk_count),
                    'geometry':(s.start_pos, s.length, s.start_pos, s.length),
                    }) for s in skel_table
        ]


class ChunkIndex(Index):

    tag_types = tuple(map(TagMeta, (
        ('cncx_offset',     2, 1, 1, 0),
        ('file_number',     3, 1, 2, 0),
        ('sequence_number', 4, 1, 4, 0),
        ('geometry',        6, 2, 8, 0),
        EndTagTable
    )))

    def __init__(self, chunk_table):
        self.cncx = CNCX(c.selector for c in chunk_table)

        self.entries = [
                ('%010d'%c.insert_pos, {

                    'cncx_offset':self.cncx[c.selector],
                    'file_number':c.file_number,
                    'sequence_number':c.sequence_number,
                    'geometry':(c.start_pos, c.length),
                    }) for s in chunk_table
        ]



