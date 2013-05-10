#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.docx.container import DOCX

from calibre.utils.zipfile import ZipFile
from calibre.utils.magick.draw import identify_data

def get_metadata(stream):
    c = DOCX(stream, extract=False)
    mi = c.metadata
    c.close()
    stream.seek(0)
    cdata = None
    with ZipFile(stream, 'r') as zf:
        for zi in zf.infolist():
            ext = zi.filename.rpartition('.')[-1].lower()
            if cdata is None and ext in {'jpeg', 'jpg', 'png', 'gif'}:
                raw = zf.read(zi)
                try:
                    width, height, fmt = identify_data(raw)
                except:
                    continue
                if 0.8 <= height/width <= 1.8 and height*width >= 12000:
                    cdata = (fmt, raw)
        if cdata is not None:
            mi.cover_data = cdata

    return mi

if __name__ == '__main__':
    import sys
    with open(sys.argv[-1], 'rb') as stream:
        print (get_metadata(stream))
