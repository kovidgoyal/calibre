#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct, sys, os
from collections import OrderedDict, defaultdict

from lxml import html

from calibre.ebooks.mobi.reader.headers import NULL_INDEX
from calibre.ebooks.mobi.reader.index import (parse_index_record,
        parse_tagx_section)
from calibre.ebooks.mobi.utils import (decode_hex_number, decint,
        decode_tbs, read_font_record)
from calibre.utils.imghdr import what
from calibre.ebooks.mobi.debug import format_bytes
from calibre.ebooks.mobi.debug.headers import TextRecord
from polyglot.builtins import iteritems, as_bytes, print_to_binary_file


class TagX:  # {{{

    def __init__(self, tag, num_values, bitmask, eof):
        self.tag, self.num_values, self.bitmask, self.eof = (tag, num_values,
                bitmask, eof)
        self.num_of_values = num_values
        self.is_eof = (self.eof == 1 and self.tag == 0 and self.num_values == 0 and self.bitmask == 0)

    def __repr__(self):
        return 'TAGX(tag=%02d, num_values=%d, bitmask=%r, eof=%d)' % (self.tag,
                self.num_values, bin(self.bitmask), self.eof)
    # }}}


class SecondaryIndexHeader:  # {{{

    def __init__(self, record):
        self.record = record
        raw = self.record.raw
        # open('/t/index_header.bin', 'wb').write(raw)
        if raw[:4] != b'INDX':
            raise ValueError('Invalid Secondary Index Record')
        self.header_length, = struct.unpack('>I', raw[4:8])
        self.unknown1 = raw[8:16]
        self.index_type, = struct.unpack('>I', raw[16:20])
        self.index_type_desc = {0: 'normal', 2:
                'inflection', 6: 'calibre'}.get(self.index_type, 'unknown')
        self.idxt_start, = struct.unpack('>I', raw[20:24])
        self.index_count, = struct.unpack('>I', raw[24:28])
        self.index_encoding_num, = struct.unpack('>I', raw[28:32])
        self.index_encoding = {65001: 'utf-8', 1252:
                'cp1252'}.get(self.index_encoding_num, 'unknown')
        if self.index_encoding == 'unknown':
            raise ValueError(
                'Unknown index encoding: %d'%self.index_encoding_num)
        self.unknown2 = raw[32:36]
        self.num_index_entries, = struct.unpack('>I', raw[36:40])
        self.ordt_start, = struct.unpack('>I', raw[40:44])
        self.ligt_start, = struct.unpack('>I', raw[44:48])
        self.num_of_ligt_entries, = struct.unpack('>I', raw[48:52])
        self.num_of_cncx_blocks, = struct.unpack('>I', raw[52:56])
        self.unknown3 = raw[56:180]
        self.tagx_offset, = struct.unpack(b'>I', raw[180:184])
        if self.tagx_offset != self.header_length:
            raise ValueError('TAGX offset and header length disagree')
        self.unknown4 = raw[184:self.header_length]

        tagx = raw[self.header_length:]
        if not tagx.startswith(b'TAGX'):
            raise ValueError('Invalid TAGX section')
        self.tagx_header_length, = struct.unpack('>I', tagx[4:8])
        self.tagx_control_byte_count, = struct.unpack('>I', tagx[8:12])
        self.tagx_entries = [TagX(*x) for x in parse_tagx_section(tagx)[1]]
        if self.tagx_entries and not self.tagx_entries[-1].is_eof:
            raise ValueError('TAGX last entry is not EOF')

        idxt0_pos = self.header_length+self.tagx_header_length
        num = ord(raw[idxt0_pos:idxt0_pos+1])
        count_pos = idxt0_pos+1+num
        self.last_entry = raw[idxt0_pos+1:count_pos]
        self.ncx_count, = struct.unpack(b'>H', raw[count_pos:count_pos+2])

        # There may be some alignment zero bytes between the end of the idxt0
        # and self.idxt_start
        idxt = raw[self.idxt_start:]
        if idxt[:4] != b'IDXT':
            raise ValueError('Invalid IDXT header')
        length_check, = struct.unpack(b'>H', idxt[4:6])
        if length_check != self.header_length + self.tagx_header_length:
            raise ValueError('Length check failed')
        if idxt[6:].replace(b'\0', b''):
            raise ValueError('Non null trailing bytes after IDXT')

    def __str__(self):
        ans = ['*'*20 + ' Secondary Index Header '+ '*'*20]
        a = ans.append

        def u(w):
            a('Unknown: %r (%d bytes) (All zeros: %r)'%(w,
                len(w), not bool(w.replace(b'\0', b''))))

        a('Header length: %d'%self.header_length)
        u(self.unknown1)
        a('Index Type: %s (%d)'%(self.index_type_desc, self.index_type))
        a('Offset to IDXT start: %d'%self.idxt_start)
        a('Number of index records: %d'%self.index_count)
        a('Index encoding: %s (%d)'%(self.index_encoding,
                self.index_encoding_num))
        u(self.unknown2)
        a('Number of index entries: %d'% self.num_index_entries)
        a('ORDT start: %d'%self.ordt_start)
        a('LIGT start: %d'%self.ligt_start)
        a('Number of LIGT entries: %d'%self.num_of_ligt_entries)
        a('Number of cncx blocks: %d'%self.num_of_cncx_blocks)
        u(self.unknown3)
        a('TAGX offset: %d'%self.tagx_offset)
        u(self.unknown4)
        a('\n\n')
        a('*'*20 + ' TAGX Header (%d bytes)'%self.tagx_header_length+ '*'*20)
        a('Header length: %d'%self.tagx_header_length)
        a('Control byte count: %d'%self.tagx_control_byte_count)
        for i in self.tagx_entries:
            a('\t' + repr(i))
        a('Index of last IndexEntry in secondary index record: %s'% self.last_entry)
        a('Number of entries in the NCX: %d'% self.ncx_count)

        return '\n'.join(ans)

