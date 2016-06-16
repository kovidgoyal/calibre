#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

from calibre.ebooks.metadata import parse_opf_version
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.metadata.utils import parse_opf, normalize_languages
from calibre.ebooks.metadata import MetaInformation

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

def set_metadata_opf2(root, mi, cover_data=None, apply_null=False, update_timestamp=False, force_identifiers=False):
    mi = MetaInformation(mi)
    for x in ('guide', 'toc', 'manifest', 'spine'):
        setattr(mi, x, None)
    opf = OPF(None, preparsed_opf=root, read_toc=False)
    if mi.languages:
        mi.languages = normalize_languages(list(opf.raw_languages) or [], mi.languages)

    opf.smart_update(mi, apply_null=apply_null)
    if getattr(mi, 'uuid', None):
        opf.application_id = mi.uuid
    if apply_null or force_identifiers:
        opf.set_identifiers(mi.get_identifiers())
    else:
        orig = opf.get_identifiers()
        orig.update(mi.get_identifiers())
        opf.set_identifiers({k:v for k, v in orig.iteritems() if k and v})
    if update_timestamp and mi.timestamp is not None:
        opf.timestamp = mi.timestamp
    return opf.render(), opf.raster_cover

def set_metadata(stream, mi, cover_data=None, apply_null=False, update_timestamp=False, force_identifiers=False):
    if isinstance(stream, bytes):
        stream = DummyFile(stream)
    root = parse_opf(stream)
    ver = parse_opf_version(root.get('version'))
    opfbytes, raster_cover = set_metadata_opf2(
        root, mi, cover_data=cover_data, apply_null=apply_null, update_timestamp=update_timestamp, force_identifiers=force_identifiers)
    return opfbytes, ver, raster_cover
