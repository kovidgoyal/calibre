#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Read metadata from RAR archives
'''

import os
from io import BytesIO

from calibre.utils.unrar import extract_member, names


def get_metadata(stream):
    from calibre.ebooks.metadata.archive import is_comic
    from calibre.ebooks.metadata.meta import get_metadata

    file_names = list(names(stream))
    if is_comic(file_names):
        return get_metadata(stream, 'cbr')
    for f in file_names:
        stream_type = os.path.splitext(f)[1].lower()
        if stream_type:
            stream_type = stream_type[1:]
            if stream_type in {'lit', 'opf', 'prc', 'mobi', 'fb2', 'epub',
                               'rb', 'imp', 'pdf', 'lrf', 'azw', 'azw1',
                               'azw3'}:
                name, data = extract_member(stream, match=None, name=f)
                stream = BytesIO(data)
                stream.name = os.path.basename(name)
                mi = get_metadata(stream, stream_type)
                mi.timestamp = None
                return mi
    raise ValueError('No ebook found in RAR archive')