# }}}


class IndexHeader:  # {{{

    def __init__(self, record):
        self.record = record
        raw = self.record.raw
        # open('/t/index_header.bin', 'wb').write(raw)
        if raw[:4] != b'INDX':
            raise ValueError('Invalid Primary Index Record')

        self.header_length, = struct.unpack('>I', raw[4:8])
        self.unknown1 = raw[8:12]
        self.header_type, = struct.unpack('>I', raw[12:16])
        self.index_type, = struct.unpack('>I', raw[16:20])
        self.index_type_desc = {0: 'normal', 2:
                'inflection', 6: 'calibre'}.get(self.index_type, 'unknown')
        self.idxt_start, = struct.unpack('>I', raw[20:24])
        self.index_count, = struct.unpack('>I', raw[24:28])
        self.index_encoding_num, = struct.unpack('>I', raw[28:32])
        self.index_encoding = {65001: 'utf-8', 1252:
                'cp1252'}.get(self.index_encoding_num, 'unknown')
        if self.index_encoding == 'unknown':
            raise ValueError(
                'Unknown index encoding: %d'%self.index_encoding_num)
        self.possibly_language = raw[32:36]
        self.num_index_entries, = struct.unpack('>I', raw[36:40])
        self.ordt_start, = struct.unpack('>I', raw[40:44])
        self.ligt_start, = struct.unpack('>I', raw[44:48])
        self.num_of_ligt_entries, = struct.unpack('>I', raw[48:52])
        self.num_of_cncx_blocks, = struct.unpack('>I', raw[52:56])
        self.unknown2 = raw[56:180]
        self.tagx_offset, = struct.unpack(b'>I', raw[180:184])
        if self.tagx_offset != self.header_length:
            raise ValueError('TAGX offset and header length disagree')
        self.unknown3 = raw[184:self.header_length]

        tagx = raw[self.header_length:]
        if not tagx.startswith(b'TAGX'):
            raise ValueError('Invalid TAGX section')
        self.tagx_header_length, = struct.unpack('>I', tagx[4:8])
        self.tagx_control_byte_count, = struct.unpack('>I', tagx[8:12])
        self.tagx_entries = [TagX(*x) for x in parse_tagx_section(tagx)[1]]
        if self.tagx_entries and not self.tagx_entries[-1].is_eof:
            raise ValueError('TAGX last entry is not EOF')

        idxt0_pos = self.header_length+self.tagx_header_length
        last_num, consumed = decode_hex_number(raw[idxt0_pos:])
        count_pos = idxt0_pos + consumed
        self.ncx_count, = struct.unpack(b'>H', raw[count_pos:count_pos+2])
        self.last_entry = last_num

        if last_num != self.ncx_count - 1:
            raise ValueError('Last id number in the NCX != NCX count - 1')
        # There may be some alignment zero bytes between the end of the idxt0
        # and self.idxt_start

        idxt = raw[self.idxt_start:]
        if idxt[:4] != b'IDXT':
            raise ValueError('Invalid IDXT header')
        length_check, = struct.unpack(b'>H', idxt[4:6])
        if length_check != self.header_length + self.tagx_header_length:
            raise ValueError('Length check failed')
        # if idxt[6:].replace(b'\0', b''):
        #     raise ValueError('Non null trailing bytes after IDXT')

    def __str__(self):
        ans = ['*'*20 + ' Index Header (%d bytes)'%len(self.record.raw)+ '*'*20]
        a = ans.append

        def u(w):
            a('Unknown: %r (%d bytes) (All zeros: %r)'%(w,
                len(w), not bool(w.replace(b'\0', b''))))

        a('Header length: %d'%self.header_length)
        u(self.unknown1)
        a('Header type: %d'%self.header_type)
        a('Index Type: %s (%d)'%(self.index_type_desc, self.index_type))
        a('Offset to IDXT start: %d'%self.idxt_start)
        a('Number of index records: %d'%self.index_count)
        a('Index encoding: %s (%d)'%(self.index_encoding,
                self.index_encoding_num))
        a('Unknown (possibly language?): %r'%(self.possibly_language))
        a('Number of index entries: %d'% self.num_index_entries)
        a('ORDT start: %d'%self.ordt_start)
        a('LIGT start: %d'%self.ligt_start)
        a('Number of LIGT entries: %d'%self.num_of_ligt_entries)
        a('Number of cncx blocks: %d'%self.num_of_cncx_blocks)
        u(self.unknown2)
        a('TAGX offset: %d'%self.tagx_offset)
        u(self.unknown3)
        a('\n\n')
        a('*'*20 + ' TAGX Header (%d bytes)'%self.tagx_header_length+ '*'*20)
        a('Header length: %d'%self.tagx_header_length)
        a('Control byte count: %d'%self.tagx_control_byte_count)
        for i in self.tagx_entries:
            a('\t' + repr(i))
        a('Index of last IndexEntry in primary index record: %s'% self.last_entry)
        a('Number of entries in the NCX: %d'% self.ncx_count)

        return '\n'.join(ans)
    # }}}


