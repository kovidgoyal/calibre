# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

"""
Read content from ztxt pdb file.
"""

import io
import struct
from compression import zlib
from typing import IO, TYPE_CHECKING

from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ebooks.pdb.ztxt import zTXTError

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.ebooks.pdb.header import PdbHeaderReader
    from calibre.utils.logging import Log

SUPPORTED_VERSION = (1, 40)


class HeaderRecord:
    """
    The first record in the file is always the header record. It holds
    information related to the location of text, images, and so on
    in the file. This is used in conjunction with the sections
    defined in the file header.
    """

    def __init__(self, raw: bytes) -> None:
        (self.version,) = struct.unpack('>H', raw[0:2])
        (self.num_records,) = struct.unpack('>H', raw[2:4])
        (self.size,) = struct.unpack('>L', raw[4:8])
        (self.record_size,) = struct.unpack('>H', raw[8:10])
        (self.flags,) = struct.unpack('>B', raw[18:19])


class Reader(FormatReader):
    def __init__(self, header: PdbHeaderReader, stream: IO[bytes], log: Log, options: Values) -> None:
        self.stream = stream
        self.log = log
        self.options = options

        self.sections = []
        for i in range(header.num_sections):
            self.sections.append(header.section_data(i))

        self.header_record = HeaderRecord(self.section_data(0))

        vmajor = (self.header_record.version & 0x0000FF00) >> 8
        vminor = self.header_record.version & 0x000000FF
        if vmajor < 1 or (vmajor == 1 and vminor < 40):
            raise zTXTError(
                f'Unsupported ztxt version ({vmajor}.{vminor}). Only versions newer than {SUPPORTED_VERSION[0]}.{SUPPORTED_VERSION[1]} are supported.'
            )

        if (self.header_record.flags & 0x01) == 0:
            raise zTXTError('Only compression method 1 (random access) is supported')

        self.log.debug(f'Foud ztxt version: {vmajor}.{vminor}')

        # Initialize the decompressor
        self.uncompressor = zlib.decompressobj()
        self.uncompressor.decompress(self.section_data(1))

    def section_data(self, number: int) -> bytes:
        return self.sections[number]

    def decompress_text(self, number: int) -> bytes:
        if number == 1:
            self.uncompressor = zlib.decompressobj()
        return self.uncompressor.decompress(self.section_data(number))

    def extract_content(self, output_dir: str) -> str | OEBBook | None:
        raw_txt = b''

        self.log.info('Decompressing text...')
        for i in range(1, self.header_record.num_records + 1):
            self.log.debug(f'\tDecompressing text section {i}')
            raw_txt += self.decompress_text(i)

        self.log.info('Converting text to OEB...')
        stream = io.BytesIO(raw_txt)

        from calibre.customize.ui import plugin_for_input_format

        txt_plugin = plugin_for_input_format('txt')
        assert txt_plugin is not None
        for opt in txt_plugin.options:
            if not hasattr(self.options, opt.option.name):
                setattr(self.options, opt.option.name, opt.recommended_value)

        stream.seek(0)
        return txt_plugin.convert(stream, self.options, 'txt', self.log, {})
