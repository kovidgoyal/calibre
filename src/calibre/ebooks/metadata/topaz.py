

__license__ = 'GPL 3'
__copyright__ = '2010, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

''' Read/write metadata from Amazon's topaz format '''
import io, sys, numbers
from struct import pack

from calibre.ebooks.metadata import MetaInformation
from calibre import force_unicode
from polyglot.builtins import codepoint_to_chr, int_to_byte


def is_dkey(x):
    q = b'dkey' if isinstance(x, bytes) else 'dkey'
    return x == q


class StringIO(io.StringIO):

    def write(self, x):
        if isinstance(x, bytes):
            x = x.decode('iso-8859-1')
        return io.StringIO.write(self, x)


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
        if isinstance(key, numbers.Integral):
            stream.seek(base + key)
            return stream.read(1)
        if isinstance(key, slice):
            start, stop, stride = key.indices(self._len)
            if stride < 0:
                start, stop = stop, start
            size = stop - start
            if size <= 0:
                return b""
            stream.seek(base + start)
            data = stream.read(size)
            if stride != 1:
                data = data[::stride]
            return data
        raise TypeError("stream indices must be integers")

    def __setitem__(self, key, value):
        stream = self._stream
        base = self.start
        if isinstance(key, numbers.Integral):
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
        self.data = StreamSlicer(stream)

        sig = self.data[:4]
        if not sig.startswith(b'TPZ'):
            raise ValueError("'%s': Not a Topaz file" % getattr(stream, 'name', 'Unnamed stream'))
        offset = 4

        self.header_records, consumed = self.decode_vwi(self.data[offset:offset+4])
        offset += consumed
        self.topaz_headers, self.th_seq = self.get_headers(offset)

        # First integrity test - metadata header
        if 'metadata' not in self.topaz_headers:
            raise ValueError("'%s': Invalid Topaz format - no metadata record" % getattr(stream, 'name', 'Unnamed stream'))

        # Second integrity test - metadata body
        md_offset = self.topaz_headers['metadata']['blocks'][0]['offset']
        md_offset += self.base
        if self.data[md_offset+1:md_offset+9] != b'metadata':
            raise ValueError("'%s': Damaged metadata record" % getattr(stream, 'name', 'Unnamed stream'))

    def book_length(self):
        ''' convenience method for retrieving book length '''
        self.get_original_metadata()
        if 'bookLength' in self.metadata:
            return int(self.metadata['bookLength'])
        return 0

    def decode_vwi(self, byts):
        pos, val = 0, 0
        done = False
        byts = bytearray(byts)
        while pos < len(byts) and not done:
            b = byts[pos]
            pos += 1
            if (b & 0x80) == 0:
                done = True
            b &= 0x7F
            val <<= 7
            val |= b
            if done:
                break
        return val, pos

    def dump_headers(self):
        ''' Diagnostic '''
        print("\ndump_headers():")
        for tag in self.topaz_headers:
            print("%s: " % (tag))
            num_recs = len(self.topaz_headers[tag]['blocks'])
            print(" num_recs: %d" % num_recs)
            if num_recs:
                print(" starting offset: 0x%x" % self.topaz_headers[tag]['blocks'][0]['offset'])

    def dump_hex(self, src, length=16):
        ''' Diagnostic '''
        FILTER=''.join([(len(repr(codepoint_to_chr(x)))==3) and codepoint_to_chr(x) or '.' for x in range(256)])
        N=0
        result=''
        while src:
            s,src = src[:length],src[length:]
            hexa = ' '.join(["%02X"%ord(x) for x in s])
            s = s.translate(FILTER)
            result += "%04X   %-*s   %s\n" % (N, length*3, hexa, s)
            N+=length
        print(result)

    def dump_metadata(self):
        ''' Diagnostic '''
        for tag in self.metadata:
            print('%s: %s' % (tag, repr(self.metadata[tag])))

    def encode_vwi(self,value):
        ans = []
        multi_byte = (value > 0x7f)
        while value:
            b = value & 0x7f
            value >>= 7
            if value == 0:
                if multi_byte:
                    ans.append(b|0x80)
                    if ans[-1] == 0xFF:
                        ans.append(0x80)
                    if len(ans) == 4:
                        return pack('>BBBB',ans[3],ans[2],ans[1],ans[0]).decode('iso-8859-1')
                    elif len(ans) == 3:
                        return pack('>BBB',ans[2],ans[1],ans[0]).decode('iso-8859-1')
                    elif len(ans) == 2:
                        return pack('>BB',ans[1],ans[0]).decode('iso-8859-1')
                else:
                    return pack('>B', b).decode('iso-8859-1')
            else:
                if len(ans):
                    ans.append(b|0x80)
                else:
                    ans.append(b)

        # If value == 0, return 0
        return pack('>B', 0x0).decode('iso-8859-1')

    def generate_dkey(self):
        for x in self.topaz_headers:
            if is_dkey(self.topaz_headers[x]['tag']):
                if self.topaz_headers[x]['blocks']:
                    offset = self.base + self.topaz_headers[x]['blocks'][0]['offset']
                    len_uncomp = self.topaz_headers[x]['blocks'][0]['len_uncomp']
                    break
                else:
                    return None
        dkey = self.topaz_headers[x]
        dks = StringIO()
        dks.write(self.encode_vwi(len(dkey['tag'])))
        offset += 1
        dks.write(dkey['tag'])
        offset += len('dkey')
        dks.write('\0')
        offset += 1
        dks.write(self.data[offset:offset + len_uncomp].decode('iso-8859-1'))
        return dks.getvalue().encode('iso-8859-1')

    def get_headers(self, offset):
        # Build a dict of topaz_header records, list of order
        topaz_headers = {}
        th_seq = []
        for x in range(self.header_records):
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
                offset += consumed
                len_uncomp, consumed = self.decode_vwi(self.data[offset:offset+4])
                offset += consumed
                len_comp, consumed = self.decode_vwi(self.data[offset:offset+4])
                offset += consumed
                blocks[val] = dict(offset=hdr_offset,len_uncomp=len_uncomp,len_comp=len_comp)
            topaz_headers[tag] = dict(blocks=blocks)
            th_seq.append(tag)
        self.eoth = self.data[offset]
        offset += 1
        self.base = offset
        return topaz_headers, th_seq

    def generate_metadata_stream(self):
        ms = StringIO()
        ms.write(self.encode_vwi(len(self.md_header['tag'])).encode('iso-8859-1'))
        ms.write(self.md_header['tag'])
        ms.write(int_to_byte(self.md_header['flags']))
        ms.write(int_to_byte(len(self.metadata)))

        # Add the metadata fields.
        # for tag in self.metadata:
        for tag in self.md_seq:
            ms.write(self.encode_vwi(len(tag)).encode('iso-8859-1'))
            ms.write(tag)
            ms.write(self.encode_vwi(len(self.metadata[tag])).encode('iso-8859-1'))
            ms.write(self.metadata[tag])

        return ms.getvalue()

    def get_metadata(self):
        ''' Return MetaInformation with title, author'''
        self.get_original_metadata()
        title = force_unicode(self.metadata['Title'], 'utf-8')
        authors = force_unicode(self.metadata['Authors'], 'utf-8').split(';')
        return MetaInformation(title, authors)

    def get_original_metadata(self):
        offset = self.base + self.topaz_headers['metadata']['blocks'][0]['offset']
        self.md_header = {}
        taglen, consumed = self.decode_vwi(self.data[offset:offset+4])
        offset += consumed
        self.md_header['tag'] = self.data[offset:offset+taglen]
        offset += taglen
        self.md_header['flags'] = ord(self.data[offset:offset+1])
        offset += 1
        self.md_header['num_recs'] = ord(self.data[offset:offset+1])
        offset += 1
        # print "self.md_header: %s" % self.md_header

        self.metadata = {}
        self.md_seq = []
        for x in range(self.md_header['num_recs']):
            taglen, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            tag = self.data[offset:offset+taglen]
            offset += taglen
            md_len, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            metadata = self.data[offset:offset + md_len]
            offset += md_len
            self.metadata[tag] = metadata
            self.md_seq.append(tag)

    def regenerate_headers(self, updated_md_len):

        original_md_len = self.topaz_headers['metadata']['blocks'][0]['len_uncomp']
        original_md_offset = self.topaz_headers['metadata']['blocks'][0]['offset']
        delta = updated_md_len - original_md_len

        # Copy the first 5 bytes of the file: sig + num_recs
        ths = io.StringIO()
        ths.write(self.data[:5])

        # Rewrite the offsets for hdr_offsets > metadata offset
        for tag in self.th_seq:
            ths.write('c')
            ths.write(self.encode_vwi(len(tag)))
            ths.write(tag)
            if self.topaz_headers[tag]['blocks']:
                ths.write(self.encode_vwi(len(self.topaz_headers[tag]['blocks'])))
                for block in self.topaz_headers[tag]['blocks']:
                    b = self.topaz_headers[tag]['blocks'][block]

                    if b['offset'] <= original_md_offset:
                        ths.write(self.encode_vwi(b['offset']))
                    else:
                        ths.write(self.encode_vwi(b['offset'] + delta))

                    if tag == 'metadata':
                        ths.write(self.encode_vwi(updated_md_len))
                    else:
                        ths.write(self.encode_vwi(b['len_uncomp']))
                    ths.write(self.encode_vwi(b['len_comp']))
            else:
                ths.write(self.encode_vwi(0))
        self.original_md_start = original_md_offset + self.base
        self.original_md_len = original_md_len
        return ths.getvalue().encode('iso-8859-1')

    def update(self,mi):
        # Collect the original metadata
        self.get_original_metadata()

        try:
            from calibre.ebooks.conversion.config import load_defaults
            prefs = load_defaults('mobi_output')
            pas = prefs.get('prefer_author_sort', False)
        except:
            pas = False

        if mi.author_sort and pas:
            authors = mi.author_sort
            self.metadata['Authors'] = authors.encode('utf-8')
        elif mi.authors:
            authors = '; '.join(mi.authors)
            self.metadata['Authors'] = authors.encode('utf-8')
        self.metadata['Title'] = mi.title.encode('utf-8')

        updated_metadata = self.generate_metadata_stream()
        # Skip tag_len, tag, extra
        prefix = len('metadata') + 2
        um_buf_len = len(updated_metadata) - prefix
        head = self.regenerate_headers(um_buf_len)

        # Chunk1: self.base -> original metadata start
        # Chunk2: original metadata end -> eof
        chunk1 = self.data[self.base:self.original_md_start]
        chunk2 = self.data[prefix + self.original_md_start + self.original_md_len:]

        self.stream.seek(0)
        self.stream.truncate(0)

        # Write the revised stream
        self.stream.write(head)
        self.stream.write('d')
        self.stream.write(chunk1)
        self.stream.write(updated_metadata)
        self.stream.write(chunk2)


def get_metadata(stream):
    mu = MetadataUpdater(stream)
    return mu.get_metadata()


def set_metadata(stream, mi):
    mu = MetadataUpdater(stream)
    mu.update(mi)
    return


if __name__ == '__main__':
    if False:
        # Test get_metadata()
        print(get_metadata(open(sys.argv[1], 'rb')))
    else:
        # Test set_metadata()
        stream = io.BytesIO()
        with open(sys.argv[1], 'rb') as data:
            stream.write(data.read())
        mi = MetaInformation(title="Updated Title", authors=['Author, Random'])
        set_metadata(stream, mi)

        # Write the result
        tokens = sys.argv[1].rpartition('.')
        with open(tokens[0]+'-updated' + '.' + tokens[2],'wb') as updated_data:
            updated_data.write(stream.getvalue())
