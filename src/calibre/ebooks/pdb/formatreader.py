# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

"""
Interface defining the necessary public functions for a pdb format reader.
"""

from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.ebooks.pdb.header import PdbHeaderReader
    from calibre.utils.logging import Log


class FormatReader:
    def __init__(self, header: PdbHeaderReader, stream: IO[bytes], log: Log, options: Values) -> None:
        raise NotImplementedError()

    def extract_content(self, output_dir: str) -> str | OEBBook | None:
        raise NotImplementedError()
