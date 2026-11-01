# License: GPLv3 Copyright: 2010, John Schember <john@nachtimwald.com>

"""
Read content from palmdoc pdb file.
"""

from typing import IO, TYPE_CHECKING

from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ptempfile import PersistentTemporaryFile

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.ebooks.pdb.header import PdbHeaderReader
    from calibre.utils.logging import Log


class Reader(FormatReader):
    def __init__(self, header: PdbHeaderReader, stream: IO[bytes], log: Log, options: Values) -> None:
        self.header = header
        self.stream = stream
        self.log = log
        self.options = options

    def extract_content(self, output_dir: str) -> str | OEBBook | None:
        self.log.info('Extracting PDF...')

        pdf = PersistentTemporaryFile('.pdf')
        pdf_path = pdf.name
        pdf.close()
        with open(pdf_path, 'wb') as pdf_out:
            for x in range(self.header.section_count()):
                pdf_out.write(self.header.section_data(x))

        from calibre.customize.ui import plugin_for_input_format

        pdf_plugin = plugin_for_input_format('pdf')
        assert pdf_plugin is not None
        for opt in pdf_plugin.options:
            if not hasattr(self.options, opt.option.name):
                setattr(self.options, opt.option.name, opt.recommended_value)

        return pdf_plugin.convert(open(pdf_path, 'rb'), self.options, 'pdf', self.log, {})
