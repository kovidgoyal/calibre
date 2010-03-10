from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

''' Read/write metadata from Amazon's topaz format '''
import copy, StringIO, sys
from struct import pack, unpack

from calibre import prints
from calibre.ebooks.metadata import MetaInformation

def read_record(raw, name):
    idx = raw.find(name)
    if idx > -1:
        length = ord(raw[idx+len(name)])
        return raw[idx+len(name)+1:idx+len(name)+1+length]

def get_metadata(stream):
    raw = stream.read(8*1024)
    if not raw.startswith('TPZ'):
        raise ValueError('Not a Topaz file')
    first = raw.find('metadata')
    if first < 0:
        raise ValueError('Invalid Topaz file')
    second = raw.find('metadata', first+10)
    if second < 0:
        raise ValueError('Invalid Topaz file')
    raw = raw[second:second+1000]
    authors = read_record(raw, 'Authors')
    if authors:
        authors = authors.decode('utf-8', 'replace').split(';')
    else:
        authors = [_('Unknown')]
    title = read_record(raw, 'Title')
    if title:
        title = title.decode('utf-8', 'replace')
    else:
        raise ValueError('No metadata in file')
    #from calibre.ebooks.metadata import MetaInformation
    return MetaInformation(title, authors)

class StreamSlicer(object):

    def __init__(self, stream, start=0, stop=None):
        self._stream = stream
        self.start = start
        if stop is None:
            stream.seek(0, 2)
            stop = stream.tell()
        self.stop = stop
        self._len = stop - start

    def __len__(self):
        return self._len

    def __getitem__(self, key):
        stream = self._stream
        base = self.start
        if isinstance(key, (int, long)):
            stream.seek(base + key)
            return stream.read(1)
        if isinstance(key, slice):
            start, stop, stride = key.indices(self._len)
            if stride < 0:
                start, stop = stop, start
            size = stop - start
            if size <= 0:
                return ""
            stream.seek(base + start)
            data = stream.read(size)
            if stride != 1:
                data = data[::stride]
            return data
        raise TypeError("stream indices must be integers")

    def __setitem__(self, key, value):
        stream = self._stream
        base = self.start
        if isinstance(key, (int, long)):
            if len(value) != 1:
                raise ValueError("key and value lengths must match")
            stream.seek(base + key)
            return stream.write(value)
        if isinstance(key, slice):
            start, stop, stride = key.indices(self._len)
            if stride < 0:
                start, stop = stop, start
            size = stop - start
            if stride != 1:
                value = value[::stride]
            if len(value) != size:
                raise ValueError("key and value lengths must match")
            stream.seek(base + start)
            return stream.write(value)
        raise TypeError("stream indices must be integers")

    def update(self, data_blocks):
        # Rewrite the stream
        stream = self._stream
        base = self.start
        stream.seek(base)
        self._stream.truncate(base)
        for block in data_blocks:
            stream.write(block)

    def truncate(self, value):
        self._stream.truncate(value)

