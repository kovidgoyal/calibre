# License: GPLv3 Copyright: 2010, Greg Riker <griker@hotmail.com>

"""Read/write metadata from Amazon's topaz format"""

import io
import numbers
import sys
from struct import pack
from typing import IO, TYPE_CHECKING, TypedDict

from calibre import force_unicode
from calibre.ebooks.metadata import MetaInformation
from polyglot.builtins import int_to_byte

if TYPE_CHECKING:
    from collections.abc import Iterable

    from calibre.ebooks.metadata.book.base import Metadata


class TopazHeader(TypedDict, total=False):
    blocks: dict[int, dict[str, int]]
    tag: bytes  # never actually set, see generate_dkey()


type TopazHeaders = dict[bytes, TopazHeader]


def is_dkey(x: bytes | str) -> bool:
    q = b'dkey' if isinstance(x, bytes) else 'dkey'
    return x == q


class StringIO(io.StringIO):
    def write(self, x: str | bytes) -> int:
        if isinstance(x, bytes):
            x = x.decode('iso-8859-1')
        return io.StringIO.write(self, x)


class StreamSlicer:
    def __init__(self, stream: IO[bytes], start: int = 0, stop: int | None = None) -> None:
        self._stream = stream
        self.start = start
        if stop is None:
            stream.seek(0, 2)
            stop = stream.tell()
        self.stop = stop
        self._len = stop - start

    def __len__(self) -> int:
        return self._len

    def __getitem__(self, key: int | slice) -> bytes:
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
                return b''
            stream.seek(base + start)
            data = stream.read(size)
            if stride != 1:
                data = data[::stride]
            return data
        raise TypeError('stream indices must be integers')

    def __setitem__(self, key: int | slice, value: bytes) -> int:
        stream = self._stream
        base = self.start
        if isinstance(key, numbers.Integral):
            if len(value) != 1:
                raise ValueError('key and value lengths must match')
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
                raise ValueError('key and value lengths must match')
            stream.seek(base + start)
            return stream.write(value)
        raise TypeError('stream indices must be integers')

    def update(self, data_blocks: Iterable[bytes]) -> None:
        # Rewrite the stream
        stream = self._stream
        base = self.start
        stream.seek(base)
        self._stream.truncate(base)
        for block in data_blocks:
            stream.write(block)

    def truncate(self, value: int) -> None:
        self._stream.truncate(value)


