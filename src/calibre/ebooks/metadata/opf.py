#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

from calibre.ebooks.metadata import parse_opf_version
from calibre.ebooks.metadata.opf2 import OPF, pretty_print
from calibre.ebooks.metadata.utils import parse_opf, normalize_languages, create_manifest_item
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

def set_metadata_opf2(root, cover_prefix, mi, opf_version, cover_data=None, apply_null=False, update_timestamp=False, force_identifiers=False):
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
    raster_cover = opf.raster_cover
    if raster_cover is None and cover_data is not None:
        if cover_prefix and not cover_prefix.endswith('/'):
            cover_prefix += '/'
        name = cover_prefix + 'cover.jpg'
        i = create_manifest_item(opf.root, name, 'cover')
        if i is not None:
            if opf_version.major < 3:
                [x.getparent().remove(x) for x in opf.root.xpath('//*[local-name()="meta" and @name="cover"]')]
                m = opf.create_metadata_element('meta', is_dc=False)
                m.set('name', 'cover'), m.set('content', i.get('id'))
            else:
                for x in opf.root.xpath('//*[local-name()="item" and contains(@properties, "cover-image")]'):
                    x.set('properties', x.get('properties').replace('cover-image', '').strip())
                i.set('properties', 'cover-image')
            raster_cover = name

    with pretty_print:
        return opf.render(), raster_cover

def set_metadata(stream, cover_prefix, mi, cover_data=None, apply_null=False, update_timestamp=False, force_identifiers=False):
    if isinstance(stream, bytes):
        stream = DummyFile(stream)
    root = parse_opf(stream)
    ver = parse_opf_version(root.get('version'))
    opfbytes, raster_cover = set_metadata_opf2(
        root, cover_prefix, mi, ver, cover_data=cover_data, apply_null=apply_null, update_timestamp=update_timestamp, force_identifiers=force_identifiers)
    return opfbytes, ver, raster_cover