class Tag:  # {{{

    '''
    Index entries are a collection of tags. Each tag is represented by this
    class.
    '''

    TAG_MAP = {
            1: ('offset', 'Offset in HTML'),
            2: ('size', 'Size in HTML'),
            3: ('label_offset', 'Label offset in CNCX'),
            4: ('depth', 'Depth of this entry in TOC'),
            5: ('class_offset', 'Class offset in CNCX'),
            6: ('pos_fid', 'File Index'),

            11: ('secondary', '[unknown, unknown, '
                'tag type from TAGX in primary index header]'),

            21: ('parent_index', 'Parent'),
            22: ('first_child_index', 'First child'),
            23: ('last_child_index', 'Last child'),

            69 : ('image_index', 'Offset from first image record to the'
                                ' image record associated with this entry'
                                ' (masthead for periodical or thumbnail for'
                                ' article entry).'),
            70 : ('desc_offset', 'Description offset in cncx'),
            71 : ('author_offset', 'Author offset in cncx'),
            72 : ('image_caption_offset', 'Image caption offset in cncx'),
            73 : ('image_attr_offset', 'Image attribution offset in cncx'),

    }

    def __init__(self, tag_type, vals, cncx):
        self.value = vals if len(vals) > 1 else vals[0] if vals else None

        self.cncx_value = None
        if tag_type in self.TAG_MAP:
            self.attr, self.desc = self.TAG_MAP[tag_type]
        else:
            print('Unknown tag value: %%s'%tag_type)
            self.desc = '??Unknown (tag value: %d)'%tag_type
            self.attr = 'unknown'

        if '_offset' in self.attr:
            self.cncx_value = cncx[self.value]

    def __str__(self):
        if self.cncx_value is not None:
            return '%s : %r [%r]'%(self.desc, self.value, self.cncx_value)
        return '%s : %r'%(self.desc, self.value)

