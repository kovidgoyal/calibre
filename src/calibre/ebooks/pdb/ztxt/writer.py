'''
Writer content to ztxt pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import struct, zlib

from calibre.ebooks.pdb.formatwriter import FormatWriter
from calibre.ebooks.pdb.header import PdbHeaderBuilder
from calibre.ebooks.txt.txtml import TXTMLizer
from calibre.ebooks.txt.newlines import TxtNewlines, specified_newlines

MAX_RECORD_SIZE = 8192


class Writer(FormatWriter):

    def __init__(self, opts, log):
        self.opts = opts
        self.log = log

    def write_content(self, oeb_book, out_stream, metadata=None):
        title = self.opts.title if self.opts.title else oeb_book.metadata.title[0].value if oeb_book.metadata.title != [] else _('Unknown')

        txt_records, txt_length = self._generate_text(oeb_book)

        crc32 = 0
        section_lengths = []
        compressor = zlib.compressobj(9)
        self.log.info('Compressing data...')
        for i in range(0, len(txt_records)):
            self.log.debug('\tCompressing record %i' % i)
            txt_records[i] = compressor.compress(txt_records[i])
            txt_records[i] = txt_records[i] + compressor.flush(zlib.Z_FULL_FLUSH)
            section_lengths.append(len(txt_records[i]))
            crc32 = zlib.crc32(txt_records[i], crc32) & 0xffffffff

        header_record = self._header_record(txt_length, len(txt_records), crc32)
        section_lengths.insert(0, len(header_record))

        out_stream.seek(0)
        hb = PdbHeaderBuilder('zTXTGPlm', title)
        hb.build_header(section_lengths, out_stream)

        for record in [header_record]+txt_records:
            out_stream.write(record)

    def _generate_text(self, oeb_book):
        writer = TXTMLizer(self.log)
        txt = writer.extract_content(oeb_book, self.opts)

        self.log.debug('\tReplacing newlines with selected type...')
        txt = specified_newlines(TxtNewlines('windows').newline,
                txt).encode(self.opts.pdb_output_encoding, 'replace')

        txt_length = len(txt)

        txt_records = []
        for i in range(0, (len(txt) / MAX_RECORD_SIZE) + 1):
            txt_records.append(txt[i * MAX_RECORD_SIZE : (i * MAX_RECORD_SIZE) + MAX_RECORD_SIZE])

        return txt_records, txt_length

    def _header_record(self, txt_length, record_count, crc32):
        record = b''

        record += struct.pack('>H', 0x012c)             # [0:2], version. 0x012c = 1.44
        record += struct.pack('>H', record_count)       # [2:4], Number of PDB records used for the text of the book.
        record += struct.pack('>L', txt_length)         # [4:8], Uncompressed length of the entire text of the book.
        record += struct.pack('>H', MAX_RECORD_SIZE)    # [8:10], Maximum size of each record containing text
        record += struct.pack('>H', 0)                  # [10:12], Number of bookmarks.
        record += struct.pack('>H', 0)                  # [12:14], Bookmark record. 0 if there are no bookmarks.
        record += struct.pack('>H', 0)                  # [14:16], Number of annotations.
        record += struct.pack('>H', 0)                  # [16:18], Annotation record. 0 if there are no annotations.
        record += struct.pack('>B', 1)                  # [18:19], Flags. Bitmask, 0x01 = Random Access. 0x02 = Non-Uniform text block size.
        record += struct.pack('>B', 0)                  # [19:20], Reserved.
        record += struct.pack('>L', crc32)              # [20:24], crc32
        record += struct.pack('>LL', 0, 0)              # [24:32], padding

        return record
