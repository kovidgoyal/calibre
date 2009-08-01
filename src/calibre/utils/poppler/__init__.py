#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.constants import plugins
from calibre.ebooks.metadata import MetaInformation, string_to_authors

poppler, poppler_err = plugins['calibre_poppler']

class NotAvailable(Exception):
    pass

def get_metadata(stream, cover=True):
    if not poppler:
        raise NotAvailable('Failed to load poppler with error: '+poppler_err)
    raw = stream.read()
    doc = poppler.PDFDoc()
    doc.load(raw)
    title = doc.title
    if not title or not title.strip():
        title = _('Unknown')
        if hasattr(stream, 'name'):
            title = os.path.splitext(stream.name)[0]
    author = doc.author
    authors = string_to_authors(author) if author else  [_('Unknown')]
    creator = doc.creator
    mi = MetaInformation(title, authors)

    if creator:
        mi.book_producer = creator

    if cover:
        from calibre.gui2 import is_ok_to_use_qt
        cdata = None
        if is_ok_to_use_qt():

            try:
                cdata = doc.render_page(0)
            except:
                import traceback
                traceback.print_exc()

        if cdata is not None:
            mi.cover_data = ('jpg', cdata)
    return mi




