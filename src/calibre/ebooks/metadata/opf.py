#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

from calibre.ebooks.metadata import parse_opf_version
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.metadata.utils import parse_opf

class DummyFile(object):

    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw

def get_metadata(stream):
    if isinstance(stream, bytes):
        stream = DummyFile(stream)
    root = parse_opf(stream)
    ver = parse_opf_version(root.get('version'))
    opf = OPF(None, preparsed_opf=root, read_toc=False)
    return opf.to_book_metadata(), ver, opf.raster_cover, opf.first_spine_item()
