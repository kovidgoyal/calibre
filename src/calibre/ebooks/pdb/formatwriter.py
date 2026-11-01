# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

"""
Interface defining the necessary public functions for a pdb format writer.
"""

from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import Metadata, OEBBook
    from calibre.utils.logging import Log


class FormatWriter:
    def __init__(self, opts: Values, log: Log) -> None:
        raise NotImplementedError()

    def write_content(self, oeb_book: OEBBook, output_stream: IO[bytes], metadata: Metadata | None = None) -> None:
        raise NotImplementedError()
