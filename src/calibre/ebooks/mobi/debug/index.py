#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct

from collections import OrderedDict, namedtuple

from calibre.ebooks.mobi.reader.headers import NULL_INDEX
from calibre.ebooks.mobi.reader.index import (CNCX, parse_indx_header,
        parse_tagx_section, parse_index_record, INDEX_HEADER_FIELDS)
from calibre.ebooks.mobi.reader.ncx import (tag_fieldname_map, default_entry)
from polyglot.builtins import iteritems, range

File = namedtuple('File',
    'file_number name divtbl_count start_position length')

Elem = namedtuple('Chunk',
    'insert_pos toc_text file_number sequence_number start_pos '
    'length')

GuideRef = namedtuple('GuideRef', 'type title pos_fid')

INDEX_HEADER_FIELDS = INDEX_HEADER_FIELDS + ('indices', 'tagx_block_size', 'tagx_block')
FIELD_NAMES = {'len':'Header length', 'type':'Unknown', 'gen':'Index Type (0 - normal, 2 - inflection)',
               'start':'IDXT Offset', 'count':'Number of entries in this record', 'code': 'character encoding', 'lng':'Unknown',
               'total':'Total number of actual Index Entries in all records', 'ordt': 'ORDT Offset', 'ligt':'LIGT Offset', 'nligt':'Number of LIGT',
               'ncncx':'Number of CNCX records', 'indices':'Geometry of index records'}


def read_variable_len_data(data, header):
    offset = header['tagx']
    indices = []
    idxt_offset = header['start']
    idxt_size = 4 + header['count'] * 2
    if offset > 0:
        tagx_block_size = header['tagx_block_size'] = struct.unpack_from(b'>I', data, offset + 4)[0]
        header['tagx_block'] = data[offset:offset+tagx_block_size]
        offset = idxt_offset + 4
        for i in range(header['count']):
            p = struct.unpack_from(b'>H', data, offset)[0]
            offset += 2
            strlen = bytearray(data[p])[0]
            text = data[p+1:p+1+strlen]
            p += 1 + strlen
            num = struct.unpack_from(b'>H', data, p)[0]
            indices.append((text, num))
    else:
        header['tagx_block'] = b''
        header['tagx_block_size'] = 0
    trailing_bytes = data[idxt_offset+idxt_size:]
    if trailing_bytes.rstrip(b'\0'):
        raise ValueError('Traling bytes after last IDXT entry: %r' % trailing_bytes.rstrip(b'\0'))
    header['indices'] = indices


def read_index(sections, idx, codec):
    table, cncx = OrderedDict(), CNCX([], codec)

    data = sections[idx].raw

    indx_header = parse_indx_header(data)
    indx_count = indx_header['count']

    if indx_header['ncncx'] > 0:
        off = idx + indx_count + 1
        cncx_records = [x.raw for x in sections[off:off+indx_header['ncncx']]]
        cncx = CNCX(cncx_records, codec)

    tag_section_start = indx_header['tagx']
    control_byte_count, tags = parse_tagx_section(data[tag_section_start:])

    read_variable_len_data(data, indx_header)
    index_headers = []

    for i in range(idx + 1, idx + 1 + indx_count):
        # Index record
        data = sections[i].raw
        index_headers.append(parse_index_record(table, data, control_byte_count, tags, codec,
                indx_header['ordt_map'], strict=True))
        read_variable_len_data(data, index_headers[-1])
    return table, cncx, indx_header, index_headers