class MetadataUpdater(object):
    def __init__(self, stream):
        self.stream = stream
        raw = stream.read(8*1024)
        if not raw.startswith('TPZ'):
            raise ValueError('Not a Topaz file')
        first = raw.find('metadata')
        if first < 0:
            raise ValueError('Invalid Topaz file')

        self.data = StreamSlicer(stream)
        self.header_records, = unpack('>B',self.data[4])
        self.get_topaz_headers()

        # Seek the metadata block
        md_block_offset, spam = self.decode_vwi(self.data[first+9:first+13])
        md_block_offset += self.base
        if self.data[md_block_offset+1:md_block_offset+9] != 'metadata':
            raise ValueError('Invalid Topaz file')
        else:
            self.md_start = md_block_offset

        offset = self.get_md_header(self.md_start)
        self.metadata = {}
        self.md_end = self.get_original_metadata(offset)
        self.orig_md_len = self.md_end - self.md_start

    def decode_vwi(self,bytes):
        pos, val = 0, 0
        done = False
        while pos < len(bytes) and not done:
            b = ord(bytes[pos])
            pos += 1
            if (b & 0x80) == 0:
                done = True
            b &= 0x7F
            val <<= 7
            val |= b
            if done: break
        return val, pos

    def encode_vwi(self,value):
        bytes = []
        multi_byte = (value > 0x7f)
        while value:
            b = value & 0x7f
            value >>= 7
            if value == 0:
                if multi_byte:
                    bytes.append(b|0x80)
                    if len(bytes) == 4:
                        return pack('>BBBB',bytes[3],bytes[2],bytes[1],bytes[0]).decode('iso-8859-1')
                    elif len(bytes) == 3:
                        return pack('>BBB',bytes[2],bytes[1],bytes[0]).decode('iso-8859-1')
                    elif len(bytes) == 2:
                        return pack('>BB',bytes[1],bytes[0]).decode('iso-8859-1')
                else:
                    return pack('>B', b).decode('iso-8859-1')
            else:
                if len(bytes):
                    bytes.append(b|0x80)
                else:
                    bytes.append(b)

        # If value == 0, return 0
        return pack('>B', 0x0).decode('iso-8859-1')

    def fixup_topaz_headers(self, size_delta):
        # Rewrite Topaz Header.  Any offset > md_hdr_offset needs to be adjusted
        ths = StringIO.StringIO()
        md_header_offset = self.md_header_offset
        # Copy the first 5 bytes
        ths.write(self.data[:5])
        md_record = False
        for th in self.topaz_headers:
            ths.write('c')
            ths.write(self.encode_vwi(len(self.topaz_headers[th]['tag'])))
            ths.write(self.topaz_headers[th]['tag'])
            ths.write(self.encode_vwi(len(self.topaz_headers[th]['blocks'])))
            for block in self.topaz_headers[th]['blocks']:
                b = self.topaz_headers[th]['blocks'][block]
                if b['hdr_offset'] > md_header_offset:
                    vwi = self.encode_vwi(b['hdr_offset'] + size_delta)
                else:
                    vwi = self.encode_vwi(b['hdr_offset'])
                ths.write(vwi)
                if self.topaz_headers[th]['tag'] == 'metadata':
                    ths.write(self.encode_vwi(b['len_uncomp'] + size_delta))
                else:
                    ths.write(self.encode_vwi(b['len_uncomp']))
                ths.write(self.encode_vwi(b['len_comp']))

        return ths.getvalue().encode('iso-8859-1')

    def generate_dkey(self):
        for x in self.topaz_headers:
            #print "dkey['blocks']: %s" % self.topaz_headers[x]['blocks']
            if self.topaz_headers[x]['tag'] == 'dkey':
                if self.topaz_headers[x]['blocks']:
                    offset = self.base + self.topaz_headers[x]['blocks'][0]['hdr_offset']
                    len_uncomp = self.topaz_headers[x]['blocks'][0]['len_uncomp']
                    break
                else:
                    return None
        dkey = self.topaz_headers[x]
        dks = StringIO.StringIO()
        dks.write(self.encode_vwi(len(dkey['tag'])))
        offset += 1
        dks.write(dkey['tag'])
        offset += len('dkey')
        dks.write(chr(0))
        offset += 1
        dks.write(self.data[offset:offset + len_uncomp].decode('iso-8859-1'))
        return dks.getvalue().encode('iso-8859-1')

    def get_topaz_headers(self):
        offset = 5
        md_header_offset = 0
        dkey_len = 0
        # Find the offset of the metadata header record
        for hr in range(self.header_records):
            marker = self.data[offset]
            offset += 1
            taglen, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            tag = self.data[offset:offset+taglen]
            offset += taglen
            if not tag == 'metadata':
                num_vals, consumed = self.decode_vwi(self.data[offset:offset+4])
                offset += consumed
                for val in range(num_vals):
                    foo, consumed = self.decode_vwi(self.data[offset:offset+4])
                    offset += consumed
                    foo, consumed = self.decode_vwi(self.data[offset:offset+4])
                    offset += consumed
                    foo, consumed = self.decode_vwi(self.data[offset:offset+4])
                    offset += consumed
                continue
            num_vals, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            md_header_offset, consumed = self.decode_vwi(self.data[offset:offset+4])
            break
        self.md_header_offset = md_header_offset

        offset = 5
        topaz_headers = {}
        dkey_offset = 0
        lowest_payload_offset = sys.maxint
        lowest_offset_err = None
        for x in range(self.header_records):
            marker = self.data[offset]
            offset += 1
            taglen, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            tag = self.data[offset:offset+taglen]
            offset += taglen
            num_vals, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            blocks = {}
            for val in range(num_vals):
                hdr_offset, consumed = self.decode_vwi(self.data[offset:offset+4])
                if tag == 'dkey':
                    dkey_offset = hdr_offset
                if tag not in ['dkey','metadata']:
                    if hdr_offset < lowest_payload_offset:
                        lowest_payload_offset = hdr_offset
                        lowest_offset_err = "lowest_payload_offset: 0x%x (%s)" % (hdr_offset,tag)
                offset += consumed
                len_uncomp, consumed = self.decode_vwi(self.data[offset:offset+4])
                offset += consumed
                len_comp, consumed = self.decode_vwi(self.data[offset:offset+4])
                offset += consumed
                blocks[val] = dict(hdr_offset=hdr_offset,len_uncomp=len_uncomp,len_comp=len_comp)
            topaz_headers[x] = dict(tag=tag,blocks=blocks)
        self.topaz_headers = topaz_headers
        self.eod = self.data[offset]
        offset += 1
        self.base = offset
        self.lowest_payload_offset = lowest_payload_offset + self.base
        if self.lowest_payload_offset < self.md_header_offset:
            prints("Unexpected TPZ file layout:\n %s\n       metadata_offset: 0x%x" % (lowest_offset_err, self.md_header_offset))
            prints("metadata needs to be before payload")
        self.base_value = None
        if dkey_offset:
            self.base_value = self.data[offset:offset + dkey_offset]
        return md_header_offset, topaz_headers

    def generate_metadata_stream(self):
        ms = StringIO.StringIO()
        # Generate the header
        ms.write(self.encode_vwi(len(self.md_header['tag'])).encode('iso-8859-1'))
        ms.write(self.md_header['tag'])
        ms.write(chr(self.md_header['flags']))
        ms.write(chr(len(self.metadata)))

        # Add the metadata fields.
        for item in self.metadata:
            ms.write(self.encode_vwi(len(self.metadata[item]['tag'])).encode('iso-8859-1'))
            ms.write(self.metadata[item]['tag'])
            ms.write(self.encode_vwi(len(self.metadata[item]['metadata'])).encode('iso-8859-1'))
            ms.write(self.metadata[item]['metadata'])

        return ms.getvalue()

    def get_md_header(self,offset):
        md_header = {}
        taglen, consumed = self.decode_vwi(self.data[offset:offset+4])
        offset += consumed
        md_header['tag'] = self.data[offset:offset+taglen]
        offset += taglen
        md_header['flags'] = ord(self.data[offset])
        offset += 1
        md_header['records'] = ord(self.data[offset])
        offset += 1
        self.md_header = md_header
        return offset

    def get_original_metadata(self,offset):
        for x in range(self.md_header['records']):
            md_record = {}
            taglen, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            md_record['tag'] = self.data[offset:offset+taglen]
            offset += taglen
            md_len, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            md_record['metadata'] = self.data[offset:offset + md_len]
            offset += md_len
            self.metadata[x] = md_record
        return offset

    def hexdump(self, src, length=16):
        # Diagnostic
        FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
        N=0; result=''
        while src:
           s,src = src[:length],src[length:]
           hexa = ' '.join(["%02X"%ord(x) for x in s])
           s = s.translate(FILTER)
           result += "%04X   %-*s   %s\n" % (N, length*3, hexa, s)
           N+=length
        print result

    def update(self,mi):
        def update_metadata(tag,value):
            for item in self.metadata:
                if self.metadata[item]['tag'] == tag:
                    self.metadata[item]['metadata'] = value
                    return

        if self.md_start > self.lowest_payload_offset:
            raise ValueError('Unable to update metadata:')

        try:
             from calibre.ebooks.conversion.config import load_defaults
             prefs = load_defaults('mobi_output')
             pas = prefs.get('prefer_author_sort', False)
        except:
            pas = False

        if mi.author_sort and pas:
            authors = mi.author_sort
            update_metadata('Authors',authors.encode('utf-8'))
        elif mi.authors:
            authors = '; '.join(mi.authors)
            update_metadata('Authors',authors)
        update_metadata('Title',mi.title.encode('utf-8'))

        updated_metadata = self.generate_metadata_stream()
        head = self.fixup_topaz_headers(len(updated_metadata) - self.orig_md_len)
        dkey = self.generate_dkey()
        tail = copy.copy(self.data[self.md_end:])

        self.stream.seek(0)
        self.stream.truncate(0)
        self.stream.write(head)
        self.stream.write(self.eod)
        if self.base_value:
            self.stream.write(self.base_value)
        if dkey:
            self.stream.write(dkey)
        self.stream.write(updated_metadata)
        self.stream.write(tail)

def set_metadata(stream, mi):
    mu = MetadataUpdater(stream)
    mu.update(mi)
    return

if __name__ == '__main__':
    import cStringIO, sys
    print get_metadata(open(sys.argv[1], 'rb'))
