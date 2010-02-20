from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from calibre.utils.zipfile import ZipFile
from calibre.ptempfile import TemporaryDirectory
from calibre import CurrentDir

def get_metadata(stream):
    from calibre.ebooks.metadata.meta import get_metadata
    from calibre.ebooks.metadata.archive import is_comic
    stream_type = None
    zf = ZipFile(stream, 'r')
    names = zf.namelist()
    if is_comic(names):
        # Is probably a comic
        return get_metadata(stream, 'cbz')

    for f in names:
        stream_type = os.path.splitext(f)[1].lower()
        if stream_type:
            stream_type = stream_type[1:]
            if stream_type in ('lit', 'opf', 'prc', 'mobi', 'fb2', 'epub',
                               'rb', 'imp', 'pdf', 'lrf'):
                with TemporaryDirectory() as tdir:
                    with CurrentDir(tdir):
                        path = zf.extract(f)
                        return get_metadata(open(path, 'rb'), stream_type)
    raise ValueError('No ebook found in ZIP archive')