# }}}


class IndexEntry:  # {{{

    '''
    The index is made up of entries, each of which is represented by an
    instance of this class. Index entries typically point to offsets in the
    HTML, specify HTML sizes and point to text strings in the CNCX that are
    used in the navigation UI.
    '''

    def __init__(self, ident, entry, cncx):
        try:
            self.index = int(ident, 16)
        except ValueError:
            self.index = ident
        self.tags = [Tag(tag_type, vals, cncx) for tag_type, vals in
                iteritems(entry)]

    @property
    def label(self):
        for tag in self.tags:
            if tag.attr == 'label_offset':
                return tag.cncx_value
        return ''

    @property
    def offset(self):
        for tag in self.tags:
            if tag.attr == 'offset':
                return tag.value
        return 0

    @property
    def size(self):
        for tag in self.tags:
            if tag.attr == 'size':
                return tag.value
        return 0

    @property
    def depth(self):
        for tag in self.tags:
            if tag.attr == 'depth':
                return tag.value
        return 0

    @property
    def parent_index(self):
        for tag in self.tags:
            if tag.attr == 'parent_index':
                return tag.value
        return -1

    @property
    def first_child_index(self):
        for tag in self.tags:
            if tag.attr == 'first_child_index':
                return tag.value
        return -1

    @property
    def last_child_index(self):
        for tag in self.tags:
            if tag.attr == 'last_child_index':
                return tag.value
        return -1

    @property
    def pos_fid(self):
        for tag in self.tags:
            if tag.attr == 'pos_fid':
                return tag.value
        return [0, 0]

    def __str__(self):
        ans = ['Index Entry(index=%s, length=%d)'%(
            self.index, len(self.tags))]
        for tag in self.tags:
            if tag.value is not None:
                ans.append('\t'+str(tag))
        if self.first_child_index != -1:
            ans.append('\tNumber of children: %d'%(self.last_child_index -
                self.first_child_index + 1))
        return '\n'.join(ans)

# }}}


