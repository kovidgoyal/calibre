#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import numbers
from struct import pack
import io
from collections import OrderedDict, defaultdict

from calibre.ebooks.mobi.utils import (encint, encode_number_as_hex,
        encode_tbs, align_block, RECORD_SIZE, CNCX as CNCX_)
from polyglot.builtins import iteritems, itervalues


class CNCX(CNCX_):  # {{{

    def __init__(self, toc, is_periodical):
        strings = []
        for item in toc.iterdescendants(breadth_first=True):
            strings.append(item.title)
            if is_periodical:
                strings.append(item.klass)
                if item.author:
                    strings.append(item.author)
                if item.description:
                    strings.append(item.description)
        CNCX_.__init__(self, strings)
# }}}


class TAGX:  # {{{

    BITMASKS = {11:0b1}
    BITMASKS.update({x:(1 << i) for i, x in enumerate([1, 2, 3, 4, 5, 21, 22, 23])})
    BITMASKS.update({x:(1 << i) for i, x in enumerate([69, 70, 71, 72, 73])})

    NUM_VALUES = defaultdict(lambda :1)
    NUM_VALUES[11] = 3
    NUM_VALUES[0] = 0

    def __init__(self):
        self.byts = bytearray()

    def add_tag(self, tag):
        buf = self.byts
        buf.append(tag)
        buf.append(self.NUM_VALUES[tag])
        # bitmask
        buf.append(self.BITMASKS[tag] if tag else 0)
        # eof
        buf.append(0 if tag else 1)

    def header(self, control_byte_count):
        header = b'TAGX'
        # table length, control byte count
        header += pack(b'>II', 12+len(self.byts), control_byte_count)
        return header

    @property
    def periodical(self):
        '''
        TAGX block for the Primary index header of a periodical
        '''
        for i in (1, 2, 3, 4, 5, 21, 22, 23, 0, 69, 70, 71, 72,73, 0):
            self.add_tag(i)
        return self.header(2) + bytes(self.byts)

    @property
    def secondary(self):
        '''
        TAGX block for the secondary index header of a periodical
        '''
        for i in (11, 0):
            self.add_tag(i)
        return self.header(1) + bytes(self.byts)

    @property
    def flat_book(self):
        '''
        TAGX block for the primary index header of a flat book
        '''
        for i in (1, 2, 3, 4, 0):
            self.add_tag(i)
        return self.header(1) + bytes(self.byts)


# }}}

# Index Entries {{{

class IndexEntry:

    TAG_VALUES = {
            'offset': 1,
            'size': 2,
            'label_offset': 3,
            'depth': 4,
            'class_offset': 5,
            'secondary': 11,
            'parent_index': 21,
            'first_child_index': 22,
            'last_child_index': 23,
            'image_index': 69,
            'desc_offset': 70,
            'author_offset': 71,

    }
    RTAG_MAP = {v:k for k, v in iteritems(TAG_VALUES)}  # noqa

    def __init__(self, offset, label_offset):
        self.offset, self.label_offset = offset, label_offset
        self.depth, self.class_offset = 0, None
        self.control_byte_count = 1

        self.length = 0
        self.index = 0

        self.parent_index = None
        self.first_child_index = None
        self.last_child_index = None

        self.image_index = None
        self.author_offset = None
        self.desc_offset = None

    def __repr__(self):
        return ('IndexEntry(offset=%r, depth=%r, length=%r, index=%r,'
                ' parent_index=%r)')%(self.offset, self.depth, self.length,
                        self.index, self.parent_index)

    @property
    def size(self):
        return self.length

    @size.setter
    def size(self, val):
        self.length = val

    @property
    def next_offset(self):
        return self.offset + self.length

    @property
    def tag_nums(self):
        yield from range(1, 5)
        for attr in ('class_offset', 'parent_index', 'first_child_index',
                'last_child_index'):
            if getattr(self, attr) is not None:
                yield self.TAG_VALUES[attr]

    @property
    def entry_type(self):
        ans = 0
        for tag in self.tag_nums:
            ans |= TAGX.BITMASKS[tag]
        return ans

    def attr_for_tag(self, tag):
        return self.RTAG_MAP[tag]

    @property
    def bytestring(self):
        buf = io.BytesIO()
        if isinstance(self.index, numbers.Integral):
            buf.write(encode_number_as_hex(self.index))
        else:
            raw = bytearray(self.index.encode('ascii'))
            raw.insert(0, len(raw))
            buf.write(bytes(raw))
        et = self.entry_type
        buf.write(bytes(bytearray([et])))

        if self.control_byte_count == 2:
            flags = 0
            for attr in ('image_index', 'desc_offset', 'author_offset'):
                val = getattr(self, attr)
                if val is not None:
                    tag = self.TAG_VALUES[attr]
                    bm = TAGX.BITMASKS[tag]
                    flags |= bm
            buf.write(bytes(bytearray([flags])))

        for tag in self.tag_nums:
            attr = self.attr_for_tag(tag)
            val = getattr(self, attr)
            if isinstance(val, numbers.Integral):
                val = [val]
            for x in val:
                buf.write(encint(x))

        if self.control_byte_count == 2:
            for attr in ('image_index', 'desc_offset', 'author_offset'):
                val = getattr(self, attr)
                if val is not None:
                    buf.write(encint(val))

        ans = buf.getvalue()
        return ans


