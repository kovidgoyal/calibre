#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Read metadata from RAR archives
'''

import os

from calibre.ptempfile import PersistentTemporaryFile, TemporaryDirectory
from calibre.libunrar import extract_member, names
from calibre import CurrentDir

def get_metadata(stream):
    from calibre.ebooks.metadata.archive import is_comic
    from calibre.ebooks.metadata.meta import get_metadata

    path = getattr(stream, 'name', False)
    if not path:
        pt = PersistentTemporaryFile('_rar-meta.rar')
        pt.write(stream.read())
        pt.close()
        path = pt.name
    path = os.path.abspath(path)
    file_names = list(names(path))
    if is_comic(file_names):
        return get_metadata(stream, 'cbr')
    for f in file_names:
        stream_type = os.path.splitext(f)[1].lower()
        if stream_type:
            stream_type = stream_type[1:]
            if stream_type in ('lit', 'opf', 'prc', 'mobi', 'fb2', 'epub',
                               'rb', 'imp', 'pdf', 'lrf', 'azw', 'azw1', 'azw3'):
                with TemporaryDirectory() as tdir:
                    with CurrentDir(tdir):
                       stream = extract_member(path, match=None, name=f,
                               as_file=True)[1]
                return get_metadata(stream, stream_type)
    raise ValueError('No ebook found in RAR archive')


