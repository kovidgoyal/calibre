#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal kovid@kovidgoyal.net

"""
Read metadata from RAR archives
"""

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
            if stream_type in {
                'lit',
                'opf',
                'prc',
                'mobi',
                'fb2',
                'epub',
                'rb',
                'imp',
                'pdf',
                'lrf',
                'azw',
                'azw1',
                'azw3',
            }:
                res = extract_member(stream, match=None, name=f)
                if res is None:
                    raise KeyError(f'There is no file named {f} in the archive')
                name, data = res
                stream = BytesIO(data)
                stream.name = os.path.basename(name)
                mi = get_metadata(stream, stream_type)
                mi.timestamp = None
                return mi
    raise ValueError('No ebook found in RAR archive')
