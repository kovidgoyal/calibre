from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import os
from calibre.ebooks.oeb.base import OEBError
from calibre.ebooks.oeb.reader import OEBReader

__all__ = ['get_reader']

READER_REGISTRY = {
    '.opf': OEBReader,
    }

def ReaderFactory(path):
    ext = os.path.splitext(path)[1].lower()
    if not ext:
        return OEBReader
    return READER_REGISTRY[ext]()
