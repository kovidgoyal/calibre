

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Support for reading the metadata from a LIT file.
'''

import io

from calibre.ebooks.metadata.opf2 import OPF
from polyglot.builtins import getcwd


def get_metadata(stream):
    from calibre.ebooks.lit.reader import LitContainer
    from calibre.utils.logging import Log
    litfile = LitContainer(stream, Log())
    src = litfile.get_metadata().encode('utf-8')
    litfile = litfile._litfile
    opf = OPF(io.BytesIO(src), getcwd())
    mi = opf.to_book_metadata()
    covers = []
    for item in opf.iterguide():
        if 'cover' not in item.get('type', '').lower():
            continue
        ctype = item.get('type')
        href = item.get('href', '')
        candidates = [href, href.replace('&', '%26')]
        for item in litfile.manifest.values():
            if item.path in candidates:
                try:
                    covers.append((litfile.get_file('/data/'+item.internal),
                                   ctype))
                except Exception:
                    pass
                break
    covers.sort(key=lambda x: len(x[0]), reverse=True)
    idx = 0
    if len(covers) > 1:
        if covers[1][1] == covers[0][1]+'-standard':
            idx = 1
    mi.cover_data = ('jpg', covers[idx][0])
    return mi