class MetadataUpdater:
    def __init__(self, stream: IO[bytes]) -> None:
        self.stream = stream
        self.data = StreamSlicer(stream)

        sig = self.data[:4]
        if not sig.startswith(b'TPZ'):
            raise ValueError("'{}': Not a Topaz file".format(getattr(stream, 'name', 'Unnamed stream')))
        offset = 4

        self.header_records, consumed = self.decode_vwi(self.data[offset : offset + 4])
        offset += consumed
        self.topaz_headers, self.th_seq = self.get_headers(offset)

        # First integrity test - metadata header
        if b'metadata' not in self.topaz_headers:
            raise ValueError("'{}': Invalid Topaz format - no metadata record".format(getattr(stream, 'name', 'Unnamed stream')))

        # Second integrity test - metadata body
        md_offset = self.topaz_headers[b'metadata']['blocks'][0]['offset']
        md_offset += self.base
        if self.data[md_offset + 1 : md_offset + 9] != b'metadata':
            raise ValueError("'{}': Damaged metadata record".format(getattr(stream, 'name', 'Unnamed stream')))

    def book_length(self) -> int:
        """convenience method for retrieving book length"""
        self.get_original_metadata()
        if b'bookLength' in self.metadata:
            return int(self.metadata[b'bookLength'])
        return 0

    def decode_vwi(self, byts: bytes | bytearray) -> tuple[int, int]:
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

    def dump_headers(self) -> None:
        """Diagnostic"""
        print('\ndump_headers():')
        for tag in self.topaz_headers:
            print(f'{tag}: ')
            num_recs = len(self.topaz_headers[tag]['blocks'])
            print(f' num_recs: {num_recs}')
            if num_recs:
                print(' starting offset: 0x{:x}'.format(self.topaz_headers[tag]['blocks'][0]['offset']))

    def dump_hex(self, src: str, length: int = 16) -> None:
        """Diagnostic"""
        FILTER = ''.join([((len(repr(chr(x))) == 3) and chr(x)) or '.' for x in range(256)])
        N = 0
        result = ''
        while src:
            s, src = src[:length], src[length:]
            hexa = ' '.join([f'{ord(x):02X}' for x in s])
            s = s.translate(FILTER)
            result += '%04X   %-*s   %s\n' % (N, length * 3, hexa, s)  # ruff: ignore[printf-string-formatting]
            N += length
        print(result)

    def dump_metadata(self) -> None:
        """Diagnostic"""
        for tag in self.metadata:
            print(f'{tag}: {self.metadata[tag]!r}')

    def encode_vwi(self, value: int) -> bytes:
        ans: list[int] = []
        multi_byte = value > 0x7F
        while value:
            b = value & 0x7F
            value >>= 7
            if value == 0:
                if multi_byte:
                    ans.append(b | 0x80)
                    if ans[-1] == 0xFF:
                        ans.append(0x80)
                    if len(ans) == 4:
                        return pack('>BBBB', ans[3], ans[2], ans[1], ans[0])
                    elif len(ans) == 3:
                        return pack('>BBB', ans[2], ans[1], ans[0])
                    elif len(ans) == 2:
                        return pack('>BB', ans[1], ans[0])
                else:
                    return pack('>B', b)
            elif ans:
                ans.append(b | 0x80)
            else:
                ans.append(b)

        # If value == 0, return 0
        return pack('>B', 0x0)

    def generate_dkey(self) -> bytes | None:
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
        dks.write(self.data[offset : offset + len_uncomp].decode('iso-8859-1'))
        return dks.getvalue().encode('iso-8859-1')

    def get_headers(self, offset: int) -> tuple[TopazHeaders, list[bytes]]:
        # Build a dict of topaz_header records, list of order
        topaz_headers: TopazHeaders = {}
        th_seq: list[bytes] = []
        for x in range(self.header_records):
            offset += 1
            taglen, consumed = self.decode_vwi(self.data[offset : offset + 4])
            offset += consumed
            tag = self.data[offset : offset + taglen]
            offset += taglen
            num_vals, consumed = self.decode_vwi(self.data[offset : offset + 4])
            offset += consumed
            blocks: dict[int, dict[str, int]] = {}
            for val in range(num_vals):
                hdr_offset, consumed = self.decode_vwi(self.data[offset : offset + 4])
                offset += consumed
                len_uncomp, consumed = self.decode_vwi(self.data[offset : offset + 4])
                offset += consumed
                len_comp, consumed = self.decode_vwi(self.data[offset : offset + 4])
                offset += consumed
                blocks[val] = {'offset': hdr_offset, 'len_uncomp': len_uncomp, 'len_comp': len_comp}
            topaz_headers[tag] = {'blocks': blocks}
            th_seq.append(tag)
        self.eoth = self.data[offset]
        offset += 1
        self.base = offset
        return topaz_headers, th_seq

    def generate_metadata_stream(self) -> bytes:
        ms = io.BytesIO()
        ms.write(self.encode_vwi(len(self.md_header['tag'])))
        ms.write(self.md_header['tag'])
        ms.write(int_to_byte(self.md_header['flags']))
        ms.write(int_to_byte(len(self.metadata)))

        # Add the metadata fields.
        # for tag in self.metadata:
        for tag in self.md_seq:
            ms.write(self.encode_vwi(len(tag)))
            ms.write(tag)
            ms.write(self.encode_vwi(len(self.metadata[tag])))
            ms.write(self.metadata[tag])

        return ms.getvalue()

    def get_metadata(self) -> Metadata:
        """Return MetaInformation with title, author"""
        self.get_original_metadata()
        title = force_unicode(self.metadata[b'Title'], 'utf-8')
        authors = force_unicode(self.metadata[b'Authors'], 'utf-8').split(';')
        return MetaInformation(title, authors)

    def get_original_metadata(self) -> None:
        offset = self.base + self.topaz_headers[b'metadata']['blocks'][0]['offset']
        self.md_header: dict = {}
        taglen, consumed = self.decode_vwi(self.data[offset : offset + 4])
        offset += consumed
        self.md_header['tag'] = self.data[offset : offset + taglen]
        offset += taglen
        self.md_header['flags'] = ord(self.data[offset : offset + 1])
        offset += 1
        self.md_header['num_recs'] = ord(self.data[offset : offset + 1])
        offset += 1
        # print('self.md_header: %s' % self.md_header)

        self.metadata: dict[bytes, bytes] = {}
        self.md_seq: list[bytes] = []
        for x in range(self.md_header['num_recs']):
            taglen, consumed = self.decode_vwi(self.data[offset : offset + 4])
            offset += consumed
            tag = self.data[offset : offset + taglen]
            offset += taglen
            md_len, consumed = self.decode_vwi(self.data[offset : offset + 4])
            offset += consumed
            metadata = self.data[offset : offset + md_len]
            offset += md_len
            self.metadata[tag] = metadata
            self.md_seq.append(tag)

    def regenerate_headers(self, updated_md_len: int) -> bytes:

        original_md_len = self.topaz_headers[b'metadata']['blocks'][0]['len_uncomp']
        original_md_offset = self.topaz_headers[b'metadata']['blocks'][0]['offset']
        delta = updated_md_len - original_md_len

        # Copy the first 5 bytes of the file: sig + num_recs
        ths = io.BytesIO()
        ths.write(self.data[:5])

        # Rewrite the offsets for hdr_offsets > metadata offset
        for tag in self.th_seq:
            ths.write(b'c')
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

                    if tag == b'metadata':
                        ths.write(self.encode_vwi(updated_md_len))
                    else:
                        ths.write(self.encode_vwi(b['len_uncomp']))
                    ths.write(self.encode_vwi(b['len_comp']))
            else:
                ths.write(self.encode_vwi(0))
        self.original_md_start = original_md_offset + self.base
        self.original_md_len = original_md_len
        return ths.getvalue()

    def update(self, mi: Metadata) -> None:
        # Collect the original metadata
        self.get_original_metadata()

        try:
            from calibre.ebooks.conversion.config import load_defaults

            prefs = load_defaults('mobi_output')
            pas = prefs.get('prefer_author_sort', False)
        except Exception:
            pas = False

        if mi.author_sort and pas:
            authors = mi.author_sort
            self.metadata[b'Authors'] = authors.encode('utf-8')
        elif mi.authors:
            authors = '; '.join(mi.authors)
            self.metadata[b'Authors'] = authors.encode('utf-8')
        self.metadata[b'Title'] = mi.title.encode('utf-8')

        updated_metadata = self.generate_metadata_stream()
        # Skip tag_len, tag, extra
        prefix = len('metadata') + 2
        um_buf_len = len(updated_metadata) - prefix
        head = self.regenerate_headers(um_buf_len)

        # Chunk1: self.base -> original metadata start
        # Chunk2: original metadata end -> eof
        chunk1 = self.data[self.base : self.original_md_start]
        chunk2 = self.data[prefix + self.original_md_start + self.original_md_len :]

        self.stream.seek(0)
        self.stream.truncate(0)

        # Write the revised stream
        self.stream.write(head)
        self.stream.write(b'd')
        self.stream.write(chunk1)
        self.stream.write(updated_metadata)
        self.stream.write(chunk2)


def get_metadata(stream: IO[bytes]) -> Metadata:
    mu = MetadataUpdater(stream)
    return mu.get_metadata()


def set_metadata(stream: IO[bytes], mi: Metadata) -> None:
    mu = MetadataUpdater(stream)
    mu.update(mi)


if __name__ == '__main__':
    if False:
        # Test get_metadata()
        with open(sys.argv[1], 'rb') as f:
            print(get_metadata(f))
    else:
        # Test set_metadata()
        stream = io.BytesIO()
        with open(sys.argv[1], 'rb') as data:
            stream.write(data.read())
        mi = MetaInformation(title='Updated Title', authors=['Author, Random'])
        set_metadata(stream, mi)

        # Write the result
        tokens = sys.argv[1].rpartition('.')
        with open(tokens[0] + '-updated' + '.' + tokens[2], 'wb') as updated_data:
            updated_data.write(stream.getvalue())