class Index(object):

    def __init__(self, idx, records, codec):
        self.table = self.cncx = self.header = self.records = None
        self.index_headers = []
        if idx != NULL_INDEX:
            self.table, self.cncx, self.header, self.index_headers = read_index(records, idx, codec)

    def render(self):
        ans = ['*'*10 + ' Index Header ' + '*'*10]
        a = ans.append
        if self.header is not None:
            for field in INDEX_HEADER_FIELDS:
                a('%-12s: %r'%(FIELD_NAMES.get(field, field), self.header[field]))
        ans.extend(['', ''])
        ans += ['*'*10 + ' Index Record Headers (%d records) ' % len(self.index_headers) + '*'*10]
        for i, header in enumerate(self.index_headers):
            ans += ['*'*10 + ' Index Record %d ' % i + '*'*10]
            for field in INDEX_HEADER_FIELDS:
                a('%-12s: %r'%(FIELD_NAMES.get(field, field), header[field]))

        if self.cncx:
            a('*'*10 + ' CNCX ' + '*'*10)
            for offset, val in iteritems(self.cncx):
                a('%10s: %s'%(offset, val))
            ans.extend(['', ''])

        if self.table is not None:
            a('*'*10 + ' %d Index Entries '%len(self.table) + '*'*10)
            for k, v in iteritems(self.table):
                a('%s: %r'%(k, v))

        if self.records:
            ans.extend(['', '', '*'*10 + ' Parsed Entries ' + '*'*10])
            for f in self.records:
                a(repr(f))

        return ans + ['']

    def __str__(self):
        return '\n'.join(self.render())

    def __iter__(self):
        return iter(self.records)


class SKELIndex(Index):

    def __init__(self, skelidx, records, codec):
        super(SKELIndex, self).__init__(skelidx, records, codec)
        self.records = []

        if self.table is not None:
            for i, text in enumerate(self.table):
                tag_map = self.table[text]
                if set(tag_map) != {1, 6}:
                    raise ValueError('SKEL Index has unknown tags: %s'%
                            (set(tag_map)-{1,6}))
                self.records.append(File(
                    i,  # file_number
                    text,  # name
                    tag_map[1][0],  # divtbl_count
                    tag_map[6][0],  # start_pos
                    tag_map[6][1])  # length
                )


class SECTIndex(Index):

    def __init__(self, sectidx, records, codec):
        super(SECTIndex, self).__init__(sectidx, records, codec)
        self.records = []

        if self.table is not None:
            for i, text in enumerate(self.table):
                tag_map = self.table[text]
                if set(tag_map) != {2, 3, 4, 6}:
                    raise ValueError('Chunk Index has unknown tags: %s'%
                            (set(tag_map)-{2, 3, 4, 6}))

                toc_text = self.cncx[tag_map[2][0]]
                self.records.append(Elem(
                    int(text),  # insert_pos
                    toc_text,  # toc_text
                    tag_map[3][0],  # file_number
                    tag_map[4][0],  # sequence_number
                    tag_map[6][0],  # start_pos
                    tag_map[6][1]  # length
                    )
                )


class GuideIndex(Index):

    def __init__(self, guideidx, records, codec):
        super(GuideIndex, self).__init__(guideidx, records, codec)
        self.records = []

        if self.table is not None:
            for i, text in enumerate(self.table):
                tag_map = self.table[text]
                if set(tag_map) not in ({1, 6}, {1, 2, 3}):
                    raise ValueError('Guide Index has unknown tags: %s'%
                            tag_map)

                title = self.cncx[tag_map[1][0]]
                self.records.append(GuideRef(
                    text,
                    title,
                    tag_map[6] if 6 in tag_map else (tag_map[2], tag_map[3])
                    )
                )


class NCXIndex(Index):

    def __init__(self, ncxidx, records, codec):
        super(NCXIndex, self).__init__(ncxidx, records, codec)
        self.records = []

        if self.table is not None:
            NCXEntry = namedtuple('NCXEntry', 'index start length depth parent '
        'first_child last_child title pos_fid kind')

            for num, x in enumerate(iteritems(self.table)):
                text, tag_map = x
                entry = e = default_entry.copy()
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
                                entry[name] = self.cncx.get(fieldvalue,
                                        default_entry[name])

                def refindx(e, name):
                    ans = e[name]
                    if ans < 0:
                        ans = None
                    return ans

                entry = NCXEntry(start=e['pos'], index=e['num'],
                        length=e['len'], depth=e['hlvl'], parent=refindx(e,
                            'parent'), first_child=refindx(e, 'child1'),
                        last_child=refindx(e, 'childn'), title=e['text'],
                        pos_fid=e['pos_fid'], kind=e['kind'])
                self.records.append(entry)
