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
from io import BytesIO

from calibre.ebooks.mobi.utils import CNCX, encint, align_block
from calibre.ebooks.mobi.writer8.header import Header

TagMeta_ = namedtuple('TagMeta',
        'name number values_per_entry bitmask end_flag')
TagMeta = lambda x:TagMeta_(*x)
EndTagTable = TagMeta(('eof', 0, 0, 0, 1))

# map of mask to number of shifts needed, works with 1 bit and two-bit wide masks
# could also be extended to 4 bit wide ones as well
mask_to_bit_shifts = { 1:0, 2:1, 3:0, 4:2, 8:3, 12:2, 16:4, 32:5, 48:4, 64:6,
        128:7, 192: 6 }

class IndexHeader(Header): # {{{

    HEADER_NAME = b'INDX'
    ALIGN_BLOCK = True
    HEADER_LENGTH = 192

    DEFINITION = '''
    # 4 - 8: Header Length
    header_length = {header_length}

    # 8 - 16: Unknown
    unknown1 = zeroes(8)

    # 16 - 20: Index type: 0 - normal 2 - inflection
    type = 2

    # 20 - 24: IDXT offset (filled in later)
    idxt_offset

    # 24 - 28: Number of index records
    num_of_records = 1

    # 28 - 32: Index encoding (65001 = utf-8)
    encoding = 65001

    # 32 - 36: Unknown
    unknown2 = NULL

    # 36 - 40: Number of Index entries
    num_of_entries = DYN

    # 40 - 44: ORDT offset
    ordt_offset

    # 44 - 48: LIGT offset
    ligt_offset

    # 48 - 52: Number of ORDT/LIGT? entries
    num_of_ordt_entries

    # 52 - 56: Number of CNCX records
    num_of_cncx = DYN

    # 56 - 180: Unknown
    unknown3 = zeroes(124)

    # 180 - 184: TAGX offset
    tagx_offset = {header_length}

    # 184 - 192: Unknown
    unknown4 = zeroes(8)

    # TAGX
    tagx = DYN

    # Last Index entry
    last_index = DYN

    # IDXT
    idxt = DYN
    '''.format(header_length=HEADER_LENGTH)

    POSITIONS = {'idxt_offset':'idxt'}
# }}}