class IndexRecord:  # {{{

    '''
    Represents all indexing information in the MOBI, apart from indexing info
    in the trailing data of the text records.
    '''

    def __init__(self, records, index_header, cncx):
        self.alltext = None
        table = OrderedDict()
        tags = [TagX(x.tag, x.num_values, x.bitmask, x.eof) for x in
                index_header.tagx_entries]
        for record in records:
            raw = record.raw

            if raw[:4] != b'INDX':
                raise ValueError('Invalid Primary Index Record')

            parse_index_record(table, record.raw,
                    index_header.tagx_control_byte_count, tags,
                    index_header.index_encoding, {}, strict=True)

        self.indices = []

        for ident, entry in iteritems(table):
            self.indices.append(IndexEntry(ident, entry, cncx))

    def get_parent(self, index):
        if index.depth < 1:
            return None
        parent_depth = index.depth - 1
        for p in self.indices:
            if p.depth != parent_depth:
                continue

    def __str__(self):
        ans = ['*'*20 + ' Index Entries (%d entries) '%len(self.indices)+ '*'*20]
        a = ans.append

        def u(w):
            a('Unknown: %r (%d bytes) (All zeros: %r)'%(w,
                len(w), not bool(w.replace(b'\0', b''))))
        for entry in self.indices:
            offset = entry.offset
            a(str(entry))
            t = self.alltext
            if offset is not None and self.alltext is not None:
                a('\tHTML before offset: %r'%t[offset-50:offset])
                a('\tHTML after offset: %r'%t[offset:offset+50])
                p = offset+entry.size
                a('\tHTML before end: %r'%t[p-50:p])
                a('\tHTML after end: %r'%t[p:p+50])

            a('')

        return '\n'.join(ans)

# }}}


class CNCX:  # {{{

    '''
    Parses the records that contain the compiled NCX (all strings from the
    NCX). Presents a simple offset : string mapping interface to access the
    data.
    '''

    def __init__(self, records, codec):
        self.records = OrderedDict()
        record_offset = 0
        for record in records:
            raw = record.raw
            pos = 0
            while pos < len(raw):
                length, consumed = decint(raw[pos:])
                if length > 0:
                    try:
                        self.records[pos+record_offset] = raw[
                            pos+consumed:pos+consumed+length].decode(codec)
                    except:
                        byts = raw[pos:]
                        r = format_bytes(byts)
                        print('CNCX entry at offset %d has unknown format %s'%(
                            pos+record_offset, r))
                        self.records[pos+record_offset] = r
                        pos = len(raw)
                pos += consumed+length
            record_offset += 0x10000

    def __getitem__(self, offset):
        return self.records.get(offset)

    def __str__(self):
        ans = ['*'*20 + ' cncx (%d strings) '%len(self.records)+ '*'*20]
        for k, v in iteritems(self.records):
            ans.append('%10d : %s'%(k, v))
        return '\n'.join(ans)


# }}}

class ImageRecord:  # {{{

    def __init__(self, idx, record, fmt):
        self.raw = record.raw
        self.fmt = fmt
        self.idx = idx

    def dump(self, folder):
        name = '%06d'%self.idx
        with open(os.path.join(folder, name+'.'+self.fmt), 'wb') as f:
            f.write(self.raw)

# }}}


class BinaryRecord:  # {{{

    def __init__(self, idx, record):
        self.raw = record.raw
        sig = self.raw[:4]
        name = '%06d'%idx
        if sig in {b'FCIS', b'FLIS', b'SRCS', b'DATP', b'RESC', b'BOUN',
                b'FDST', b'AUDI', b'VIDE', b'CRES', b'CONT', b'CMET'}:
            name += '-' + sig.decode('ascii')
        elif sig == b'\xe9\x8e\r\n':
            name += '-' + 'EOF'
        self.name = name

    def dump(self, folder):
        with open(os.path.join(folder, self.name+'.bin'), 'wb') as f:
            f.write(self.raw)

# }}}


class FontRecord:  # {{{

    def __init__(self, idx, record):
        self.raw = record.raw
        name = '%06d'%idx
        self.font = read_font_record(self.raw)
        if self.font['err']:
            raise ValueError('Failed to read font record: %s Headers: %s'%(
                self.font['err'], self.font['headers']))
        self.payload = (self.font['font_data'] if self.font['font_data'] else
                self.font['raw_data'])
        self.name = '%s.%s'%(name, self.font['ext'])

    def dump(self, folder):
        with open(os.path.join(folder, self.name), 'wb') as f:
            f.write(self.payload)

# }}}