class PeriodicalIndexEntry(IndexEntry):

    def __init__(self, offset, label_offset, class_offset, depth):
        IndexEntry.__init__(self, offset, label_offset)
        self.depth = depth
        self.class_offset = class_offset
        self.control_byte_count = 2


class SecondaryIndexEntry(IndexEntry):

    INDEX_MAP = {'author':73, 'caption':72, 'credit':71, 'description':70,
                'mastheadImage':69}

    def __init__(self, index):
        IndexEntry.__init__(self, 0, 0)
        self.index = index

        tag = self.INDEX_MAP[index]

        # The values for this index entry
        # I dont know what the 5 means, it is not the number of entries
        self.secondary = [5 if tag == min(
            itervalues(self.INDEX_MAP)) else 0, 0, tag]

    @property
    def tag_nums(self):
        yield 11

    @property
    def entry_type(self):
        return 1

    @classmethod
    def entries(cls):
        rmap = {v:k for k,v in iteritems(cls.INDEX_MAP)}
        for tag in sorted(rmap, reverse=True):
            yield cls(rmap[tag])

# }}}


class TBS:  # {{{

    '''
    Take the list of index nodes starting/ending on a record and calculate the
    trailing byte sequence for the record.
    '''

    def __init__(self, data, is_periodical, first=False, section_map={},
            after_first=False):
        self.section_map = section_map

        if is_periodical:
            # The starting bytes.
            # The value is zero which I think indicates the periodical
            # index entry. The values for the various flags seem to be
            # unused. If the 0b100 is present, it means that the record
            # deals with section 1 (or is the final record with section
            # transitions).
            self.type_010 = encode_tbs(0, {0b010: 0}, flag_size=3)
            self.type_011 = encode_tbs(0, {0b010: 0, 0b001: 0},
                    flag_size=3)
            self.type_110 = encode_tbs(0, {0b100: 2, 0b010: 0},
                    flag_size=3)
            self.type_111 = encode_tbs(0, {0b100: 2, 0b010: 0, 0b001:
                0}, flag_size=3)

            if not data:
                byts = b''
                if after_first:
                    # This can happen if a record contains only text between
                    # the periodical start and the first section
                    byts = self.type_011
                self.bytestring = byts
            else:
                depth_map = defaultdict(list)
                for x in ('starts', 'ends', 'completes'):
                    for idx in data[x]:
                        depth_map[idx.depth].append(idx)
                for l in itervalues(depth_map):
                    l.sort(key=lambda x:x.offset)
                self.periodical_tbs(data, first, depth_map)
        else:
            if not data:
                self.bytestring = b''
            else:
                self.book_tbs(data, first)

    def periodical_tbs(self, data, first, depth_map):
        buf = io.BytesIO()

        has_section_start = (depth_map[1] and
                set(depth_map[1]).intersection(set(data['starts'])))
        spanner = data['spans']
        parent_section_index = -1

        if depth_map[0]:
            # We have a terminal record

            # Find the first non periodical node
            first_node = None
            for nodes in (depth_map[1], depth_map[2]):
                for node in nodes:
                    if (first_node is None or (node.offset, node.depth) <
                            (first_node.offset, first_node.depth)):
                        first_node = node

            typ = (self.type_110 if has_section_start else self.type_010)

            # parent_section_index is needed for the last record
            if first_node is not None and first_node.depth > 0:
                parent_section_index = (first_node.index if first_node.depth == 1 else first_node.parent_index)
            else:
                parent_section_index = max(iter(self.section_map))

        else:
            # Non terminal record

            if spanner is not None:
                # record is spanned by a single article
                parent_section_index = spanner.parent_index
                typ = (self.type_110 if parent_section_index == 1 else
                        self.type_010)
            elif not depth_map[1]:
                # has only article nodes, i.e. spanned by a section
                parent_section_index = depth_map[2][0].parent_index
                typ = (self.type_111 if parent_section_index == 1 else
                        self.type_010)
            else:
                # has section transitions
                if depth_map[2]:
                    parent_section_index = depth_map[2][0].parent_index
                else:
                    parent_section_index = depth_map[1][0].index
                typ = self.type_011

        buf.write(typ)

        if typ not in (self.type_110, self.type_111) and parent_section_index > 0:
            extra = {}
            # Write starting section information
            if spanner is None:
                num_articles = len([a for a in depth_map[1] if a.parent_index == parent_section_index])
                if not depth_map[1]:
                    extra = {0b0001: 0}
                if num_articles > 1:
                    extra = {0b0100: num_articles}
            buf.write(encode_tbs(parent_section_index, extra))

        if spanner is None:
            articles = depth_map[2]
            sections = {self.section_map[a.parent_index] for a in
                articles}
            sections = sorted(sections, key=lambda x:x.offset)
            section_map = {s:[a for a in articles if a.parent_index ==
                s.index] for s in sections}
            for i, section in enumerate(sections):
                # All the articles in this record that belong to section
                articles = section_map[section]
                first_article = articles[0]
                last_article = articles[-1]
                num = len(articles)
                last_article_ends = (last_article in data['ends'] or
                        last_article in data['completes'])

                try:
                    next_sec = sections[i+1]
                except:
                    next_sec = None

                extra = {}
                if num > 1:
                    extra[0b0100] = num
                if False and i == 0 and next_sec is not None:
                    # Write offset to next section from start of record
                    # I can't figure out exactly when Kindlegen decides to
                    # write this so I have disabled it for now.
                    extra[0b0001] = next_sec.offset - data['offset']

                buf.write(encode_tbs(first_article.index-section.index, extra))

                if next_sec is not None:
                    buf.write(encode_tbs(last_article.index-next_sec.index,
                        {0b1000: 0}))

                # If a section TOC starts and extends into the next record add
                # a trailing vwi. We detect this by TBS type==3, processing last
                # section present in the record, and the last article in that
                # section either ends or completes and doesn't finish
                # on the last byte of the record.
                elif (typ == self.type_011 and last_article_ends and
                      ((last_article.offset+last_article.size) % RECORD_SIZE > 0)
                     ):
                    buf.write(encode_tbs(last_article.index-section.index-1,
                        {0b1000: 0}))

        else:
            buf.write(encode_tbs(spanner.index - parent_section_index,
                {0b0001: 0}))

        self.bytestring = buf.getvalue()

    def book_tbs(self, data, first):
        spanner = data['spans']
        if spanner is not None:
            self.bytestring = encode_tbs(spanner.index, {0b010: 0, 0b001: 0},
                    flag_size=3)
        else:
            starts, completes, ends = (data['starts'], data['completes'],
                                        data['ends'])
            if (not completes and (
                (len(starts) == 1 and not ends) or (len(ends) == 1 and not
                    starts))):
                node = starts[0] if starts else ends[0]
                self.bytestring = encode_tbs(node.index, {0b010: 0}, flag_size=3)
            else:
                nodes = []
                for x in (starts, completes, ends):
                    nodes.extend(x)
                nodes.sort(key=lambda x:x.index)
                self.bytestring = encode_tbs(nodes[0].index, {0b010:0,
                    0b100: len(nodes)}, flag_size=3)