class Index(object): # {{{

    control_byte_count = 1
    cncx = CNCX()
    tag_types = (EndTagTable,)

    HEADER_LENGTH = IndexHeader.HEADER_LENGTH

    @classmethod
    def generate_tagx(cls):
        header = b'TAGX'
        byts = bytearray()
        for tag_meta in cls.tag_types:
            byts.extend(tag_meta[1:])
        # table length, control byte count
        header += pack(b'>II', 12+len(byts), cls.control_byte_count)
        return header + bytes(byts)

    @classmethod
    def calculate_control_bytes_for_each_entry(cls, entries):
        control_bytes = []
        for lead_text, tags in entries:
            cbs = []
            ans = 0
            for (name, number, vpe, mask, endi) in cls.tag_types:
                if endi == 1:
                    cbs.append(ans)
                    ans = 0
                    continue
                try:
                    nvals = len(tags.get(name, ()))
                except TypeError:
                    nvals = 1
                nentries = nvals // vpe
                shifts = mask_to_bit_shifts[mask]
                ans |= mask & (nentries << shifts)
            if len(cbs) != cls.control_byte_count:
                raise ValueError('The entry %r is invalid'%[lead_text, tags])
            control_bytes.append(cbs)
        return control_bytes

    def __call__(self):
        self.control_bytes = self.calculate_control_bytes_for_each_entry(
                self.entries)

        rendered_entries = []
        index, idxt, buf = BytesIO(), BytesIO(), BytesIO()
        IndexEntry = namedtuple('IndexEntry', 'offset length raw')
        last_lead_text = b''
        too_large = ValueError('Index has too many entries, calibre does not'
                    ' support generating multiple index records at this'
                    ' time.')

        for i, x in enumerate(self.entries):
            control_bytes = self.control_bytes[i]
            leading_text, tags = x
            buf.seek(0), buf.truncate(0)
            leading_text = (leading_text.encode('utf-8') if
                    isinstance(leading_text, unicode) else leading_text)
            raw = bytearray(leading_text)
            raw.insert(0, len(leading_text))
            buf.write(bytes(raw))
            buf.write(bytes(bytearray(control_bytes)))
            for tag in self.tag_types:
                values = tags.get(tag.name, None)
                if values is None: continue
                try:
                    len(values)
                except TypeError:
                    values = [values]
                if values:
                    for val in values:
                        try:
                            buf.write(encint(val))
                        except ValueError:
                            raise ValueError('Invalid values for %r: %r'%(
                                tag, values))
            raw = buf.getvalue()
            offset = index.tell()
            if offset + self.HEADER_LENGTH >= 0x10000:
                raise too_large
            rendered_entries.append(IndexEntry(offset, len(raw), raw))
            idxt.write(pack(b'>H', self.HEADER_LENGTH+offset))
            index.write(raw)
            last_lead_text = leading_text

        index_block = align_block(index.getvalue())
        idxt_block = align_block(b'IDXT' + idxt.getvalue())
        body = index_block + idxt_block
        if len(body) + self.HEADER_LENGTH >= 0x10000:
            raise too_large
        header = b'INDX'
        buf.seek(0), buf.truncate(0)
        buf.write(pack(b'>I', self.HEADER_LENGTH))
        buf.write(b'\0'*4) # Unknown
        buf.write(pack(b'>I', 1)) # Header type? Or index record number?
        buf.write(b'\0'*4) # Unknown

        # IDXT block offset
        buf.write(pack(b'>I', self.HEADER_LENGTH + len(index_block)))

        # Number of index entries
        buf.write(pack(b'>I', len(rendered_entries)))

        buf.write(b'\xff'*8) # Unknown

        buf.write(b'\0'*156) # Unknown

        header += buf.getvalue()
        index_record = header + body

        tagx = self.generate_tagx()
        idxt = (b'IDXT' + pack(b'>H', IndexHeader.HEADER_LENGTH + len(tagx)) +
                b'\0')
        # Last index
        idx = bytes(bytearray([len(last_lead_text)])) + last_lead_text
        idx += pack(b'>H', len(rendered_entries))

        header = {
                'num_of_entries': len(rendered_entries),
                'num_of_cncx': len(self.cncx),
                'tagx':tagx,
                'last_index':align_block(idx),
                'idxt':idxt
        }
        header = IndexHeader()(**header)
        self.records = [header, index_record]
        self.records.extend(self.cncx.records)
        return self.records
# }}}

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
                    }) for c in chunk_table
        ]

class GuideIndex(Index):

    tag_types = tuple(map(TagMeta, (
        ('title',           1, 1, 1, 0),
        ('pos_fid',         6, 2, 2, 0),
        EndTagTable
    )))

    def __init__(self, guide_table):
        self.cncx = CNCX(c.title for c in guide_table)

        self.entries = [
                (r.type, {

                    'title':self.cncx[r.title],
                    'pos_fid':r.pos_fid,
                    }) for r in guide_table
        ]


class NCXIndex(Index):

    control_byte_count = 2
    tag_types = tuple(map(TagMeta, (
        ('offset',             1, 1, 1, 0),
        ('length',             2, 1, 2, 0),
        ('label',              3, 1, 4, 0),
        ('depth',              4, 1, 8, 0),
        ('parent',             21, 1, 16, 0),
        ('first_child',        22, 1, 32, 0),
        ('last_child',         23, 1, 64, 0),
        ('pos_fid',            6, 2, 128, 0),
        EndTagTable,
        ('image',              69, 1, 1, 0),
        ('description',        70, 1, 2, 0),
        ('author',             71, 1, 4, 0),
        ('caption',            72, 1, 8, 0),
        ('attribution',        73, 1, 16, 0),
        EndTagTable
    )))

    def __init__(self, toc_table):
        strings = []
        for entry in toc_table:
            strings.append(entry['label'])
            aut = entry.get('author', None)
            if aut:
                strings.append(aut)
            desc = entry.get('description', None)
            if desc:
                strings.append(desc)
        self.cncx = CNCX(strings)

        def to_entry(x):
            ans = {}
            for f in ('offset', 'length', 'depth', 'pos_fid', 'parent',
                    'first_child', 'last_child'):
                if f in x:
                    ans[f] = x[f]
            for f in ('label', 'description', 'author'):
                if f in x:
                    ans[f] = self.cncx[x[f]]
            return ('%02x'%x['index'], ans)

        self.entries = list(map(to_entry, toc_table))