class TBSIndexing:  # {{{

    def __init__(self, text_records, indices, doc_type):
        self.record_indices = OrderedDict()
        self.doc_type = doc_type
        self.indices = indices
        pos = 0
        for r in text_records:
            start = pos
            pos += len(r.raw)
            end = pos - 1
            self.record_indices[r] = x = {'starts':[], 'ends':[],
                    'complete':[], 'geom': (start, end)}
            for entry in indices:
                istart, sz = entry.offset, entry.size
                iend = istart + sz - 1
                has_start = istart >= start and istart <= end
                has_end = iend >= start and iend <= end
                rec = None
                if has_start and has_end:
                    rec = 'complete'
                elif has_start and not has_end:
                    rec = 'starts'
                elif not has_start and has_end:
                    rec = 'ends'
                if rec:
                    x[rec].append(entry)

    def get_index(self, idx):
        for i in self.indices:
            if i.index in {idx, str(idx)}:
                return i
        raise IndexError('Index %d not found'%idx)

    def __str__(self):
        ans = ['*'*20 + ' TBS Indexing (%d records) '%len(self.record_indices)+ '*'*20]
        for r, dat in iteritems(self.record_indices):
            ans += self.dump_record(r, dat)[-1]
        return '\n'.join(ans)

    def dump(self, bdir):
        types = defaultdict(list)
        for r, dat in iteritems(self.record_indices):
            tbs_type, strings = self.dump_record(r, dat)
            if tbs_type == 0:
                continue
            types[tbs_type] += strings
        for typ, strings in iteritems(types):
            with open(os.path.join(bdir, 'tbs_type_%d.txt'%typ), 'wb') as f:
                f.write(as_bytes('\n'.join(strings)))

    def dump_record(self, r, dat):
        ans = []
        ans.append('\nRecord #%d: Starts at: %d Ends at: %d'%(r.idx,
            dat['geom'][0], dat['geom'][1]))
        s, e, c = dat['starts'], dat['ends'], dat['complete']
        ans.append(('\tContains: %d index entries '
            '(%d ends, %d complete, %d starts)')%tuple(map(len, (s+e+c, e,
                c, s))))
        byts = bytearray(r.trailing_data.get('indexing', b''))
        ans.append('TBS bytes: %s'%format_bytes(byts))
        for typ, entries in (('Ends', e), ('Complete', c), ('Starts', s)):
            if entries:
                ans.append('\t%s:'%typ)
                for x in entries:
                    ans.append(('\t\tIndex Entry: %s (Parent index: %s, '
                            'Depth: %d, Offset: %d, Size: %d) [%s]')%(
                        x.index, x.parent_index, x.depth, x.offset, x.size, x.label))

        def bin4(num):
            ans = bin(num)[2:]
            return as_bytes('0'*(4-len(ans)) + ans)

        def repr_extra(x):
            return str({bin4(k):v for k, v in iteritems(extra)})

        tbs_type = 0
        is_periodical = self.doc_type in (257, 258, 259)
        if len(byts):
            outermost_index, extra, consumed = decode_tbs(byts, flag_size=3)
            byts = byts[consumed:]
            for k in extra:
                tbs_type |= k
            ans.append('\nTBS: %d (%s)'%(tbs_type, bin4(tbs_type)))
            ans.append('Outermost index: %d'%outermost_index)
            ans.append('Unknown extra start bytes: %s'%repr_extra(extra))
            if is_periodical:  # Hierarchical periodical
                try:
                    byts, a = self.interpret_periodical(tbs_type, byts,
                        dat['geom'][0])
                except:
                    import traceback
                    traceback.print_exc()
                    a = []
                    print('Failed to decode TBS bytes for record: %d'%r.idx)
                ans += a
            if byts:
                sbyts = tuple(hex(b)[2:] for b in byts)
                ans.append('Remaining bytes: %s'%' '.join(sbyts))

        ans.append('')
        return tbs_type, ans

    def interpret_periodical(self, tbs_type, byts, record_offset):
        ans = []

        def read_section_transitions(byts, psi=None):  # {{{
            if psi is None:
                # Assume previous section is 1
                psi = self.get_index(1)

            while byts:
                ai, extra, consumed = decode_tbs(byts)
                byts = byts[consumed:]
                if extra.get(0b0010, None) is not None:
                    raise ValueError('Dont know how to interpret flag 0b0010'
                            ' while reading section transitions')
                if extra.get(0b1000, None) is not None:
                    if len(extra) > 1:
                        raise ValueError('Dont know how to interpret flags'
                                ' %r while reading section transitions'%extra)
                    nsi = self.get_index(psi.index+1)
                    ans.append('Last article in this record of section %d'
                            ' (relative to next section index [%d]): '
                            '%d [%d absolute index]'%(psi.index, nsi.index, ai,
                                ai+nsi.index))
                    psi = nsi
                    continue

                ans.append('First article in this record of section %d'
                        ' (relative to its parent section): '
                        '%d [%d absolute index]'%(psi.index, ai, ai+psi.index))

                num = extra.get(0b0100, None)
                if num is None:
                    msg = ('The section %d has at most one article'
                            ' in this record')%psi.index
                else:
                    msg = ('Number of articles in this record of '
                        'section %d: %d')%(psi.index, num)
                ans.append(msg)

                offset = extra.get(0b0001, None)
                if offset is not None:
                    if offset == 0:
                        ans.append('This record is spanned by the article:'
                                '%d'%(ai+psi.index))
                    else:
                        ans.append('->Offset to start of next section (%d) from start'
                            ' of record: %d [%d absolute offset]'%(psi.index+1,
                                offset, offset+record_offset))
            return byts
        # }}}

        def read_starting_section(byts):  # {{{
            orig = byts
            si, extra, consumed = decode_tbs(byts)
            byts = byts[consumed:]
            if len(extra) > 1 or 0b0010 in extra or 0b1000 in extra:
                raise ValueError('Dont know how to interpret flags %r'
                        ' when reading starting section'%extra)
            si = self.get_index(si)
            ans.append('The section at the start of this record is:'
                    ' %s'%si.index)
            if 0b0100 in extra:
                num = extra[0b0100]
                ans.append('The number of articles from the section %d'
                        ' in this record: %s'%(si.index, num))
            elif 0b0001 in extra:
                eof = extra[0b0001]
                if eof != 0:
                    raise ValueError('Unknown eof value %s when reading'
                            ' starting section. All bytes: %r'%(eof, orig))
                ans.append('??This record has more than one article from '
                        ' the section: %s'%si.index)
            return si, byts
        # }}}

        if tbs_type & 0b0100:
            # Starting section is the first section
            ssi = self.get_index(1)
        else:
            ssi, byts = read_starting_section(byts)

        byts = read_section_transitions(byts, ssi)

        return byts, ans

