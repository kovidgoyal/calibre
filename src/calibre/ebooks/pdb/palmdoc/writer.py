'''
Writer content to palmdoc pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import struct

from calibre.ebooks.pdb.formatwriter import FormatWriter
from calibre.ebooks.pdb.header import PdbHeaderBuilder
from calibre.ebooks.txt.txtml import TXTMLizer
from calibre.ebooks.txt.newlines import TxtNewlines, specified_newlines

MAX_RECORD_SIZE = 4096


class Writer(FormatWriter):

    def __init__(self, opts, log):
        self.opts = opts
        self.log = log

    def write_content(self, oeb_book, out_stream, metadata=None):
        from calibre.ebooks.compression.palmdoc import compress_doc

        title = self.opts.title if self.opts.title else oeb_book.metadata.title[0].value if oeb_book.metadata.title != [] else _('Unknown')

        txt_records, txt_length = self._generate_text(oeb_book)
        header_record = self._header_record(txt_length, len(txt_records))

        section_lengths = [len(header_record)]
        self.log.info('Compessing data...')
        for i in range(0, len(txt_records)):
            self.log.debug('\tCompressing record %i' % i)
            txt_records[i] = compress_doc(txt_records[i])
            section_lengths.append(len(txt_records[i]))

        out_stream.seek(0)
        hb = PdbHeaderBuilder('TEXtREAd', title)
        hb.build_header(section_lengths, out_stream)

        for record in [header_record] + txt_records:
            out_stream.write(record)

    def _generate_text(self, oeb_book):
        writer = TXTMLizer(self.log)
        txt = writer.extract_content(oeb_book, self.opts)

        self.log.debug('\tReplacing newlines with selected type...')
        txt = specified_newlines(TxtNewlines('windows').newline,
                txt).encode(self.opts.pdb_output_encoding, 'replace')

        txt_length = len(txt)

        txt_records = []
        for i in range(0, (len(txt) // MAX_RECORD_SIZE) + 1):
            txt_records.append(txt[i * MAX_RECORD_SIZE: (i * MAX_RECORD_SIZE) + MAX_RECORD_SIZE])

        return txt_records, txt_length

    def _header_record(self, txt_length, record_count):
        record = b''

        record += struct.pack('>H', 2)                  # [0:2],   PalmDoc compression. (1 = No compression).
        record += struct.pack('>H', 0)                  # [2:4],   Always 0.
        record += struct.pack('>L', txt_length)         # [4:8],   Uncompressed length of the entire text of the book.
        record += struct.pack('>H', record_count)       # [8:10],  Number of PDB records used for the text of the book.
        record += struct.pack('>H', MAX_RECORD_SIZE)    # [10-12], Maximum size of each record containing text, always 4096.
        record += struct.pack('>L', 0)                  # [12-16], Current reading position, as an offset into the uncompressed text.

        return record
