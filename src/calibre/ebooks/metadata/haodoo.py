# License: GPLv3 Copyright: 2012, Kan-Ru Chen <kanru@kanru.info>

"""
Read meta information from Haodoo.net pdb files.
"""

from typing import IO, TYPE_CHECKING

from calibre.ebooks.pdb.haodoo.reader import Reader
from calibre.ebooks.pdb.header import PdbHeaderReader

if TYPE_CHECKING:
    from calibre.ebooks.metadata.book.base import Metadata


def get_metadata(stream: IO[bytes], extract_cover: bool = True) -> Metadata:
    """
    Return metadata as a L{MetaInfo} object
    """
    stream.seek(0)

    pheader = PdbHeaderReader(stream)
    reader = Reader(pheader, stream, None, None)

    return reader.get_metadata()