# }}}


class MOBIFile:  # {{{

    def __init__(self, mf):
        for x in ('raw', 'palmdb', 'record_headers', 'records', 'mobi_header',
                'huffman_record_nums',):
            setattr(self, x, getattr(mf, x))

        self.index_header = self.index_record = None
        self.indexing_record_nums = set()
        pir = getattr(self.mobi_header, 'primary_index_record', NULL_INDEX)
        if pir != NULL_INDEX:
            self.index_header = IndexHeader(self.records[pir])
            numi = self.index_header.index_count
            self.cncx = CNCX(self.records[
                pir+1+numi:pir+1+numi+self.index_header.num_of_cncx_blocks],
                self.index_header.index_encoding)
            self.index_record = IndexRecord(self.records[pir+1:pir+1+numi],
                    self.index_header, self.cncx)
            self.indexing_record_nums = set(range(pir,
                pir+1+numi+self.index_header.num_of_cncx_blocks))
        self.secondary_index_record = self.secondary_index_header = None
        sir = self.mobi_header.secondary_index_record
        if sir != NULL_INDEX:
            self.secondary_index_header = SecondaryIndexHeader(self.records[sir])
            numi = self.secondary_index_header.index_count
            self.indexing_record_nums.add(sir)
            self.secondary_index_record = IndexRecord(
                    self.records[sir+1:sir+1+numi], self.secondary_index_header, self.cncx)
            self.indexing_record_nums |= set(range(sir+1, sir+1+numi))

        ntr = self.mobi_header.number_of_text_records
        fii = self.mobi_header.first_image_index
        self.text_records = [TextRecord(r, self.records[r],
            self.mobi_header.extra_data_flags, mf.decompress6) for r in range(1,
            min(len(self.records), ntr+1))]
        self.image_records, self.binary_records = [], []
        self.font_records = []
        image_index = 0
        for i in range(self.mobi_header.first_resource_record, min(self.mobi_header.last_resource_record, len(self.records))):
            if i in self.indexing_record_nums or i in self.huffman_record_nums:
                continue
            image_index += 1
            r = self.records[i]
            fmt = None
            if i >= fii and r.raw[:4] not in {b'FLIS', b'FCIS', b'SRCS',
                    b'\xe9\x8e\r\n', b'RESC', b'BOUN', b'FDST', b'DATP',
                    b'AUDI', b'VIDE', b'FONT', b'CRES', b'CONT', b'CMET'}:
                try:
                    fmt = what(None, r.raw)
                except:
                    pass
            if fmt is not None:
                self.image_records.append(ImageRecord(image_index, r, fmt))
            elif r.raw[:4] == b'FONT':
                self.font_records.append(FontRecord(i, r))
            else:
                self.binary_records.append(BinaryRecord(i, r))

        if self.index_record is not None:
            self.tbs_indexing = TBSIndexing(self.text_records,
                    self.index_record.indices, self.mobi_header.type_raw)

    def print_header(self, f=sys.stdout):
        p = print_to_binary_file(f)
        p(str(self.palmdb))
        p()
        p('Record headers:')
        for i, r in enumerate(self.records):
            p('%6d. %s'%(i, r.header))

        p()
        p(str(self.mobi_header))
