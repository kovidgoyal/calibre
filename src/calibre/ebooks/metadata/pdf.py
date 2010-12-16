from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Read meta information from PDF files'''

#import re
from functools import partial

from calibre import prints
from calibre.constants import plugins
from calibre.ebooks.metadata import MetaInformation, string_to_authors

pdfreflow, pdfreflow_error = plugins['pdfreflow']

#_isbn_pat = re.compile(r'ISBN[: ]*([-0-9Xx]+)')

def get_metadata(stream, cover=True):
    if pdfreflow is None:
        raise RuntimeError(pdfreflow_error)
    stream.seek(0)
    raw = stream.read()
    #isbn = _isbn_pat.search(raw)
    #if isbn is not None:
    #    isbn = isbn.group(1).replace('-', '').replace(' ', '')
    info = pdfreflow.get_metadata(raw, cover)
    title = info.get('Title', None)
    au = info.get('Author', None)
    if au is None:
        au = [_('Unknown')]
    else:
        au = string_to_authors(au)
    mi = MetaInformation(title, au)
    #if isbn is not None:
    #    mi.isbn = isbn

    creator = info.get('Creator', None)
    if creator:
        mi.book_producer = creator

    keywords = info.get('Keywords', None)
    mi.tags = []
    if keywords:
        mi.tags = [x.strip() for x in keywords.split(',')]

    subject = info.get('Subject', None)
    if subject:
        mi.tags.insert(0, subject)

    if cover and 'cover' in info:
        data = info['cover']
        if data is None:
            prints(title, 'has no pages, cover extraction impossible.')
        else:
            mi.cover_data = ('png', data)

    return mi

get_quick_metadata = partial(get_metadata, cover=False)

from calibre.utils.podofo import set_metadata as podofo_set_metadata

def set_metadata(stream, mi):
    stream.seek(0)
    return podofo_set_metadata(stream, mi)