# }}}


class Indexer:  # {{{

    def __init__(self, serializer, number_of_text_records,
            size_of_last_text_record, masthead_offset, is_periodical,
            opts, oeb):
        self.serializer = serializer
        self.number_of_text_records = number_of_text_records
        self.text_size = (RECORD_SIZE * (self.number_of_text_records-1) +
                            size_of_last_text_record)
        self.masthead_offset = masthead_offset
        self.secondary_record_offset = None

        self.oeb = oeb
        self.log = oeb.log
        self.opts = opts

        self.is_periodical = is_periodical
        if self.is_periodical and self.masthead_offset is None:
            raise ValueError('Periodicals must have a masthead')

        self.log('Generating MOBI index for a %s'%('periodical' if
            self.is_periodical else 'book'))
        self.is_flat_periodical = False
        if self.is_periodical:
            periodical_node = next(iter(oeb.toc))
            sections = tuple(periodical_node)
            self.is_flat_periodical = len(sections) == 1

        self.records = []

        if self.is_periodical:
            # Ensure all articles have an author and description before
            # creating the CNCX
            for node in oeb.toc.iterdescendants():
                if node.klass == 'article':
                    aut, desc = node.author, node.description
                    if not aut:
                        aut = _('Unknown')
                    if not desc:
                        desc = _('No details available')
                    node.author, node.description = aut, desc

        self.cncx = CNCX(oeb.toc, self.is_periodical)

        if self.is_periodical:
            self.indices = self.create_periodical_index()
        else:
            self.indices = self.create_book_index()

        if not self.indices:
            raise ValueError('No valid entries in TOC, cannot generate index')

        self.records.append(self.create_index_record())
        self.records.insert(0, self.create_header())
        self.records.extend(self.cncx.records)

        if is_periodical:
            self.secondary_record_offset = len(self.records)
            self.records.append(self.create_header(secondary=True))
            self.records.append(self.create_index_record(secondary=True))

        self.calculate_trailing_byte_sequences()

    def create_index_record(self, secondary=False):  # {{{
        header_length = 192
        buf = io.BytesIO()
        indices = list(SecondaryIndexEntry.entries()) if secondary else self.indices

        # Write index entries
        offsets = []
        for i in indices:
            offsets.append(buf.tell())
            buf.write(i.bytestring)

        index_block = align_block(buf.getvalue())

        # Write offsets to index entries as an IDXT block
        idxt_block = b'IDXT'
        buf.seek(0), buf.truncate(0)
        for offset in offsets:
            buf.write(pack(b'>H', header_length+offset))
        idxt_block = align_block(idxt_block + buf.getvalue())
        body = index_block + idxt_block

        header = b'INDX'
        buf.seek(0), buf.truncate(0)
        buf.write(pack(b'>I', header_length))
        buf.write(b'\0'*4)  # Unknown
        buf.write(pack(b'>I', 1))  # Header type? Or index record number?
        buf.write(b'\0'*4)  # Unknown
        # IDXT block offset
        buf.write(pack(b'>I', header_length + len(index_block)))
        # Number of index entries
        buf.write(pack(b'>I', len(offsets)))
        # Unknown
        buf.write(b'\xff'*8)
        # Unknown
        buf.write(b'\0'*156)

        header += buf.getvalue()

        ans = header + body
        if len(ans) > 0x10000:
            raise ValueError('Too many entries (%d) in the TOC'%len(offsets))
        return ans
    # }}}

    def create_header(self, secondary=False):  # {{{
        buf = io.BytesIO()
        if secondary:
            tagx_block = TAGX().secondary
        else:
            tagx_block = (TAGX().periodical if self.is_periodical else
                                TAGX().flat_book)
        header_length = 192

        # Ident 0 - 4
        buf.write(b'INDX')

        # Header length 4 - 8
        buf.write(pack(b'>I', header_length))

        # Unknown 8-16
        buf.write(b'\0'*8)

        # Index type: 0 - normal, 2 - inflection 16 - 20
        buf.write(pack(b'>I', 2))

        # IDXT offset 20-24
        buf.write(pack(b'>I', 0))  # Filled in later

        # Number of index records 24-28
        buf.write(pack(b'>I', 1 if secondary else len(self.records)))

        # Index Encoding 28-32
        buf.write(pack(b'>I', 65001))  # utf-8

        # Unknown 32-36
        buf.write(b'\xff'*4)

        # Number of index entries 36-40
        indices = list(SecondaryIndexEntry.entries()) if secondary else self.indices
        buf.write(pack(b'>I', len(indices)))

        # ORDT offset 40-44
        buf.write(pack(b'>I', 0))

        # LIGT offset 44-48
        buf.write(pack(b'>I', 0))

        # Number of LIGT entries 48-52
        buf.write(pack(b'>I', 0))

        # Number of CNCX records 52-56
        buf.write(pack(b'>I', 0 if secondary else len(self.cncx.records)))

        # Unknown 56-180
        buf.write(b'\0'*124)

        # TAGX offset 180-184
        buf.write(pack(b'>I', header_length))

        # Unknown 184-192
        buf.write(b'\0'*8)

        # TAGX block
        buf.write(tagx_block)

        num = len(indices)

        # The index of the last entry in the NCX
        idx = indices[-1].index
        if isinstance(idx, numbers.Integral):
            idx = encode_number_as_hex(idx)
        else:
            idx = idx.encode('ascii')
            idx = (bytes(bytearray([len(idx)]))) + idx
        buf.write(idx)

        # The number of entries in the NCX
        buf.write(pack(b'>H', num))

        # Padding
        pad = (4 - (buf.tell()%4))%4
        if pad:
            buf.write(b'\0'*pad)

        idxt_offset = buf.tell()

        buf.write(b'IDXT')
        buf.write(pack(b'>H', header_length + len(tagx_block)))
        buf.write(b'\0')
        buf.seek(20)
        buf.write(pack(b'>I', idxt_offset))

        return align_block(buf.getvalue())
    # }}}

    def create_book_index(self):  # {{{
        indices = []
        seen = set()
        id_offsets = self.serializer.id_offsets

        # Flatten toc so that chapter to chapter jumps work with all sub
        # chapter levels as well
        for node in self.oeb.toc.iterdescendants():
            try:
                offset = id_offsets[node.href]
                label = self.cncx[node.title]
            except:
                self.log.warn('TOC item %s [%s] not found in document'%(
                    node.title, node.href))
                continue

            if offset in seen:
                continue
            seen.add(offset)

            indices.append(IndexEntry(offset, label))

        indices.sort(key=lambda x:x.offset)

        # Set lengths
        for i, index in enumerate(indices):
            try:
                next_offset = indices[i+1].offset
            except:
                next_offset = self.serializer.body_end_offset
            index.length = next_offset - index.offset

        # Remove empty indices
        indices = [x for x in indices if x.length > 0]

        # Reset lengths in case any were removed
        for i, index in enumerate(indices):
            try:
                next_offset = indices[i+1].offset
            except:
                next_offset = self.serializer.body_end_offset
            index.length = next_offset - index.offset

        # Set index values
        for index, x in enumerate(indices):
            x.index = index

        return indices

    # }}}

    def create_periodical_index(self):  # {{{
        periodical_node = next(iter(self.oeb.toc))
        periodical_node_offset = self.serializer.body_start_offset
        periodical_node_size = (self.serializer.body_end_offset -
                periodical_node_offset)

        normalized_sections = []

        id_offsets = self.serializer.id_offsets

        periodical = PeriodicalIndexEntry(periodical_node_offset,
                self.cncx[periodical_node.title],
                self.cncx[periodical_node.klass], 0)
        periodical.length = periodical_node_size
        periodical.first_child_index = 1
        periodical.image_index = self.masthead_offset

        seen_sec_offsets = set()
        seen_art_offsets = set()

        for sec in periodical_node:
            normalized_articles = []
            try:
                offset = id_offsets[sec.href]
                label = self.cncx[sec.title]
                klass = self.cncx[sec.klass]
            except:
                continue
            if offset in seen_sec_offsets:
                continue

            seen_sec_offsets.add(offset)
            section = PeriodicalIndexEntry(offset, label, klass, 1)
            section.parent_index = 0

            for art in sec:
                try:
                    offset = id_offsets[art.href]
                    label = self.cncx[art.title]
                    klass = self.cncx[art.klass]
                except:
                    continue
                if offset in seen_art_offsets:
                    continue
                seen_art_offsets.add(offset)
                article = PeriodicalIndexEntry(offset, label, klass, 2)
                normalized_articles.append(article)
                article.author_offset = self.cncx[art.author]
                article.desc_offset = self.cncx[art.description]
                if getattr(art, 'toc_thumbnail', None) is not None:
                    try:
                        ii = self.serializer.images[art.toc_thumbnail] - 1
                        if ii > -1:
                            article.image_index = ii
                    except KeyError:
                        pass  # Image not found in serializer

            if normalized_articles:
                normalized_articles.sort(key=lambda x:x.offset)
                normalized_sections.append((section, normalized_articles))

        normalized_sections.sort(key=lambda x:x[0].offset)

        # Set lengths
        for s, x in enumerate(normalized_sections):
            sec, normalized_articles = x
            try:
                sec.length = normalized_sections[s+1][0].offset - sec.offset
            except:
                sec.length = self.serializer.body_end_offset - sec.offset
            for i, art in enumerate(normalized_articles):
                try:
                    art.length = normalized_articles[i+1].offset - art.offset
                except:
                    art.length = sec.offset + sec.length - art.offset

        # Filter
        for i, x in list(enumerate(normalized_sections)):
            sec, normalized_articles = x
            normalized_articles = list(filter(lambda x: x.length > 0,
                normalized_articles))
            normalized_sections[i] = (sec, normalized_articles)

        normalized_sections = list(filter(lambda x: x[0].length > 0 and x[1],
            normalized_sections))

        # Set indices
        i = 0
        for sec, articles in normalized_sections:
            i += 1
            sec.index = i
            sec.parent_index = 0

        for sec, articles in normalized_sections:
            for art in articles:
                i += 1
                art.index = i

                art.parent_index = sec.index

        for sec, normalized_articles in normalized_sections:
            sec.first_child_index = normalized_articles[0].index
            sec.last_child_index = normalized_articles[-1].index

        # Set lengths again to close up any gaps left by filtering
        for s, x in enumerate(normalized_sections):
            sec, articles = x
            try:
                next_offset = normalized_sections[s+1][0].offset
            except:
                next_offset = self.serializer.body_end_offset
            sec.length = next_offset - sec.offset

            for a, art in enumerate(articles):
                try:
                    next_offset = articles[a+1].offset
                except:
                    next_offset = sec.next_offset
                art.length = next_offset - art.offset

        # Sanity check
        for s, x in enumerate(normalized_sections):
            sec, articles = x
            try:
                next_sec = normalized_sections[s+1][0]
            except:
                if (sec.length == 0 or sec.next_offset !=
                        self.serializer.body_end_offset):
                    raise ValueError('Invalid section layout')
            else:
                if next_sec.offset != sec.next_offset or sec.length == 0:
                    raise ValueError('Invalid section layout')
            for a, art in enumerate(articles):
                try:
                    next_art = articles[a+1]
                except:
                    if (art.length == 0 or art.next_offset !=
                            sec.next_offset):
                        raise ValueError('Invalid article layout')
                else:
                    if art.length == 0 or art.next_offset != next_art.offset:
                        raise ValueError('Invalid article layout')

        # Flatten
        indices = [periodical]
        for sec, articles in normalized_sections:
            indices.append(sec)
            periodical.last_child_index = sec.index

        for sec, articles in normalized_sections:
            for a in articles:
                indices.append(a)

        return indices
    # }}}

    # TBS {{{
    def calculate_trailing_byte_sequences(self):
        self.tbs_map = {}
        found_node = False
        sections = [i for i in self.indices if i.depth == 1]
        section_map = OrderedDict((i.index, i) for i in
                sorted(sections, key=lambda x:x.offset))

        deepest = max(i.depth for i in self.indices)

        for i in range(self.number_of_text_records):
            offset = i * RECORD_SIZE
            next_offset = offset + RECORD_SIZE
            data = {'ends':[], 'completes':[], 'starts':[],
                    'spans':None, 'offset':offset, 'record_number':i+1}

            for index in self.indices:

                if index.offset >= next_offset:
                    # Node starts after current record
                    if index.depth == deepest:
                        break
                    else:
                        continue
                if index.next_offset <= offset:
                    # Node ends before current record
                    continue
                if index.offset >= offset:
                    # Node starts in current record
                    if index.next_offset <= next_offset:
                        # Node ends in current record
                        data['completes'].append(index)
                    else:
                        data['starts'].append(index)
                else:
                    # Node starts before current records
                    if index.next_offset <= next_offset:
                        # Node ends in current record
                        data['ends'].append(index)
                    elif index.depth == deepest:
                        data['spans'] = index

            if (data['ends'] or data['completes'] or data['starts'] or
                    data['spans'] is not None):
                self.tbs_map[i+1] = TBS(data, self.is_periodical, first=not
                        found_node, section_map=section_map)
                found_node = True
            else:
                self.tbs_map[i+1] = TBS({}, self.is_periodical, first=False,
                        after_first=found_node, section_map=section_map)

    def get_trailing_byte_sequence(self, num):
        return self.tbs_map[num].bytestring
    # }}}

# }}}