# }}}


def inspect_mobi(mobi_file, ddir):
    f = MOBIFile(mobi_file)
    with open(os.path.join(ddir, 'header.txt'), 'wb') as out:
        f.print_header(f=out)

    alltext = os.path.join(ddir, 'text.html')
    with open(alltext, 'wb') as of:
        alltext = b''
        for rec in f.text_records:
            of.write(rec.raw)
            alltext += rec.raw
        of.seek(0)

    root = html.fromstring(alltext.decode(f.mobi_header.encoding))
    with open(os.path.join(ddir, 'pretty.html'), 'wb') as of:
        of.write(html.tostring(root, pretty_print=True, encoding='utf-8',
            include_meta_content_type=True))

    if f.index_header is not None:
        f.index_record.alltext = alltext
        with open(os.path.join(ddir, 'index.txt'), 'wb') as out:
            print = print_to_binary_file(out)
            print(str(f.index_header), file=out)
            print('\n\n', file=out)
            if f.secondary_index_header is not None:
                print(str(f.secondary_index_header), file=out)
                print('\n\n', file=out)
            if f.secondary_index_record is not None:
                print(str(f.secondary_index_record), file=out)
                print('\n\n', file=out)
            print(str(f.cncx), file=out)
            print('\n\n', file=out)
            print(str(f.index_record), file=out)
        with open(os.path.join(ddir, 'tbs_indexing.txt'), 'wb') as out:
            print = print_to_binary_file(out)
            print(str(f.tbs_indexing), file=out)
        f.tbs_indexing.dump(ddir)

    for tdir, attr in [('text', 'text_records'), ('images', 'image_records'),
            ('binary', 'binary_records'), ('font', 'font_records')]:
        tdir = os.path.join(ddir, tdir)
        os.mkdir(tdir)
        for rec in getattr(f, attr):
            rec.dump(tdir)


# }}}
