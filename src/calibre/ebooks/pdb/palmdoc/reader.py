# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

"""
Read content from palmdoc pdb file.
"""

import io
import struct
from typing import IO, TYPE_CHECKING

from calibre.ebooks.pdb.formatreader import FormatReader

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.ebooks.pdb.header import PdbHeaderReader
    from calibre.utils.logging import Log


class HeaderRecord:
    """
    The first record in the file is always the header record. It holds
    information related to the location of text, images, and so on
    in the file. This is used in conjunction with the sections
    defined in the file header.
    """

    def __init__(self, raw: bytes) -> None:
        (self.compression,) = struct.unpack('>H', raw[0:2])
        (self.num_records,) = struct.unpack('>H', raw[8:10])


class Reader(FormatReader):
    def __init__(self, header: PdbHeaderReader, stream: IO[bytes], log: Log, options: Values) -> None:
        self.stream = stream
        self.log = log
        self.options = options

        self.sections = []
        for i in range(header.num_sections):
            self.sections.append(header.section_data(i))

        self.header_record = HeaderRecord(self.section_data(0))

    def section_data(self, number: int) -> bytes:
        return self.sections[number]

    def decompress_text(self, number: int) -> bytes:
        if self.header_record.compression == 1:
            return self.section_data(number)
        if self.header_record.compression in {2, 258}:
            from calibre.ebooks.compression.palmdoc import decompress_doc

            return decompress_doc(self.section_data(number))
        return b''

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
