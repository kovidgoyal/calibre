#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.docx.container import DOCX
from calibre.ebooks.docx.names import XPath, get

from calibre.utils.magick.draw import identify_data

images = XPath('//*[name()="w:drawing" or name()="w:pict"]/descendant::*[(name()="a:blip" and @r:embed) or (name()="v:imagedata" and @r:id)][1]')

def get_cover(docx):
    doc = docx.document
    rid_map = docx.document_relationships[0]
    for image in images(doc):
        rid = get(image, 'r:embed') or get(image, 'r:id')
        if rid in rid_map:
            try:
                raw = docx.read(rid_map[rid])
                width, height, fmt = identify_data(raw)
            except Exception:
                continue
            if 0.8 <= height/width <= 1.8 and height*width >= 160000:
                return (fmt, raw)

def get_metadata(stream):
    c = DOCX(stream, extract=False)
    mi = c.metadata
    try:
        cdata = get_cover(c)
    except Exception:
        cdata = None
        import traceback
        traceback.print_exc()
    c.close()
    stream.seek(0)
    if cdata is not None:
        mi.cover_data = cdata

    return mi

if __name__ == '__main__':
    import sys
    with open(sys.argv[-1], 'rb') as stream:
        print (get_metadata(stream))
