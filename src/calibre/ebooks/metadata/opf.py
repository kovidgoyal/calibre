#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from typing import IO, TYPE_CHECKING, cast

from lxml import etree

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPF, pretty_print
from calibre.ebooks.metadata.opf3 import apply_metadata, read_metadata
from calibre.ebooks.metadata.utils import create_manifest_item, normalize_languages, parse_opf, parse_opf_version

if TYPE_CHECKING:
    from _typeshed import SupportsRead
    from lxml.etree import _Element

    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.metadata.utils import OPFVersion

type MetadataResult = tuple[Metadata, OPFVersion | None, str | None, str | None]


class DummyFile:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def read(self) -> bytes:
        return self.raw


def get_metadata2(root: _Element, ver: OPFVersion, ftype: str = 'epub') -> MetadataResult:
    opf = OPF(None, preparsed_opf=root, read_toc=False)
    if ftype == 'kepub':
        raster_cover = opf.epub3_raster_cover or opf.raster_cover
    else:
        raster_cover = opf.raster_cover
    return opf.to_book_metadata(), ver, raster_cover, opf.first_spine_item()


def get_metadata3(root: _Element, ver: OPFVersion, ftype: str = 'epub') -> MetadataResult:
    return read_metadata(root, ver=ver, return_extra_data=True)


def get_metadata_from_parsed(root: _Element, ftype: str = 'epub') -> MetadataResult:
    ver = parse_opf_version(root.get('version'))
    f = get_metadata2 if ver.major < 3 else get_metadata3
    return f(root, ver, ftype)


def get_metadata(stream: bytes | SupportsRead[bytes], ftype: str = 'epub') -> MetadataResult:
    # DummyFile provides the read() method that parse_opf needs
    f = cast('IO[bytes]', DummyFile(stream)) if isinstance(stream, bytes) else stream
    root = parse_opf(f)
    return get_metadata_from_parsed(root, ftype)


def set_metadata_opf2(
    root: _Element,
    cover_prefix: str,
    mi: Metadata,
    opf_version: OPFVersion,
    cover_data: bytes | None = None,
    apply_null: bool = False,
    update_timestamp: bool = False,
    force_identifiers: bool = False,
    add_missing_cover: bool = True,
    ftype: str = 'epub',
) -> tuple[bytes, str | None]:
    mi = MetaInformation(mi)
    for x in ('guide', 'toc', 'manifest', 'spine'):
        setattr(mi, x, None)
    opf = OPF(None, preparsed_opf=root, read_toc=False)
    if mi.languages:
        mi.languages = normalize_languages(list(opf.raw_languages) or [], mi.languages)

    opf.smart_update(mi, apply_null=apply_null)
    if mi.uuid:
        opf.application_id = mi.uuid
    if apply_null or force_identifiers:
        opf.set_identifiers(mi.get_identifiers())
    else:
        orig = opf.get_identifiers()
        orig.update(mi.get_identifiers())
        opf.set_identifiers({k: v for k, v in orig.items() if k and v})
    if update_timestamp and mi.timestamp is not None:
        opf.timestamp = mi.timestamp
    raster_cover = opf.raster_cover
    if raster_cover is None and cover_data is not None and add_missing_cover:
        guide_raster_cover = opf.guide_raster_cover
        i = None
        if guide_raster_cover is not None:
            i = guide_raster_cover
            raster_cover = i.get('href')
        else:
            if cover_prefix and not cover_prefix.endswith('/'):
                cover_prefix += '/'
            name = cover_prefix + 'cover.jpg'
            i = create_manifest_item(opf.root, name, 'cover')
            if i is not None:
                raster_cover = name
        if i is not None:
            if opf_version.major < 3:
                [x.getparent().remove(x) for x in opf.root.xpath('//*[local-name()="meta" and @name="cover"]')]
                m = opf.create_metadata_element('meta', is_dc=False)
                m.set('name', 'cover'), m.set('content', i.get('id'))  # ty: ignore[invalid-argument-type] i always has an id
            if opf_version.major > 2 or ftype == 'kepub':
                for x in opf.root.xpath('//*[local-name()="item" and contains(@properties, "cover-image")]'):
                    x.set('properties', x.get('properties').replace('cover-image', '').strip())
                i.set('properties', 'cover-image')

    with pretty_print:
        return opf.render(), raster_cover


def set_metadata_opf3(
    root: _Element,
    cover_prefix: str,
    mi: Metadata,
    opf_version: OPFVersion,
    cover_data: bytes | None = None,
    apply_null: bool = False,
    update_timestamp: bool = False,
    force_identifiers: bool = False,
    add_missing_cover: bool = True,
    ftype: str = 'epub',
) -> tuple[bytes, str | None]:
    raster_cover = apply_metadata(
        root,
        mi,
        cover_prefix=cover_prefix,
        cover_data=cover_data,
        apply_null=apply_null,
        update_timestamp=update_timestamp,
        force_identifiers=force_identifiers,
        add_missing_cover=add_missing_cover,
    )
    return etree.tostring(root, encoding='utf-8'), raster_cover


def set_metadata(
    stream: bytes | SupportsRead[bytes],
    mi: Metadata,
    cover_prefix: str = '',
    cover_data: bytes | None = None,
    apply_null: bool = False,
    update_timestamp: bool = False,
    force_identifiers: bool = False,
    add_missing_cover: bool = True,
    ftype: str = 'epub',
) -> tuple[bytes, OPFVersion, str | None]:
    # DummyFile provides the read() method that parse_opf needs
    f = cast('IO[bytes]', DummyFile(stream)) if isinstance(stream, bytes) else stream
    root = parse_opf(f)
    ver = parse_opf_version(root.get('version'))
    f = set_metadata_opf2 if ver.major < 3 else set_metadata_opf3
    opfbytes, raster_cover = f(
        root,
        cover_prefix,
        mi,
        ver,
        cover_data=cover_data,
        ftype=ftype,
        apply_null=apply_null,
        update_timestamp=update_timestamp,
        force_identifiers=force_identifiers,
        add_missing_cover=add_missing_cover,
    )
    return opfbytes, ver, raster_cover
